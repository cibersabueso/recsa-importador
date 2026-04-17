from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field

from models.camel_base import CamelModel


class ColumnaMapeo(CamelModel):
    origen: str
    destino: str | None = None
    obligatorio: bool = False


class MapeoConfig(CamelModel):
    archivo_id: str = Field(
        validation_alias=AliasChoices("archivo_id", "archivoId"),
    )
    columna_clave: str | None = None
    columna_join: str | None = None
    columnas: list[ColumnaMapeo] = Field(
        default_factory=list,
        validation_alias=AliasChoices("columnas", "mapeos"),
    )


class MapeoResponse(BaseModel):
    ok: bool
    archivo_id: str
    total_mapeadas: int
    obligatorias: int


class MapeoLoteResponse(BaseModel):
    ok: bool
    total_archivos: int
    total_mapeadas: int
