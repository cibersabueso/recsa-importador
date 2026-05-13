from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from cli.layouts._loader import (
    Layout,
    cargar_layout,
    expandir_nombres,
    nombres_solo_join,
)
from models.config import ProcesoConfig
from models.job import ArchivoJob, JobPayload
from models.mapeo import ColumnaMapeo
from utils.file_parser import detectar_tipo

MAX_COLUMNAS_MAPEADAS: int = 200


def _construir_archivo(
    archivo_raw: dict[str, Any],
    layouts_cache: dict[str, Layout],
) -> tuple[ArchivoJob, list[str] | None]:
    layout_nombre = archivo_raw.get("layout")
    if not layout_nombre or not isinstance(layout_nombre, str):
        raise ValueError(f"Archivo sin 'layout': {archivo_raw}")
    if layout_nombre not in layouts_cache:
        layouts_cache[layout_nombre] = cargar_layout(layout_nombre)
    layout = layouts_cache[layout_nombre]

    ruta = archivo_raw.get("ruta")
    if not ruta or not isinstance(ruta, str):
        raise ValueError(f"Archivo con layout '{layout_nombre}' sin 'ruta'")
    nombre = Path(ruta).name
    tipo = detectar_tipo(nombre)

    orden_raw = archivo_raw.get("orden")
    if not isinstance(orden_raw, int) or orden_raw < 1:
        raise ValueError(f"Archivo '{nombre}': 'orden' debe ser un entero >= 1")

    columna_clave = archivo_raw.get("columna_clave")
    if not columna_clave or not isinstance(columna_clave, str):
        raise ValueError(f"Archivo '{nombre}': falta 'columna_clave'")
    columna_join = archivo_raw.get("columna_join")
    if columna_join is not None and not isinstance(columna_join, str):
        raise ValueError(f"Archivo '{nombre}': 'columna_join' debe ser string")

    mapeos_raw = archivo_raw.get("mapeos") or []
    if not isinstance(mapeos_raw, list):
        raise ValueError(f"Archivo '{nombre}': 'mapeos' debe ser una lista")
    columnas = [ColumnaMapeo.model_validate(col) for col in mapeos_raw]

    solo_join = nombres_solo_join(layout)
    columnas = [col for col in columnas if col.destino not in solo_join]

    nombres_columnas: list[str] | None = None
    if not layout.tiene_encabezados:
        nombres_columnas = expandir_nombres(layout)

    archivo = ArchivoJob(
        archivo_id=uuid.uuid4().hex,
        nombre=nombre,
        ruta=ruta,
        tipo=tipo,
        orden=orden_raw,
        delimitador=layout.delimitador,
        separador_decimal=layout.separador_decimal,
        codificacion=layout.codificacion,
        tiene_encabezados=layout.tiene_encabezados,
        columna_clave=columna_clave,
        columna_join=columna_join,
        columnas=columnas,
        layout=layout_nombre,
    )
    return archivo, nombres_columnas


def construir_payload(
    config: dict[str, Any],
) -> tuple[JobPayload, dict[str, list[str]], str | None]:
    proceso_raw = config.get("proceso")
    if not isinstance(proceso_raw, dict):
        raise ValueError("Falta sección 'proceso' en la config")
    archivos_raw = config.get("archivos")
    if not isinstance(archivos_raw, list) or not archivos_raw:
        raise ValueError("Falta sección 'archivos' o está vacía")

    proceso = ProcesoConfig.model_validate(proceso_raw)
    grupo_prueba_raw = proceso_raw.get("grupo_prueba")
    grupo_prueba = (
        str(grupo_prueba_raw) if isinstance(grupo_prueba_raw, str) else None
    )

    layouts_cache: dict[str, Layout] = {}
    archivos: list[ArchivoJob] = []
    nombres_por_archivo: dict[str, list[str]] = {}
    total_mapeos = 0
    for archivo_raw in archivos_raw:
        if not isinstance(archivo_raw, dict):
            raise ValueError("Cada archivo debe ser un mapping")
        archivo, nombres = _construir_archivo(archivo_raw, layouts_cache)
        archivos.append(archivo)
        total_mapeos += len(archivo.columnas)
        if nombres:
            nombres_por_archivo[archivo.archivo_id] = nombres
    if total_mapeos > MAX_COLUMNAS_MAPEADAS:
        raise ValueError(
            f"Límite de columnas excedido: {total_mapeos} > {MAX_COLUMNAS_MAPEADAS}"
        )
    payload = JobPayload(proceso=proceso, archivos=archivos)
    return payload, nombres_por_archivo, grupo_prueba
