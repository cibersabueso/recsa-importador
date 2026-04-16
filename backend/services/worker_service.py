from __future__ import annotations

import csv
import logging
import threading
import time
from pathlib import Path
from typing import Any

from models.job import ArchivoJob, Job, JobPayload
from models.mapeo import ColumnaMapeo
from models.resultado import EstadisticasArchivo, ResultadoProceso
from services import queue_service
from services.file_service import UPLOAD_DIR
from utils.file_parser import leer_archivo
from utils.validators import CAMPOS_ESTANDAR, normalizar_decimal, validar_fila

RESULTADOS_DIR = UPLOAD_DIR / "resultados"
RESULTADOS_DIR.mkdir(parents=True, exist_ok=True)

POLL_INTERVAL_SECONDS = 2.0

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
        queue_service.update_status(job.id, "completed", resultado)
    except Exception as error:  # noqa: BLE001
        resultado.estado = "error"
        resultado.errores.append(str(error))
        queue_service.update_status(job.id, "error", resultado)


def _ejecutar(payload: JobPayload, resultado: ResultadoProceso) -> None:
    archivos = payload.archivos
    if not archivos:
        raise ValueError("El job no incluye archivos")

    principal = next((a for a in archivos if a.orden == 1), None)
    if principal is None:
        raise ValueError("Falta archivo principal (orden 1)")

    datos_por_archivo: dict[str, dict[str, dict[str, str | None]]] = {}
    estadisticas: list[EstadisticasArchivo] = []

    for archivo in archivos:
        estadistica, indexados = _procesar_archivo(archivo)
        estadisticas.append(estadistica)
        datos_por_archivo[archivo.archivo_id] = indexados

    datos_principal = datos_por_archivo[principal.archivo_id]
    filas_resultado: list[dict[str, str | None]] = []
    for clave, fila_principal in datos_principal.items():
        fusionada: dict[str, str | None] = {campo: None for campo in CAMPOS_ESTANDAR}
        fusionada.update(fila_principal)
        for archivo in archivos:
            if archivo.archivo_id == principal.archivo_id:
                continue
            fila_secundaria = datos_por_archivo[archivo.archivo_id].get(clave)
            if fila_secundaria is None:
                continue
            for campo, valor in fila_secundaria.items():
                if valor is not None and fusionada.get(campo) in (None, ""):
                    fusionada[campo] = valor
        filas_resultado.append(fusionada)

    archivo_salida = RESULTADOS_DIR / f"{resultado.job_id}.csv"
    _escribir_resultado(archivo_salida, filas_resultado)

    resultado.detalle_archivos = estadisticas
    resultado.total_filas = sum(e.total_filas for e in estadisticas)
    resultado.filas_validas = len(filas_resultado)
    resultado.filas_con_error = sum(e.filas_con_error for e in estadisticas)
    resultado.duplicados = sum(e.duplicados for e in estadisticas)
    resultado.archivo_resultado = str(archivo_salida)


def _procesar_archivo(
    archivo: ArchivoJob,
) -> tuple[EstadisticasArchivo, dict[str, dict[str, str | None]]]:
    ruta = Path(archivo.ruta)
    if not ruta.exists():
        raise ValueError(f"Archivo no encontrado en disco: {archivo.nombre}")

    _, filas = leer_archivo(
        ruta=ruta,
        tipo=archivo.tipo,
        delimitador=archivo.delimitador,
        codificacion=archivo.codificacion,
        tiene_encabezados=archivo.tiene_encabezados,
    )

    obligatorios_destino = [
        col.destino
        for col in archivo.columnas
        if col.obligatorio and col.destino is not None
    ]
    columna_clave_origen = next(
        (col.origen for col in archivo.columnas if col.destino == archivo.columna_clave),
        archivo.columna_clave,
    )

    indexados: dict[str, dict[str, str | None]] = {}
    filas_validas = 0
    filas_con_error = 0
    duplicados = 0

    for fila_origen in filas:
        fila_destino = _aplicar_mapeo(
            fila_origen, archivo.columnas, archivo.separador_decimal
        )
        es_valida, _ = validar_fila(fila_destino, obligatorios_destino)
        if not es_valida:
            filas_con_error += 1
            continue
        clave = fila_origen.get(columna_clave_origen)
        if clave is None or str(clave).strip() == "":
            filas_con_error += 1
            continue
        clave_str = str(clave).strip()
        if clave_str in indexados:
            duplicados += 1
            continue
        indexados[clave_str] = fila_destino
        filas_validas += 1

    estadistica = EstadisticasArchivo(
        archivo_id=archivo.archivo_id,
        nombre=archivo.nombre,
        orden=archivo.orden,
        total_filas=len(filas),
        filas_validas=filas_validas,
        filas_con_error=filas_con_error,
        duplicados=duplicados,
        separador=archivo.delimitador,
        columna_clave=archivo.columna_clave,
    )
    return estadistica, indexados


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


def _escribir_resultado(ruta: Path, filas: list[dict[str, str | None]]) -> None:
    with ruta.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CAMPOS_ESTANDAR, delimiter=";")
        writer.writeheader()
        for fila in filas:
            writer.writerow({campo: fila.get(campo) or "" for campo in CAMPOS_ESTANDAR})
