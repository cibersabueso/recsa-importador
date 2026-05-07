from __future__ import annotations

import re
from typing import Literal

TipoInferido = Literal[
    "EMPTY", "DATE", "DECIMAL", "NUM_PAD", "INT", "CATEGORICAL", "TEXT"
]

RE_DATE = re.compile(r"^\d{2}[-/]\d{2}[-/]\d{4}$")
RE_DECIMAL = re.compile(r"^\d+\.\d+$")
RE_NUM_PAD = re.compile(r"^0+\d+$")
RE_INT = re.compile(r"^\d+$")
RE_NOMBRE_TEXT = re.compile(r"^[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ \-\.]{4,}$")

UMBRAL_RATIO = 0.8
UMBRAL_CATEGORICAL_MAX = 20


def inferir_tipo(valores: list[str | None]) -> TipoInferido:
    no_vacios = [v for v in valores if v is not None and v != ""]
    if not no_vacios:
        return "EMPTY"
    total = len(no_vacios)

    matches_date = sum(1 for v in no_vacios if RE_DATE.match(v))
    if matches_date / total >= UMBRAL_RATIO:
        return "DATE"

    matches_dec = sum(1 for v in no_vacios if RE_DECIMAL.match(v))
    if matches_dec / total >= UMBRAL_RATIO:
        return "DECIMAL"

    pad_matches = [v for v in no_vacios if RE_NUM_PAD.match(v)]
    if len(pad_matches) / total >= UMBRAL_RATIO:
        longitudes = {len(v) for v in pad_matches}
        if len(longitudes) == 1:
            return "NUM_PAD"

    matches_int = sum(1 for v in no_vacios if RE_INT.match(v))
    if matches_int / total >= UMBRAL_RATIO:
        return "INT"

    unicos = len(set(no_vacios))
    if unicos < UMBRAL_CATEGORICAL_MAX:
        return "CATEGORICAL"

    return "TEXT"


def parece_nombre_persona(valores: list[str | None]) -> bool:
    no_vacios = [v for v in valores if v]
    if len(no_vacios) < 3:
        return False
    matches = sum(1 for v in no_vacios if RE_NOMBRE_TEXT.match(v))
    return matches / len(no_vacios) >= 0.6
