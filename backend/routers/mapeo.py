from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from models.mapeo import MapeoConfig, MapeoResponse
from services.file_service import obtener_archivo
from services.mapeo_service import guardar_mapeo

router = APIRouter(prefix="/api", tags=["mapeo"])


@router.post("/mapeo", response_model=MapeoResponse)
def configurar_mapeo(mapeo: MapeoConfig) -> MapeoResponse:
    if obtener_archivo(mapeo.archivo_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Archivo no encontrado: {mapeo.archivo_id}",
        )

    destinos = [col.destino for col in mapeo.columnas]
    if mapeo.columna_clave not in destinos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La columna clave '{mapeo.columna_clave}' no está mapeada",
        )

    guardar_mapeo(mapeo)
    return MapeoResponse(
        ok=True,
        archivo_id=mapeo.archivo_id,
        total_mapeadas=len(mapeo.columnas),
        obligatorias=sum(1 for c in mapeo.columnas if c.obligatorio),
    )
