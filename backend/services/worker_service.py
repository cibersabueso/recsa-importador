from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

from psycopg import Connection

from db._nombres import nombre_tabla_cliente
from db.db_config import resolver_db
from db.postgres_client import ensure_schema, get_connection
from models.job import ArchivoJob, Job, JobPayload
from models.mapeo import ColumnaMapeo
from models.resultado import EstadisticasArchivo, ResultadoProceso
from services import queue_service
from services.file_service import UPLOAD_DIR
from services.progress_tracker import NO_OP_PROGRESS, ProgressTracker
from services.sinks import CsvSink, FilaSink, PostgresSink
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

SinkTipo = Literal["csv", "postgres"]

logger = logging.getLogger("recsa.worker")

_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()

_NOMBRES_REGISTRY: dict[str, list[str]] = {}


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
        queue_service.update_status(job.id, "completado", resultado)
    except Exception as error:  # noqa: BLE001
        logger.exception("Error procesando job %s: %s", job.id, error)
        resultado.estado = "error"
        resultado.errores.append(str(error))
        queue_service.update_status(job.id, "error", resultado)


class _ContadorProgreso:
    def __init__(
        self,
        job_id: str,
        total_estimado: int,
        resultado: ResultadoProceso,
        logger: logging.Logger | None = None,
        progress: ProgressTracker | None = None,
    ) -> None:
        self.job_id = job_id
        self.total_estimado = max(total_estimado, 1)
        self.resultado = resultado
        self.filas_procesadas = 0
        self._ultimo_reporte = 0
        self._log: logging.Logger = (
            logger if logger is not None else logging.getLogger("recsa.worker")
        )
        self._progress = progress

    def sumar(self, cantidad: int) -> None:
        if cantidad <= 0:
            return
        self.filas_procesadas += cantidad
        if self._progress is not None:
            self._progress.avanzar(cantidad)
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
            self._log.warning("No se pudo reportar progreso: %s", error)

    def flush(self) -> None:
        if self.filas_procesadas > self._ultimo_reporte:
            self._reportar()


def _estimar_lineas_archivo(
    archivo: ArchivoJob, logger: logging.Logger | None = None
) -> int:
    log = logger if logger is not None else logging.getLogger("recsa.worker")
    ruta = Path(archivo.ruta)
    if not ruta.exists():
        return 0
    if not es_tipo_delimitado(archivo.tipo):
        return 0
    try:
        lineas = contar_lineas(ruta)
    except OSError as error:
        log.warning("No se pudo contar líneas de %s: %s", archivo.nombre, error)
        return 0
    if archivo.tiene_encabezados and lineas > 0:
        lineas -= 1
    return lineas


def _estimar_total_filas(
    archivos: list[ArchivoJob], logger: logging.Logger | None = None
) -> int:
    return sum(_estimar_lineas_archivo(a, logger) for a in archivos)


def _crear_sink(
    tipo: SinkTipo, job_id: str, payload: JobPayload
) -> tuple[FilaSink, str, Connection | None]:
    if tipo == "csv":
        archivo_salida = RESULTADOS_DIR / f"{job_id}.csv"
        return CsvSink(archivo_salida), str(archivo_salida), None
    pais = payload.proceso.pais
    db_config = resolver_db(pais)
    ensure_schema(db_config)
    conn = get_connection(db_config)
    nombre_tabla = nombre_tabla_cliente(payload.proceso.empresa)
    sink = PostgresSink(conn, job_id, nombre_tabla)
    pais_label = pais.strip().upper() if pais else "default"
    identificador = (
        f"postgres://{db_config.database}.{nombre_tabla}"
        f"?job_id={job_id}&pais={pais_label}"
    )
    return sink, identificador, conn


