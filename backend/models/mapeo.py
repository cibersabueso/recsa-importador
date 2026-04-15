from pydantic import BaseModel


class ColumnaMapeo(BaseModel):
    origen: str
    destino: str
    obligatorio: bool


class MapeoConfig(BaseModel):
    archivo_id: str
    columna_clave: str
    columnas: list[ColumnaMapeo]


class MapeoResponse(BaseModel):
    ok: bool
    archivo_id: str
    total_mapeadas: int
    obligatorias: int
