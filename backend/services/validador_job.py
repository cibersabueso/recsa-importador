from __future__ import annotations

from pathlib import Path

from cli.layouts._loader import cargar_layout
from models.job import ArchivoJob, JobPayload
from services.validador_carga import validar_archivo

MUESTRAS_DEFAULT = 500


def _validar_basico_sin_layout(archivo: ArchivoJob, ruta: Path) -> list[str]:
    errores: list[str] = []
    try:
        with ruta.open("r", encoding="utf-8", errors="replace") as handle:
            primera = handle.readline().rstrip("\r\n")
    except OSError as error:
        errores.append(
            f"no se pudo leer el archivo '{archivo.nombre}': {error}"
        )
        return errores
    if not primera:
        errores.append(f"el archivo '{archivo.nombre}' está vacío")
        return errores
    columnas = primera.split(archivo.delimitador)
    if len(columnas) < 2:
        errores.append(
            f"el archivo '{archivo.nombre}' produce {len(columnas)} columna(s) "
            f"al separar por '{archivo.delimitador}'; revisar delimitador o "
            f"formato del archivo"
        )
    return errores


def validar_job(
    payload: JobPayload,
    nombres_por_archivo: dict[str, list[str]] | None = None,
) -> tuple[bool, list[str]]:
    del nombres_por_archivo
    errores_globales: list[str] = []

    if not payload.archivos:
        errores_globales.append(
            "el payload no declara archivos para procesar"
        )
        return False, errores_globales

    for archivo in payload.archivos:
        ruta = Path(archivo.ruta)
        if not ruta.exists():
            errores_globales.append(
                f"el archivo '{archivo.nombre}' no existe en la ruta declarada: "
                f"{archivo.ruta}"
            )
            continue

        if archivo.layout:
            try:
                layout = cargar_layout(archivo.layout)
            except ValueError as error:
                errores_globales.append(
                    f"el layout '{archivo.layout}' del archivo "
                    f"'{archivo.nombre}' no se pudo cargar: {error}"
                )
                continue
            ok, errores = validar_archivo(ruta, layout, muestras=MUESTRAS_DEFAULT)
            if not ok:
                errores_globales.extend(errores)
        else:
            errores_globales.extend(_validar_basico_sin_layout(archivo, ruta))

    return len(errores_globales) == 0, errores_globales


def formatear_errores(errores: list[str]) -> str:
    if not errores:
        return ""
    return " | ".join(errores)
