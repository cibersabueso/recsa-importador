from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

LAYOUTS_DIR: Path = Path(__file__).resolve().parent

TipoColumna = Literal[
    "string", "int", "decimal", "date", "empty", "categorical"
]


class LayoutColumna(BaseModel):
    posicion: int | None = None
    nombre: str
    tipo: TipoColumna = "string"
    formato: str | None = None
    requerido: bool = False
    solo_join: bool = False


class Layout(BaseModel):
    nombre: str
    descripcion: str | None = None
    delimitador: str
    codificacion: str = "UTF-8"
    tiene_encabezados: bool
    separador_decimal: str = "."
    columnas: list[LayoutColumna] = Field(default_factory=list)


def cargar_layout(nombre: str) -> Layout:
    ruta = LAYOUTS_DIR / f"{nombre}.yml"
    if not ruta.exists():
        disponibles = listar_layouts()
        raise ValueError(
            f"Layout '{nombre}' no encontrado en {LAYOUTS_DIR}. "
            f"Disponibles: {disponibles}"
        )
    with ruta.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(
            f"Layout '{nombre}': se esperaba un mapping en la raíz del YAML"
        )
    return Layout.model_validate(data)


def listar_layouts() -> list[str]:
    if not LAYOUTS_DIR.exists():
        return []
    return sorted(p.stem for p in LAYOUTS_DIR.glob("*.yml"))


def expandir_nombres(layout: Layout) -> list[str]:
    if not layout.columnas:
        return []
    posiciones = {
        col.posicion: col.nombre
        for col in layout.columnas
        if col.posicion is not None
    }
    if not posiciones:
        return [col.nombre for col in layout.columnas]
    max_pos = max(posiciones.keys())
    return [posiciones.get(i, f"col_{i}") for i in range(max_pos + 1)]


def nombres_solo_join(layout: Layout) -> set[str]:
    return {col.nombre for col in layout.columnas if col.solo_join}
