from typing import Literal

from pydantic import BaseModel

TipoArchivo = Literal["csv", "txt", "xlsx", "xml", "json"]


class ArchivoMetadata(BaseModel):
    archivo_id: str
    nombre: str
    tipo: TipoArchivo
    tamano: int
    ruta: str
    codificacion_detectada: str | None = None
    delimitador_detectado: str | None = None


class UploadResponse(BaseModel):
    archivos: list[ArchivoMetadata]