def _ejecutar(
    payload: JobPayload,
    resultado: ResultadoProceso,
    sink: SinkTipo = "csv",
    logger: logging.Logger | None = None,
    nombres_por_archivo: dict[str, list[str]] | None = None,
    progress: ProgressTracker | None = None,
) -> None:
    log = logger if logger is not None else logging.getLogger("recsa.worker")
    progreso = progress if progress is not None else NO_OP_PROGRESS
    archivos = payload.archivos
    if not archivos:
        raise ValueError("El job no incluye archivos")

    principal = next((a for a in archivos if a.orden == 1), None)
    if principal is None:
        raise ValueError("Falta archivo principal (orden 1)")

    secundarios = [a for a in archivos if a.archivo_id != principal.archivo_id]

    if nombres_por_archivo:
        for archivo_id, nombres in nombres_por_archivo.items():
            if nombres:
                _NOMBRES_REGISTRY[archivo_id] = list(nombres)

    progreso.iniciar_fase("Estimando filas totales", None)
    log.info("Estimando filas totales...")
    total_estimado = _estimar_total_filas(archivos, log)
    log.info("Total estimado: %d", total_estimado)
    contador = _ContadorProgreso(
        resultado.job_id, total_estimado, resultado, log, progress=progress
    )

    estadisticas: list[EstadisticasArchivo] = []
    fila_sink, identificador, conn = _crear_sink(sink, resultado.job_id, payload)

    try:
        total_principal = _estimar_lineas_archivo(principal, log)
        progreso.iniciar_fase(
            f"Procesando archivo principal: {principal.nombre}", total_principal
        )
        log.info("Procesando archivo principal: %s", principal.nombre)
        if not secundarios:
            stats_principal = _procesar_principal_streaming(
                principal, fila_sink, contador, resultado
            )
            estadisticas.append(stats_principal)
            filas_salida = stats_principal.filas_validas
        else:
            indice, mapa_join, stats_principal = _indexar_principal(
                principal, contador, resultado
            )
            estadisticas.append(stats_principal)
            log.info("Indice principal con %d claves", len(indice))
            for secundario in secundarios:
                total_sec = _estimar_lineas_archivo(secundario, log)
                progreso.iniciar_fase(
                    f"Enriqueciendo desde: {secundario.nombre}", total_sec
                )
                log.info("Enriqueciendo desde: %s", secundario.nombre)
                stats_sec = _enriquecer_desde_secundario(
                    secundario, indice, mapa_join, contador, resultado
                )
                estadisticas.append(stats_sec)
            destino_label = (
                "Escribiendo a Postgres" if sink == "postgres" else "Escribiendo a CSV"
            )
            progreso.iniciar_fase(destino_label, len(indice))
            log.info("Escribiendo a sink...")
            filas_salida = _escribir_indice(fila_sink, indice, progreso)
            indice.clear()
            mapa_join.clear()
    finally:
        fila_sink.close()
        if conn is not None:
            conn.close()
        for archivo in archivos:
            _NOMBRES_REGISTRY.pop(archivo.archivo_id, None)
        progreso.terminar_fase()
        log.info("Sink cerrado")

    contador.flush()

    resultado.detalle_archivos = estadisticas
    resultado.total_filas = sum(e.total_filas for e in estadisticas)
    resultado.filas_validas = filas_salida
    resultado.filas_con_error = sum(e.filas_con_error for e in estadisticas)
    resultado.duplicados = sum(e.duplicados for e in estadisticas)
    resultado.sin_match = sum(e.sin_match for e in estadisticas)
    resultado.archivo_resultado = identificador
    resultado.filas_procesadas = contador.filas_procesadas


def _iter_chunks_archivo(
    archivo: ArchivoJob,
) -> Iterator[list[dict[str, Any]]]:
    ruta = Path(archivo.ruta)
    if not ruta.exists():
        raise ValueError(f"Archivo no encontrado en disco: {archivo.nombre}")

    nombres = _NOMBRES_REGISTRY.get(archivo.archivo_id)

    if es_tipo_delimitado(archivo.tipo):
        iterador = leer_archivo_chunks(
            ruta=ruta,
            tipo=archivo.tipo,
            delimitador=archivo.delimitador,
            codificacion=archivo.codificacion,
            tiene_encabezados=archivo.tiene_encabezados,
            chunksize=CHUNK_SIZE_DEFAULT,
            nombres_columnas=nombres,
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
        nombres_columnas=nombres,
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
    sink: FilaSink,
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
            sink.write(fila_destino)
            filas_validas += 1
        contador.sumar(len(filas))

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
        duplicados=0,
        sin_match=sin_match,
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
    sink: FilaSink,
    indice: dict[str, dict[str, str | None]],
    progress: ProgressTracker | None = None,
) -> int:
    total = 0
    for fila in indice.values():
        fusionada: dict[str, str | None] = {campo: None for campo in CAMPOS_ESTANDAR}
        fusionada.update(fila)
        sink.write(fusionada)
        total += 1
        if progress is not None:
            progress.avanzar(1)
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
