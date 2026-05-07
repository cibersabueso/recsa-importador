from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from tqdm import tqdm


@dataclass
class FaseRegistro:
    nombre: str
    total: int
    inicio: datetime
    fin: datetime
    duracion_segundos: float


class ProgressTracker:
    def __init__(
        self, total_estimado: int, descripcion: str = "Procesando"
    ) -> None:
        self.total_estimado: int = total_estimado
        self.descripcion: str = descripcion
        self.fases: list[FaseRegistro] = []
        self._barra: Any | None = None
        self._fase_actual: str | None = None
        self._fase_inicio: datetime | None = None
        self._fase_total: int = 0
        self._fase_avance: int = 0

    def iniciar_fase(self, nombre: str, total: int | None = None) -> None:
        if self._fase_actual is not None:
            self.terminar_fase()
        self._fase_actual = nombre
        self._fase_inicio = datetime.now()
        self._fase_total = int(total) if total is not None else 0
        self._fase_avance = 0
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

    def avanzar(self, n: int = 1) -> None:
        if n <= 0:
            return
        self._fase_avance += n
        if self._barra is not None:
            self._barra.update(n)

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
                total=self._fase_avance or self._fase_total,
                inicio=inicio,
                fin=fin,
                duracion_segundos=duracion,
            )
        )
        if self._barra is not None:
            try:
                self._barra.close()
            except Exception:  # noqa: BLE001
                pass
            self._barra = None
        self._fase_actual = None
        self._fase_inicio = None
        self._fase_total = 0
        self._fase_avance = 0

    def cerrar(self) -> None:
        if self._fase_actual is not None:
            self.terminar_fase()


class _NoOpProgress:
    fases: list[FaseRegistro] = []

    def iniciar_fase(self, nombre: str, total: int | None = None) -> None:
        return None

    def avanzar(self, n: int = 1) -> None:
        return None

    def terminar_fase(self) -> None:
        return None

    def cerrar(self) -> None:
        return None


NO_OP_PROGRESS: _NoOpProgress = _NoOpProgress()
