from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, status

from models.camel_base import CamelModel
from models.config import Codificacion, Delimitador, ProcesoConfig, SeparadorDecimal
from models.job import ArchivoJob, JobPayload
from models.mapeo import ColumnaMapeo
from services import queue_service
from services.file_service import obtener_archivo

router = APIRouter(prefix="/api", tags=["proceso"])

EstadoFrontend = Literal["pendiente", "en_proceso", "completado", "error"]

_ESTADO_DB_A_FRONTEND: dict[str, EstadoFrontend] = {
    "pending": "pendiente",
    "processing": "en_proceso",
    "completed": "completado",
    "error": "error",
}


class ArchivoProcesarRequest(CamelModel):
    id: str
    nombre: str
    tipo: str
    orden: int = 1
    delimitador: Delimitador = ","
    separador_decimal: SeparadorDecimal = "."
    codificacion: Codificacion = "UTF-8"
    tiene_encabezados: bool = True
    columna_clave: str | None = None
    ruta: str = ""
    archivo_id_servidor: str | None = None


class MapeoProcesarRequest(CamelModel):
    archivo_id: str
    columna_clave: str | None = None
    mapeos: list[ColumnaMapeo] = []


class ProcesarRequest(CamelModel):
    proceso: ProcesoConfig
    archivos: list[ArchivoProcesarRequest]
    mapeos: list[MapeoProcesarRequest] = []


@router.post("/procesar")
def procesar(request: ProcesarRequest) -> dict[str, object]:
    if not request.archivos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe incluir al menos un archivo",
        )

    mapeo_por_archivo = {m.archivo_id: m for m in request.mapeos}
    archivos_job: list[ArchivoJob] = []

    for archivo in request.archivos:
        mapeo = mapeo_por_archivo.get(archivo.id)
        columnas_mapeo = (
            [c for c in mapeo.mapeos if c.destino is not None] if mapeo else []
        )
        columna_clave = (
            (mapeo.columna_clave if mapeo else None)
            or archivo.columna_clave
            or ""
        )
        ruta = archivo.ruta
        if not ruta:
            id_lookup = archivo.archivo_id_servidor or archivo.id
            metadata = obtener_archivo(id_lookup)
            ruta = metadata.ruta if metadata is not None else ""
        if not ruta:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Falta ruta del archivo '{archivo.nombre}'. "
                    "Suba el archivo vía POST /api/upload antes de procesar."
                ),
            )
        archivos_job.append(
            ArchivoJob(
                archivo_id=archivo.id,
                nombre=archivo.nombre,
                ruta=ruta,
                tipo=archivo.tipo,
                orden=archivo.orden,
                delimitador=archivo.delimitador,
                separador_decimal=archivo.separador_decimal,
                codificacion=archivo.codificacion,
                tiene_encabezados=archivo.tiene_encabezados,
                columna_clave=columna_clave,
                columnas=columnas_mapeo,
            )
        )

    if not any(a.orden == 1 for a in archivos_job):
        archivos_job[0].orden = 1

    payload = JobPayload(proceso=request.proceso, archivos=archivos_job)
    job = queue_service.enqueue(payload)

    return {
        "jobId": job.id,
        "estado": _ESTADO_DB_A_FRONTEND.get(job.status, "pendiente"),
        "filasValidas": 0,
        "filasConError": 0,
        "duplicados": 0,
        "archivos": [
            {
                "archivoId": a.archivo_id,
                "nombre": a.nombre,
                "filasValidas": 0,
                "filasConError": 0,
                "duplicados": 0,
            }
            for a in archivos_job
        ],
    }


@router.get("/resultado/{job_id}")
def resultado(job_id: str) -> dict[str, object]:
    job = queue_service.obtener_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job no encontrado: {job_id}",
        )

    resultado_job = job.resultado
    estado = _ESTADO_DB_A_FRONTEND.get(job.status, "pendiente")

    if resultado_job is None:
        return {
            "jobId": job.id,
            "estado": estado,
            "filasValidas": 0,
            "filasConError": 0,
            "duplicados": 0,
            "archivos": [],
        }

    return {
        "jobId": job.id,
        "estado": estado,
        "filasValidas": resultado_job.filas_validas,
        "filasConError": resultado_job.filas_con_error,
        "duplicados": resultado_job.duplicados,
        "archivos": [
            {
                "archivoId": det.archivo_id,
                "nombre": det.nombre,
                "filasValidas": det.filas_validas,
                "filasConError": det.filas_con_error,
                "duplicados": det.duplicados,
            }
            for det in resultado_job.detalle_archivos
        ],
        "archivoResultado": (
            Path(resultado_job.archivo_resultado).name
            if resultado_job.archivo_resultado
            else None
        ),
    }
