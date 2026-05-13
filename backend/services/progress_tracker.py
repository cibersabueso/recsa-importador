from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from tqdm import tqdm

from services import queue_service

PROGRESS_KEY_PREFIX: str = "recsa:progress:"
PROGRESS_TTL_SECONDS: int = 3600
PUBLISH_FILAS_INTERVAL: int = 1000
PUBLISH_TIME_INTERVAL_SECONDS: float = 1.0

logger = logging.getLogger("recsa.progress")


def progress_key(job_id: str) -> str:
    return f"{PROGRESS_KEY_PREFIX}{job_id}"


@dataclass
class FaseRegistro:
    nombre: str
    total: int
    inicio: datetime
    fin: datetime
    duracion_segundos: float


class ProgressTracker:
    def __init__(
        self,
        total_estimado: int,
        descripcion: str = "Procesando",
        job_id: str | None = None,
        fase_total: int | None = None,
    ) -> None:
        self.total_estimado: int = total_estimado
        self.descripcion: str = descripcion
        self.fases: list[FaseRegistro] = []
        self.job_id: str | None = job_id
        self.fase_total: int = int(fase_total) if fase_total is not None else 0
        self._barra: Any | None = None
        self._fase_actual: str | None = None
        self._fase_inicio: datetime | None = None
        self._fase_inicio_mono: float = 0.0
        self._fase_total_filas: int = 0
        self._fase_avance: int = 0
        self._fase_indice: int = 0
        self._ultima_publicacion_filas: int = 0
        self._ultima_publicacion_mono: float = 0.0

    def iniciar_fase(self, nombre: str, total: int | None = None) -> None:
        if self._fase_actual is not None:
            self.terminar_fase()
        self._fase_actual = nombre
        self._fase_inicio = datetime.now()
        self._fase_inicio_mono = time.monotonic()
        self._fase_total_filas = int(total) if total is not None else 0
        self._fase_avance = 0
        self._fase_indice += 1
        if self.fase_total > 0 and self._fase_indice > self.fase_total:
            self.fase_total = self._fase_indice
        self._barra = tqdm(
            total=total,
            desc=nombre,
            unit=" filas",
            unit_scale=True,
            dynamic_ncols=True,
            leave=True,
            mininterval=0.5,
            file=sys.stderr,
            ascii=True,
        )
        self._ultima_publicacion_filas = 0
        self._ultima_publicacion_mono = 0.0
        self._publicar_progreso(forzar=True)

    def avanzar(self, n: int = 1) -> None:
        if n <= 0:
            return
        self._fase_avance += n
        if self._barra is not None:
            self._barra.update(n)
        self._maybe_publicar()

    def terminar_fase(self) -> None:
        if self._fase_actual is None:
            return
        nombre = self._fase_actual
        inicio = self._fase_inicio if self._fase_inicio is not None else datetime.now()
        fin = datetime.now()
        duracion = (fin - inicio).total_seconds()
        self.fases.append(
            FaseRegistro(
                nombre=nombre,
                total=self._fase_avance or self._fase_total_filas,
                inicio=inicio,
                fin=fin,
                duracion_segundos=duracion,
            )
        )
        self._publicar_progreso(forzar=True)
        if self._barra is not None:
            try:
                self._barra.close()
            except Exception:  # noqa: BLE001
                pass
            self._barra = None
        self._fase_actual = None
        self._fase_inicio = None
        self._fase_inicio_mono = 0.0
        self._fase_total_filas = 0
        self._fase_avance = 0

    def cerrar(self) -> None:
        if self._fase_actual is not None:
            self.terminar_fase()

    def _maybe_publicar(self) -> None:
        if self.job_id is None:
            return
        ahora = time.monotonic()
        delta_filas = self._fase_avance - self._ultima_publicacion_filas
        delta_tiempo = ahora - self._ultima_publicacion_mono
        if (
            delta_filas >= PUBLISH_FILAS_INTERVAL
            or delta_tiempo >= PUBLISH_TIME_INTERVAL_SECONDS
        ):
            self._publicar_progreso(forzar=False, ahora_mono=ahora)

    def _publicar_progreso(
        self, forzar: bool = False, ahora_mono: float | None = None
    ) -> None:
        if self.job_id is None:
            return
        if self._fase_actual is None:
            return
        if ahora_mono is None:
            ahora_mono = time.monotonic()
        transcurrido = max(0.0, ahora_mono - self._fase_inicio_mono)
        if self._fase_total_filas > 0:
            porcentaje = (self._fase_avance / self._fase_total_filas) * 100.0
            porcentaje = max(0.0, min(100.0, porcentaje))
        else:
            porcentaje = 0.0
        if transcurrido > 0:
            velocidad = int(self._fase_avance / transcurrido)
        else:
            velocidad = 0
        ahora_iso = datetime.now(timezone.utc).isoformat()
        inicio_iso = (
            self._fase_inicio.isoformat()
            if self._fase_inicio is not None
            else ahora_iso
        )
        fase_total = self.fase_total if self.fase_total > 0 else self._fase_indice
        mapping: dict[str, Any] = {
            "job_id": self.job_id,
            "fase_actual": self._fase_actual,
            "fase_indice": self._fase_indice,
            "fase_total": fase_total,
            "filas_procesadas": self._fase_avance,
            "filas_totales": self._fase_total_filas,
            "porcentaje": round(porcentaje, 2),
            "velocidad_filas_seg": velocidad,
            "inicio_fase": inicio_iso,
            "updated_at": ahora_iso,
        }
        try:
            cliente = queue_service._cliente()
            clave = progress_key(self.job_id)
            pipe = cliente.pipeline()
            pipe.hset(clave, mapping={k: str(v) for k, v in mapping.items()})
            pipe.expire(clave, PROGRESS_TTL_SECONDS)
            pipe.execute()
        except Exception as error:  # noqa: BLE001
            if forzar:
                logger.warning(
                    "No se pudo publicar progreso del job %s: %s",
                    self.job_id,
                    error,
                )
            return
        self._ultima_publicacion_filas = self._fase_avance
        self._ultima_publicacion_mono = ahora_mono


class _NoOpProgress:
    fases: list[FaseRegistro] = []
    job_id: str | None = None
    fase_total: int = 0

    def iniciar_fase(self, nombre: str, total: int | None = None) -> None:
        return None

    def avanzar(self, n: int = 1) -> None:
        return None

    def terminar_fase(self) -> None:
        return None

    def cerrar(self) -> None:
        return None


NO_OP_PROGRESS: _NoOpProgress = _NoOpProgress()
