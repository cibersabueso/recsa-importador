from typing import Literal

from pydantic import BaseModel, Field

Delimitador = Literal[";", ",", "|", "\t"]
SeparadorDecimal = Literal[",", "."]
Codificacion = Literal["UTF-8", "Latin1", "Windows-1252"]


class ProcesoConfig(BaseModel):
    empresa: str
    tipo_carga: str
    tipo_proceso: str
    nombre_interfaz: str
    responsable: str


class ArchivoConfig(BaseModel):
    archivo_id: str
    orden: int = Field(ge=1)
    delimitador: Delimitador
    separador_decimal: SeparadorDecimal
    codificacion: Codificacion
    tiene_encabezados: bool


class ConfigResponse(BaseModel):
    ok: bool
    mensaje: str


class PreviewResponse(BaseModel):
    archivo_id: str
    columnas: list[str]
    filas: list[dict[str, str | None]]
    total_columnas: int
