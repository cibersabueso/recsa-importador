from __future__ import annotations

import csv
import logging
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any, TextIO

from models.job import ArchivoJob, Job, JobPayload
from models.mapeo import ColumnaMapeo
from models.resultado import EstadisticasArchivo, ResultadoProceso
from services import queue_service
from services.file_service import UPLOAD_DIR
from utils.file_parser import (
    CHUNK_SIZE_DEFAULT,
    contar_lineas,
    es_tipo_delimitado,
    leer_archivo,
    leer_archivo_chunks,
)
from utils.validators import CAMPOS_ESTANDAR, normalizar_decimal, validar_fila

RESULTADOS_DIR = UPLOAD_DIR / "resultados"
RESULTADOS_DIR.mkdir(parents=True, exist_ok=True)

POLL_INTERVAL_SECONDS = 2.0
PROGRESO_INTERVALO_FILAS = 50_000
MAX_ERRORES_REGISTRADOS = 100

logger = logging.getLogger("recsa.worker")

_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()


def iniciar_worker() -> None:
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_loop, name="recsa-worker", daemon=True)
    _worker_thread.start()


def detener_worker() -> None:
    _stop_event.set()


def _loop() -> None:
    queue_service.inicializar()
    while not _stop_event.is_set():
        try:
            job = queue_service.dequeue()
            if job is None:
                _stop_event.wait(POLL_INTERVAL_SECONDS)
                continue
            _procesar_job(job)
        except Exception as error:  # noqa: BLE001
            logger.exception("Error en loop del worker: %s", error)
            _stop_event.wait(POLL_INTERVAL_SECONDS)


def _procesar_job(job: Job) -> None:
    resultado = ResultadoProceso(job_id=job.id, estado="procesando")
    try:
        _ejecutar(job.payload, resultado)
        resultado.estado = "completado"
        resultado.progreso_porcentaje = 100
        queue_service.update_status(job.id, "completed", resultado)
    except Exception as error:  # noqa: BLE001
        logger.exception("Error procesando job %s: %s", job.id, error)
        resultado.estado = "error"
        resultado.errores.append(str(error))
        queue_service.update_status(job.id, "error", resultado)


class _ContadorProgreso:
    def __init__(self, job_id: str, total_estimado: int, resultado: ResultadoProceso) -> None:
        self.job_id = job_id
        self.total_estimado = max(total_estimado, 1)
        self.resultado = resultado
        self.filas_procesadas = 0
        self._ultimo_reporte = 0

    def sumar(self, cantidad: int) -> None:
        if cantidad <= 0:
            return
        self.filas_procesadas += cantidad
        if self.filas_procesadas - self._ultimo_reporte >= PROGRESO_INTERVALO_FILAS:
            self._reportar()

    def _reportar(self) -> None:
        self._ultimo_reporte = self.filas_procesadas
        self.resultado.filas_procesadas = self.filas_procesadas
        porcentaje = int(100 * self.filas_procesadas / self.total_estimado)
        self.resultado.progreso_porcentaje = min(99, max(0, porcentaje))
        try:
            queue_service.update_progreso(self.job_id, self.resultado)
        except Exception as error:  # noqa: BLE001
            logger.warning("No se pudo reportar progreso: %s", error)

    def flush(self) -> None:
        if self.filas_procesadas > self._ultimo_reporte:
            self._reportar()


def _estimar_total_filas(archivos: list[ArchivoJob]) -> int:
    total = 0
    for archivo in archivos:
        ruta = Path(archivo.ruta)
        if not ruta.exists():
            continue
        if es_tipo_delimitado(archivo.tipo):
            try:
                lineas = contar_lineas(ruta)
                if archivo.tiene_encabezados and lineas > 0:
                    lineas -= 1
                total += lineas
            except OSError as error:
                logger.warning("No se pudo contar líneas de %s: %s", archivo.nombre, error)
    return total


