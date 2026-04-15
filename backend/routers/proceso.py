from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from models.resultado import JobResponse, ResultadoProceso
from services.proceso_service import ejecutar_proceso, obtener_resultado

router = APIRouter(prefix="/api", tags=["proceso"])


@router.post("/procesar", response_model=JobResponse)
def procesar() -> JobResponse:
    try:
        resultado = ejecutar_proceso()
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    return JobResponse(job_id=resultado.job_id, estado=resultado.estado)


@router.get("/resultado/{job_id}", response_model=ResultadoProceso)
def resultado(job_id: str) -> ResultadoProceso:
    resultado_proceso = obtener_resultado(job_id)
    if resultado_proceso is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job no encontrado: {job_id}",
        )
    return resultado_proceso
