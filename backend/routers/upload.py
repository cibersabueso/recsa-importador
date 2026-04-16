from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from models.archivo import UploadResponse
from services.file_service import guardar_archivo

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload", response_model=UploadResponse, response_model_by_alias=True)
async def subir_archivos(archivos: list[UploadFile] = File(...)) -> UploadResponse:
    if not archivos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se recibieron archivos",
        )
    metadatos = []
    for archivo in archivos:
        try:
            metadata = await guardar_archivo(archivo)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error
        except Exception as error:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error guardando archivo: {error}",
            ) from error
        metadatos.append(metadata)
    return UploadResponse(archivos=metadatos)