def _ejecutar(payload: JobPayload, resultado: ResultadoProceso) -> None:
    archivos = payload.archivos
    if not archivos:
        raise ValueError("El job no incluye archivos")

    principal = next((a for a in archivos if a.orden == 1), None)
    if principal is None:
        raise ValueError("Falta archivo principal (orden 1)")

    secundarios = [a for a in archivos if a.archivo_id != principal.archivo_id]
    total_estimado = _estimar_total_filas(archivos)
    contador = _ContadorProgreso(resultado.job_id, total_estimado, resultado)

    archivo_salida = RESULTADOS_DIR / f"{resultado.job_id}.csv"
    estadisticas: list[EstadisticasArchivo] = []

    if not secundarios:
        stats_principal = _procesar_principal_streaming(
            principal, archivo_salida, contador, resultado
        )
        estadisticas.append(stats_principal)
        filas_salida = stats_principal.filas_validas
    else:
        indice, mapa_join, stats_principal = _indexar_principal(
            principal, contador, resultado
        )
        estadisticas.append(stats_principal)
        for secundario in secundarios:
            stats_sec = _enriquecer_desde_secundario(
                secundario, indice, mapa_join, contador, resultado
            )
            estadisticas.append(stats_sec)
        filas_salida = _escribir_indice(archivo_salida, indice)
        indice.clear()
        mapa_join.clear()

    contador.flush()

    resultado.detalle_archivos = estadisticas
    resultado.total_filas = sum(e.total_filas for e in estadisticas)
    resultado.filas_validas = filas_salida
    resultado.filas_con_error = sum(e.filas_con_error for e in estadisticas)
    resultado.duplicados = sum(e.duplicados for e in estadisticas)
    resultado.archivo_resultado = str(archivo_salida)
    resultado.filas_procesadas = contador.filas_procesadas


def _abrir_writer(
    archivo_salida: Path,
) -> tuple[TextIO, csv.DictWriter]:
    handle = archivo_salida.open("w", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=CAMPOS_ESTANDAR, delimiter=";")
    writer.writeheader()
    return handle, writer


def _fila_csv(fila: dict[str, str | None]) -> dict[str, str]:
    return {campo: (fila.get(campo) or "") for campo in CAMPOS_ESTANDAR}


def _iter_chunks_archivo(
    archivo: ArchivoJob,
) -> Iterator[list[dict[str, Any]]]:
    ruta = Path(archivo.ruta)
    if not ruta.exists():
        raise ValueError(f"Archivo no encontrado en disco: {archivo.nombre}")

    if es_tipo_delimitado(archivo.tipo):
        iterador = leer_archivo_chunks(
            ruta=ruta,
            tipo=archivo.tipo,
            delimitador=archivo.delimitador,
            codificacion=archivo.codificacion,
            tiene_encabezados=archivo.tiene_encabezados,
            chunksize=CHUNK_SIZE_DEFAULT,
        )
        for _, filas in iterador:
            yield filas
        return

    _, filas = leer_archivo(
        ruta=ruta,
        tipo=archivo.tipo,
        delimitador=archivo.delimitador,
        codificacion=archivo.codificacion,
        tiene_encabezados=archivo.tiene_encabezados,
    )
    for inicio in range(0, len(filas), CHUNK_SIZE_DEFAULT):
        yield filas[inicio : inicio + CHUNK_SIZE_DEFAULT]


def _resolver_columna_origen(archivo: ArchivoJob, destino: str) -> str:
    return next(
        (col.origen for col in archivo.columnas if col.destino == destino),
        destino,
    )


def _columna_identidad_origen(archivo: ArchivoJob) -> str:
    return _resolver_columna_origen(archivo, archivo.columna_clave)


def _columna_join_origen(archivo: ArchivoJob) -> str:
    destino = archivo.columna_join or archivo.columna_clave
    return _resolver_columna_origen(archivo, destino)


def _obligatorios(archivo: ArchivoJob) -> list[str]:
    return [
        col.destino
        for col in archivo.columnas
        if col.obligatorio and col.destino is not None
    ]


