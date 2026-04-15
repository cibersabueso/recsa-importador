from __future__ import annotations

import csv
import uuid
from pathlib import Path
from threading import Lock
from typing import Any

from models.config import ArchivoConfig
from models.mapeo import MapeoConfig
from models.resultado import EstadisticasArchivo, ResultadoProceso
from services.config_service import listar_archivo_configs, obtener_archivo_config
from services.file_service import UPLOAD_DIR, obtener_archivo
from services.mapeo_service import obtener_mapeo
from utils.file_parser import leer_archivo
from utils.validators import CAMPOS_ESTANDAR, normalizar_decimal, validar_fila

RESULTADOS_DIR = UPLOAD_DIR / "resultados"
RESULTADOS_DIR.mkdir(parents=True, exist_ok=True)

_jobs: dict[str, ResultadoProceso] = {}
_lock = Lock()


def ejecutar_proceso() -> ResultadoProceso:
    job_id = uuid.uuid4().hex
    resultado = ResultadoProceso(job_id=job_id, estado="procesando")
    with _lock:
        _jobs[job_id] = resultado

    try:
        _procesar(resultado)
        resultado.estado = "completado"
    except Exception as error:  # noqa: BLE001
        resultado.estado = "error"
        resultado.errores.append(str(error))

    with _lock:
        _jobs[job_id] = resultado
    return resultado


def obtener_resultado(job_id: str) -> ResultadoProceso | None:
    with _lock:
        return _jobs.get(job_id)


def _procesar(resultado: ResultadoProceso) -> None:
    configs = listar_archivo_configs()
    if not configs:
        raise ValueError("No hay archivos configurados")

    principal = next((c for c in configs if c.orden == 1), None)
    if principal is None:
        raise ValueError("Falta archivo principal (orden 1)")

    datos_por_archivo: dict[str, dict[str, dict[str, str | None]]] = {}
    estadisticas_por_archivo: dict[str, EstadisticasArchivo] = {}

    for config in configs:
        estadistica, datos_indexados = _procesar_archivo(config)
        estadisticas_por_archivo[config.archivo_id] = estadistica
        datos_por_archivo[config.archivo_id] = datos_indexados

    datos_principal = datos_por_archivo[principal.archivo_id]
    filas_resultado: list[dict[str, str | None]] = []

    for clave, fila_principal in datos_principal.items():
        fusionada: dict[str, str | None] = {campo: None for campo in CAMPOS_ESTANDAR}
        fusionada.update(fila_principal)
        for config in configs:
            if config.archivo_id == principal.archivo_id:
                continue
            fila_secundaria = datos_por_archivo[config.archivo_id].get(clave)
            if fila_secundaria is None:
                continue
            for campo, valor in fila_secundaria.items():
                if valor is not None and fusionada.get(campo) in (None, ""):
                    fusionada[campo] = valor
        filas_resultado.append(fusionada)

    archivo_salida = RESULTADOS_DIR / f"{resultado.job_id}.csv"
    _escribir_resultado(archivo_salida, filas_resultado)

    resultado.detalle_archivos = list(estadisticas_por_archivo.values())
    resultado.total_filas = sum(e.total_filas for e in resultado.detalle_archivos)
    resultado.filas_validas = len(filas_resultado)
    resultado.filas_con_error = sum(e.filas_con_error for e in resultado.detalle_archivos)
    resultado.duplicados = sum(e.duplicados for e in resultado.detalle_archivos)
    resultado.archivo_resultado = str(archivo_salida)


def _procesar_archivo(
    config: ArchivoConfig,
) -> tuple[EstadisticasArchivo, dict[str, dict[str, str | None]]]:
    metadata = obtener_archivo(config.archivo_id)
    if metadata is None:
        raise ValueError(f"Archivo no encontrado: {config.archivo_id}")

    mapeo = obtener_mapeo(config.archivo_id)
    if mapeo is None:
        raise ValueError(f"Mapeo no definido para archivo: {metadata.nombre}")

    _, filas = leer_archivo(
        ruta=Path(metadata.ruta),
        tipo=metadata.tipo,
        delimitador=config.delimitador,
        codificacion=config.codificacion,
        tiene_encabezados=config.tiene_encabezados,
    )

    columnas_obligatorias_destino = [col.destino for col in mapeo.columnas if col.obligatorio]
    columnas_clave_origen = next(
        (col.origen for col in mapeo.columnas if col.destino == mapeo.columna_clave),
        mapeo.columna_clave,
    )

    datos_indexados: dict[str, dict[str, str | None]] = {}
    filas_validas = 0
    filas_con_error = 0
    duplicados = 0

    for fila_origen in filas:
        fila_destino = _aplicar_mapeo(fila_origen, mapeo, config.separador_decimal)
        es_valida, _ = validar_fila(fila_destino, columnas_obligatorias_destino)
        if not es_valida:
            filas_con_error += 1
            continue
        clave = fila_origen.get(columnas_clave_origen)
        if clave is None or str(clave).strip() == "":
            filas_con_error += 1
            continue
        clave_str = str(clave).strip()
        if clave_str in datos_indexados:
            duplicados += 1
            continue
        datos_indexados[clave_str] = fila_destino
        filas_validas += 1

    estadistica = EstadisticasArchivo(
        archivo_id=config.archivo_id,
        nombre=metadata.nombre,
        orden=config.orden,
        total_filas=len(filas),
        filas_validas=filas_validas,
        filas_con_error=filas_con_error,
        duplicados=duplicados,
        separador=config.delimitador,
        columna_clave=mapeo.columna_clave,
    )
    return estadistica, datos_indexados


def _aplicar_mapeo(
    fila_origen: dict[str, Any],
    mapeo: MapeoConfig,
    separador_decimal: str,
) -> dict[str, str | None]:
    fila_destino: dict[str, str | None] = {campo: None for campo in CAMPOS_ESTANDAR}
    for columna in mapeo.columnas:
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
