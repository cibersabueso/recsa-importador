from __future__ import annotations

from threading import Lock

from models.mapeo import MapeoConfig

_mapeos: dict[str, MapeoConfig] = {}
_lock = Lock()


def guardar_mapeo(mapeo: MapeoConfig) -> MapeoConfig:
    with _lock:
        _mapeos[mapeo.archivo_id] = mapeo
    return mapeo


def obtener_mapeo(archivo_id: str) -> MapeoConfig | None:
    with _lock:
        return _mapeos.get(archivo_id)


def listar_mapeos() -> list[MapeoConfig]:
    with _lock:
        return list(_mapeos.values())
