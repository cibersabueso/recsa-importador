from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, BaseModel, Field

from models.camel_base import CamelModel

Delimitador = Literal[";", ",", "|", "\t"]
SeparadorDecimal = Literal[",", "."]
Codificacion = Literal["UTF-8", "Latin1", "Windows-1252"]


class ProcesoConfig(CamelModel):
    empresa: str
    tipo_carga: str
    tipo_proceso: str
    nombre_interfaz: str
    responsable: str


class ArchivoConfig(CamelModel):
    archivo_id: str = Field(
        validation_alias=AliasChoices("archivo_id", "archivoId", "id"),
    )
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