def _procesar_principal_streaming(
    archivo: ArchivoJob,
    archivo_salida: Path,
    contador: _ContadorProgreso,
    resultado: ResultadoProceso,
) -> EstadisticasArchivo:
    obligatorios = _obligatorios(archivo)
    col_identidad = _columna_identidad_origen(archivo)

    claves_vistas: set[str] = set()
    total_filas = 0
    filas_validas = 0
    filas_con_error = 0
    duplicados = 0

    handle, writer = _abrir_writer(archivo_salida)
    try:
        for filas in _iter_chunks_validado(archivo, [col_identidad], resultado):
            total_filas += len(filas)
            for fila_origen in filas:
                fila_destino = _aplicar_mapeo(
                    fila_origen, archivo.columnas, archivo.separador_decimal
                )
                es_valida, _errores = validar_fila(fila_destino, obligatorios)
                if not es_valida:
                    filas_con_error += 1
                    _registrar_error(
                        resultado,
                        archivo.nombre,
                        "campos obligatorios vacíos",
                        fila_origen,
                    )
                    continue
                clave = fila_origen.get(col_identidad)
                if clave is None or str(clave).strip() == "":
                    filas_con_error += 1
                    _registrar_error(
                        resultado, archivo.nombre, "columna identidad vacía", fila_origen
                    )
                    continue
                clave_str = str(clave).strip()
                if clave_str in claves_vistas:
                    duplicados += 1
                    continue
                claves_vistas.add(clave_str)
                writer.writerow(_fila_csv(fila_destino))
                filas_validas += 1
            contador.sumar(len(filas))
    finally:
        handle.close()

    return EstadisticasArchivo(
        archivo_id=archivo.archivo_id,
        nombre=archivo.nombre,
        orden=archivo.orden,
        total_filas=total_filas,
        filas_validas=filas_validas,
        filas_con_error=filas_con_error,
        duplicados=duplicados,
        separador=archivo.delimitador,
        columna_clave=archivo.columna_clave,
    )


def _indexar_principal(
    archivo: ArchivoJob,
    contador: _ContadorProgreso,
    resultado: ResultadoProceso,
) -> tuple[
    dict[str, dict[str, str | None]],
    dict[str, list[str]],
    EstadisticasArchivo,
]:
    obligatorios = _obligatorios(archivo)
    col_identidad = _columna_identidad_origen(archivo)
    col_join = _columna_join_origen(archivo)

    indice: dict[str, dict[str, str | None]] = {}
    mapa_join: dict[str, list[str]] = {}
    total_filas = 0
    filas_validas = 0
    filas_con_error = 0
    duplicados = 0

    for filas in _iter_chunks_validado(
        archivo, [col_identidad, col_join], resultado
    ):
        total_filas += len(filas)
        for fila_origen in filas:
            fila_destino = _aplicar_mapeo(
                fila_origen, archivo.columnas, archivo.separador_decimal
            )
            es_valida, _errores = validar_fila(fila_destino, obligatorios)
            if not es_valida:
                filas_con_error += 1
                _registrar_error(
                    resultado,
                    archivo.nombre,
                    "campos obligatorios vacíos",
                    fila_origen,
                )
                continue
            clave = fila_origen.get(col_identidad)
            if clave is None or str(clave).strip() == "":
                filas_con_error += 1
                _registrar_error(
                    resultado, archivo.nombre, "columna identidad vacía", fila_origen
                )
                continue
            clave_str = str(clave).strip()
            if clave_str in indice:
                duplicados += 1
                continue
            indice[clave_str] = fila_destino
            join_valor = fila_origen.get(col_join)
            if join_valor is not None and str(join_valor).strip() != "":
                join_str = str(join_valor).strip()
                mapa_join.setdefault(join_str, []).append(clave_str)
            filas_validas += 1
        contador.sumar(len(filas))

    estadistica = EstadisticasArchivo(
        archivo_id=archivo.archivo_id,
        nombre=archivo.nombre,
        orden=archivo.orden,
        total_filas=total_filas,
        filas_validas=filas_validas,
        filas_con_error=filas_con_error,
        duplicados=duplicados,
        separador=archivo.delimitador,
        columna_clave=archivo.columna_clave,
    )
    return indice, mapa_join, estadistica


