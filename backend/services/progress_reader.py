from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from services import queue_service
from services.progress_tracker import progress_key

logger = logging.getLogger("recsa.progress_reader")


def _parse_int(valor: Any, default: int = 0) -> int:
    if valor is None:
        return default
    try:
        return int(float(str(valor)))
    except (TypeError, ValueError):
        return default


def _parse_float(valor: Any, default: float = 0.0) -> float:
    if valor is None:
        return default
    try:
        return float(str(valor))
    except (TypeError, ValueError):
        return default


def _parse_dt(valor: Any) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor))
    except ValueError:
        return None


def leer_progreso(job_id: str) -> dict[str, Any] | None:
    try:
        cliente = queue_service._cliente()
    except Exception as error:  # noqa: BLE001
        logger.warning("No se pudo obtener cliente Redis: %s", error)
        return None
    try:
        datos = cliente.hgetall(progress_key(job_id))
    except Exception as error:  # noqa: BLE001
        logger.warning("No se pudo leer progreso del job %s: %s", job_id, error)
        return None
    if not datos:
        return None

    fase_indice = _parse_int(datos.get("fase_indice"))
    fase_total = _parse_int(datos.get("fase_total"))
    filas_procesadas = _parse_int(datos.get("filas_procesadas"))
    filas_totales = _parse_int(datos.get("filas_totales"))
    porcentaje_fase = _parse_float(datos.get("porcentaje"))
    velocidad = _parse_int(datos.get("velocidad_filas_seg"))
    inicio_fase = _parse_dt(datos.get("inicio_fase"))
    updated_at = _parse_dt(datos.get("updated_at"))

    transcurrido_seg = 0
    if inicio_fase is not None:
        ahora = datetime.now(inicio_fase.tzinfo or timezone.utc)
        transcurrido_seg = max(0, int((ahora - inicio_fase).total_seconds()))

    restante_seg: int | None = None
    if velocidad > 0 and filas_totales > filas_procesadas:
        restante_seg = max(0, int((filas_totales - filas_procesadas) / velocidad))

    return {
        "job_id": str(datos.get("job_id") or job_id),
        "fase_actual": str(datos.get("fase_actual") or ""),
        "fase_indice": fase_indice,
        "fase_total": fase_total,
        "filas_procesadas": filas_procesadas,
        "filas_totales": filas_totales,
        "porcentaje_fase": porcentaje_fase,
        "velocidad_filas_seg": velocidad,
        "inicio_fase": inicio_fase.isoformat() if inicio_fase is not None else None,
        "updated_at": updated_at.isoformat() if updated_at is not None else None,
        "tiempo_transcurrido_seg": transcurrido_seg,
        "tiempo_estimado_restante_seg": restante_seg,
    }
