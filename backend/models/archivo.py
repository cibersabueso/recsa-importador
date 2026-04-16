from typing import Literal

from models.camel_base import CamelModel

TipoArchivo = Literal["csv", "txt", "xlsx", "xml", "json"]


class ArchivoMetadata(CamelModel):
    archivo_id: str
    nombre: str
    tipo: TipoArchivo
    tamano: int
    ruta: str
    codificacion_detectada: str | None = None
    delimitador_detectado: str | None = None


class UploadResponse(CamelModel):
    archivos: list[ArchivoMetadata]
