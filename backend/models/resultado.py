from typing import Literal

from pydantic import BaseModel

EstadoJob = Literal["pendiente", "procesando", "completado", "error"]


class EstadisticasArchivo(BaseModel):
    archivo_id: str
    nombre: str
    orden: int
    total_filas: int
    filas_validas: int
    filas_con_error: int
    duplicados: int
    separador: str
    columna_clave: str


class ResultadoProceso(BaseModel):
    job_id: str
    estado: EstadoJob
    total_filas: int = 0
    filas_validas: int = 0
    filas_con_error: int = 0
    duplicados: int = 0
    detalle_archivos: list[EstadisticasArchivo] = []
    errores: list[str] = []
    archivo_resultado: str | None = None


class JobResponse(BaseModel):
    job_id: str
    estado: EstadoJob