def _enriquecer_desde_secundario(
    archivo: ArchivoJob,
    indice: dict[str, dict[str, str | None]],
    mapa_join: dict[str, list[str]],
    contador: _ContadorProgreso,
    resultado: ResultadoProceso,
) -> EstadisticasArchivo:
    col_join = _columna_join_origen(archivo)

    total_filas = 0
    filas_validas = 0
    filas_con_error = 0
    sin_match = 0

    for filas in _iter_chunks_validado(archivo, [col_join], resultado):
        total_filas += len(filas)
        for fila_origen in filas:
            join_valor = fila_origen.get(col_join)
            if join_valor is None or str(join_valor).strip() == "":
                filas_con_error += 1
                _registrar_error(
                    resultado, archivo.nombre, "columna join vacía", fila_origen
                )
                continue
            join_str = str(join_valor).strip()
            claves_identidad = mapa_join.get(join_str)
            if not claves_identidad:
                sin_match += 1
                continue
            fila_destino = _aplicar_mapeo(
                fila_origen, archivo.columnas, archivo.separador_decimal
            )
            for clave_identidad in claves_identidad:
                fila_principal = indice.get(clave_identidad)
                if fila_principal is None:
                    continue
                for campo, valor in fila_destino.items():
                    if valor is not None and fila_principal.get(campo) in (None, ""):
                        fila_principal[campo] = valor
            filas_validas += 1
        contador.sumar(len(filas))

    return EstadisticasArchivo(
        archivo_id=archivo.archivo_id,
        nombre=archivo.nombre,
        orden=archivo.orden,
        total_filas=total_filas,
        filas_validas=filas_validas,
        filas_con_error=filas_con_error,
        duplicados=sin_match,  # Reutiliza el campo para reportar filas sin match en el principal
        separador=archivo.delimitador,
        columna_clave=archivo.columna_clave,
    )


def _iter_chunks_seguro(
    archivo: ArchivoJob, resultado: ResultadoProceso
) -> Iterator[list[dict[str, Any]]]:
    iterador = _iter_chunks_archivo(archivo)
    while True:
        try:
            chunk = next(iterador)
        except StopIteration:
            return
        except (UnicodeDecodeError, ValueError) as error:
            _registrar_error(
                resultado, archivo.nombre, f"chunk descartado: {error}", None
            )
            continue
        yield chunk


def _iter_chunks_validado(
    archivo: ArchivoJob,
    columnas_requeridas: list[str],
    resultado: ResultadoProceso,
) -> Iterator[list[dict[str, Any]]]:
    requeridas = [col for col in columnas_requeridas if col]
    validado = False
    for chunk in _iter_chunks_seguro(archivo, resultado):
        if not validado and chunk:
            disponibles = set(chunk[0].keys())
            faltantes = [col for col in requeridas if col not in disponibles]
            if faltantes:
                raise ValueError(
                    f"Archivo '{archivo.nombre}': faltan columnas requeridas "
                    f"{faltantes}. Disponibles: {sorted(disponibles)}"
                )
            validado = True
        yield chunk


def _registrar_error(
    resultado: ResultadoProceso,
    nombre_archivo: str,
    motivo: str,
    fila: dict[str, Any] | None,
) -> None:
    if len(resultado.errores) >= MAX_ERRORES_REGISTRADOS:
        return
    if fila is None:
        mensaje = f"{nombre_archivo}: {motivo}"
    else:
        preview = {k: v for k, v in list(fila.items())[:4]}
        mensaje = f"{nombre_archivo}: {motivo} | {preview}"
    resultado.errores.append(mensaje)


def _escribir_indice(
    archivo_salida: Path, indice: dict[str, dict[str, str | None]]
) -> int:
    handle, writer = _abrir_writer(archivo_salida)
    total = 0
    try:
        for fila in indice.values():
            fusionada: dict[str, str | None] = {campo: None for campo in CAMPOS_ESTANDAR}
            fusionada.update(fila)
            writer.writerow(_fila_csv(fusionada))
            total += 1
    finally:
        handle.close()
    return total


def _aplicar_mapeo(
    fila_origen: dict[str, Any],
    columnas: list[ColumnaMapeo],
    separador_decimal: str,
) -> dict[str, str | None]:
    fila_destino: dict[str, str | None] = {campo: None for campo in CAMPOS_ESTANDAR}
    for columna in columnas:
        if columna.destino not in CAMPOS_ESTANDAR:
            continue
        valor = fila_origen.get(columna.origen)
        if valor is None:
            fila_destino[columna.destino] = None
            continue
        texto = str(valor).strip() or None
        if columna.destino in {"monto_deuda_original", "monto_deuda_actual"}:
            texto = normalizar_decimal(texto, separador_decimal)
        fila_destino[columna.destino] = texto
    return fila_destino
