from __future__ import annotations

from threading import Lock

from models.config import ArchivoConfig, ProcesoConfig

_proceso: ProcesoConfig | None = None
_archivos_config: dict[str, ArchivoConfig] = {}
_lock = Lock()


def guardar_proceso(config: ProcesoConfig) -> ProcesoConfig:
    global _proceso
    with _lock:
        _proceso = config
    return config


def obtener_proceso() -> ProcesoConfig | None:
    with _lock:
        return _proceso


def guardar_archivo_config(config: ArchivoConfig) -> ArchivoConfig:
    with _lock:
        _archivos_config[config.archivo_id] = config
    return config


def obtener_archivo_config(archivo_id: str) -> ArchivoConfig | None:
    with _lock:
        return _archivos_config.get(archivo_id)


def listar_archivo_configs() -> list[ArchivoConfig]:
    with _lock:
        return sorted(_archivos_config.values(), key=lambda c: c.orden)
