from __future__ import annotations

import hashlib
import re
import unicodedata

PREFIJO_TABLA: str = "cargas_"
MAX_NOMBRE_TOTAL: int = 60
MAX_NOMBRE_TRUNCADO: int = 50
LARGO_HASH: int = 8


def normalizar_empresa(empresa: str) -> str:
    if not isinstance(empresa, str) or not empresa.strip():
        raise ValueError("empresa debe ser un string no vacío")
    base = empresa.strip()
    sin_tildes = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode(
        "ascii"
    )
    lower = sin_tildes.lower()
    normalizado = re.sub(r"[^a-z0-9_]", "_", lower)
    normalizado = re.sub(r"_+", "_", normalizado).strip("_")
    if not normalizado:
        raise ValueError(f"empresa '{empresa}' no produce identificador válido")
    return normalizado


def nombre_tabla_cliente(empresa: str) -> str:
    normalizado = normalizar_empresa(empresa)
    tentativo = f"{PREFIJO_TABLA}{normalizado}"
    if len(tentativo) <= MAX_NOMBRE_TOTAL:
        return tentativo
    hash_suffix = hashlib.md5(empresa.strip().encode("utf-8")).hexdigest()[:LARGO_HASH]
    espacio = MAX_NOMBRE_TRUNCADO - len(PREFIJO_TABLA) - 1 - LARGO_HASH
    if espacio < 1:
        raise ValueError("Configuración inválida para truncado de nombre de tabla")
    truncado = normalizado[:espacio].rstrip("_") or normalizado[:espacio]
    return f"{PREFIJO_TABLA}{truncado}_{hash_suffix}"
