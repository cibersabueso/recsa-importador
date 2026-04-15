from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from models.config import (
    ArchivoConfig,
    ConfigResponse,
    PreviewResponse,
    ProcesoConfig,
)
from services.config_service import (
    guardar_archivo_config,
    guardar_proceso,
    obtener_archivo_config,
)
from services.file_service import obtener_archivo
from utils.file_parser import leer_archivo

router = APIRouter(prefix="/api/config", tags=["config"])
preview_router = APIRouter(prefix="/api", tags=["preview"])


@router.post("/proceso", response_model=ConfigResponse)
def configurar_proceso(config: ProcesoConfig) -> ConfigResponse:
    guardar_proceso(config)
    return ConfigResponse(ok=True, mensaje="Configuración de proceso guardada")


@router.post("/archivo", response_model=ConfigResponse)
def configurar_archivo(config: ArchivoConfig) -> ConfigResponse:
    metadata = obtener_archivo(config.archivo_id)
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Archivo no encontrado: {config.archivo_id}",
        )
    guardar_archivo_config(config)
    return ConfigResponse(
        ok=True,
        mensaje=f"Configuración guardada para archivo {metadata.nombre}",
    )


@preview_router.get("/preview/{archivo_id}", response_model=PreviewResponse)
def vista_previa(archivo_id: str) -> PreviewResponse:
    metadata = obtener_archivo(archivo_id)
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Archivo no encontrado: {archivo_id}",
        )

    config = obtener_archivo_config(archivo_id)
    delimitador = config.delimitador if config else (metadata.delimitador_detectado or ",")
    codificacion = config.codificacion if config else (metadata.codificacion_detectada or "UTF-8")
    tiene_encabezados = config.tiene_encabezados if config else True

    try:
        columnas, filas = leer_archivo(
            ruta=Path(metadata.ruta),
            tipo=metadata.tipo,
            delimitador=delimitador,
            codificacion=codificacion,
            tiene_encabezados=tiene_encabezados,
        )
    except Exception as error:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error leyendo archivo: {error}",
        ) from error

    return PreviewResponse(
        archivo_id=archivo_id,
        columnas=columnas,
        filas=filas[:3],
        total_columnas=len(columnas),
    )
