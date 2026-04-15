from __future__ import annotations

import uuid
from pathlib import Path
from threading import Lock

from fastapi import UploadFile

from models.archivo import ArchivoMetadata
from utils.file_parser import detectar_codificacion, detectar_delimitador, detectar_tipo

UPLOAD_DIR = Path("/tmp/recsa_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_archivos: dict[str, ArchivoMetadata] = {}
_lock = Lock()


async def guardar_archivo(archivo: UploadFile) -> ArchivoMetadata:
    nombre_original = archivo.filename or "archivo"
    tipo = detectar_tipo(nombre_original)
    archivo_id = uuid.uuid4().hex
    destino = UPLOAD_DIR / f"{archivo_id}_{Path(nombre_original).name}"
    contenido = await archivo.read()
    destino.write_bytes(contenido)

    codificacion: str | None = None
    delimitador: str | None = None
    if tipo in {"csv", "txt"}:
        codificacion = detectar_codificacion(destino)
        delimitador = detectar_delimitador(destino, codificacion)
    elif tipo in {"json", "xml"}:
        codificacion = detectar_codificacion(destino)

    metadata = ArchivoMetadata(
        archivo_id=archivo_id,
        nombre=nombre_original,
        tipo=tipo,
        tamano=len(contenido),
        ruta=str(destino),
        codificacion_detectada=codificacion,
        delimitador_detectado=delimitador,
    )
    with _lock:
        _archivos[archivo_id] = metadata
    return metadata


def obtener_archivo(archivo_id: str) -> ArchivoMetadata | None:
    with _lock:
        return _archivos.get(archivo_id)


def listar_archivos() -> list[ArchivoMetadata]:
    with _lock:
        return list(_archivos.values())
