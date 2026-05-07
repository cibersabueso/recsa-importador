from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def _normalizar(valor: str | None) -> str | None:
    if valor is None:
        return None
    texto = valor.strip()
    if not texto:
        return None
    return texto


def to_decimal(valor: str | None) -> Decimal | None:
    texto = _normalizar(valor)
    if texto is None:
        return None
    normalizado = texto.replace(" ", "")
    if "," in normalizado and "." in normalizado:
        if normalizado.rfind(",") > normalizado.rfind("."):
            normalizado = normalizado.replace(".", "").replace(",", ".")
        else:
            normalizado = normalizado.replace(",", "")
    elif "," in normalizado:
        normalizado = normalizado.replace(",", ".")
    try:
        return Decimal(normalizado)
    except (InvalidOperation, ValueError):
        return None


def to_date_ddmmyyyy(valor: str | None) -> date | None:
    texto = _normalizar(valor)
    if texto is None:
        return None
    for formato in ("%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def to_int(valor: str | None) -> int | None:
    texto = _normalizar(valor)
    if texto is None:
        return None
    try:
        return int(texto)
    except ValueError:
        try:
            return int(Decimal(texto))
        except (InvalidOperation, ValueError):
            return None


def to_text(valor: str | None, max_len: int | None = None) -> str | None:
    texto = _normalizar(valor)
    if texto is None:
        return None
    if max_len is not None and len(texto) > max_len:
        return texto[:max_len]
    return texto
