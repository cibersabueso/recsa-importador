from __future__ import annotations

from fastapi import APIRouter

from models.mapeo import MapeoConfig, MapeoLoteResponse
from services.mapeo_service import guardar_mapeo

router = APIRouter(prefix="/api", tags=["mapeo"])


@router.post("/mapeo", response_model=MapeoLoteResponse)
def configurar_mapeo(mapeos: list[MapeoConfig]) -> MapeoLoteResponse:
    total_mapeadas = 0
    for mapeo in mapeos:
        guardar_mapeo(mapeo)
        total_mapeadas += len(mapeo.columnas)
    return MapeoLoteResponse(
        ok=True,
        total_archivos=len(mapeos),
        total_mapeadas=total_mapeadas,
    )
