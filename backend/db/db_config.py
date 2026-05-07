from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


CONFIG_PATH: Path = Path(__file__).resolve().parent / "databases.yml"


@dataclass(frozen=True)
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


def _config_desde_env() -> DBConfig:
    return DBConfig(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ.get("POSTGRES_USER", "recsa"),
        password=os.environ.get("POSTGRES_PASSWORD", "recsa123"),
        database=os.environ.get("POSTGRES_DB", "recsa_cargas"),
    )


def _validar_config(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("databases.yml debe contener un mapping en la raíz")
    return raw


def _construir_dbconfig(nombre: str, raw: dict[str, Any]) -> DBConfig:
    requeridos = ("host", "port", "user", "password", "database")
    faltantes = [campo for campo in requeridos if campo not in raw]
    if faltantes:
        raise ValueError(
            f"Config '{nombre}' incompleta, faltan campos: {faltantes}"
        )
    return DBConfig(
        host=str(raw["host"]),
        port=int(raw["port"]),
        user=str(raw["user"]),
        password=str(raw["password"]),
        database=str(raw["database"]),
    )


def cargar_config() -> tuple[dict[str, DBConfig], DBConfig]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"databases.yml no encontrado en {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    raw = _validar_config(raw)

    paises_raw = raw.get("paises") or {}
    if not isinstance(paises_raw, dict):
        raise ValueError("Sección 'paises' en databases.yml debe ser un mapping")

    paises: dict[str, DBConfig] = {}
    for codigo, datos in paises_raw.items():
        if not isinstance(datos, dict):
            raise ValueError(f"Config del país '{codigo}' debe ser un mapping")
        paises[str(codigo)] = _construir_dbconfig(str(codigo), datos)

    default_raw = raw.get("default_connection")
    if not isinstance(default_raw, dict):
        raise ValueError(
            "Sección 'default_connection' faltante o inválida en databases.yml"
        )
    default_config = _construir_dbconfig("default_connection", default_raw)

    return paises, default_config


def resolver_db(pais: str | None) -> DBConfig:
    try:
        paises, default_config = cargar_config()
    except FileNotFoundError:
        return _config_desde_env()
    if pais is not None:
        codigo = pais.strip().upper()
        if codigo in paises:
            return paises[codigo]
    return default_config
