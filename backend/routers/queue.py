from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from models.job import EnqueueResponse, Job, JobPayload, JobResumen
from services import queue_service

router = APIRouter(prefix="/api/queue", tags=["queue"])


@router.post("/enqueue", response_model=EnqueueResponse)
def encolar(payload: JobPayload) -> EnqueueResponse:
    if not payload.archivos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El payload debe incluir al menos un archivo",
        )
    if not any(archivo.orden == 1 for archivo in payload.archivos):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe existir un archivo principal con orden 1",
        )
    job = queue_service.enqueue(payload)
    return EnqueueResponse(job_id=job.id, status=job.status)


@router.get("/status/{job_id}", response_model=Job)
def estado(job_id: str) -> Job:
    job = queue_service.obtener_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job no encontrado: {job_id}",
        )
    return job


@router.get("/jobs", response_model=list[JobResumen])
def listar() -> list[JobResumen]:
    return queue_service.listar_jobs()
