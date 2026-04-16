from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from models.config import Codificacion, Delimitador, ProcesoConfig, SeparadorDecimal
from models.mapeo import ColumnaMapeo
from models.resultado import ResultadoProceso

EstadoJob = Literal["pending", "processing", "completed", "error"]
TipoOrigen = Literal["sftp", "correo", "teams"]


class OrigenConfig(BaseModel):
    tipo: TipoOrigen
    host: str | None = None
    puerto: int | None = None
    usuario: str | None = None
    password: str | None = None
    ruta: str | None = None
    direccion: str | None = None
    carpeta: str | None = None
    equipo: str | None = None
    canal: str | None = None


class ArchivoJob(BaseModel):
    archivo_id: str
    nombre: str
    ruta: str = ""
    tipo: str
    orden: int = Field(ge=1)
    delimitador: Delimitador
    separador_decimal: SeparadorDecimal
    codificacion: Codificacion
    tiene_encabezados: bool
    columna_clave: str
    columnas: list[ColumnaMapeo]


class JobPayload(BaseModel):
    proceso: ProcesoConfig
    archivos: list[ArchivoJob]
    origen: OrigenConfig | None = None


class Job(BaseModel):
    id: str
    status: EstadoJob
    payload: JobPayload
    resultado: ResultadoProceso | None = None
    created_at: str
    updated_at: str


class EnqueueResponse(BaseModel):
    job_id: str
    status: EstadoJob


class JobResumen(BaseModel):
    id: str
    status: EstadoJob
    empresa: str
    tipo_carga: str
    responsable: str
    total_archivos: int
    created_at: str
    updated_at: str
