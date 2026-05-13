from __future__ import annotations


def formatear_duracion(segundos: int | float | None) -> str:
    if segundos is None:
        return "-"
    if segundos < 0:
        return "-"
    seg_total = int(segundos)
    if seg_total == 0:
        return "0s"
    if seg_total < 60:
        return f"{seg_total}s"
    minutos_total = seg_total // 60
    seg = seg_total % 60
    if minutos_total < 60:
        return f"{minutos_total}m {seg}s"
    horas = minutos_total // 60
    minutos = minutos_total % 60
    return f"{horas}h {minutos}m {seg}s"
