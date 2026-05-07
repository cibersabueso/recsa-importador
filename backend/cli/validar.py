from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cli._inferencia import TipoInferido, inferir_tipo
from cli.layouts._loader import Layout, LayoutColumna, cargar_layout

NivelValidacion = Literal["OK", "WARNING", "ERROR"]

TIPO_LAYOUT_A_INFERIDOS: dict[str, set[str]] = {
    "string": {"TEXT", "CATEGORICAL", "NUM_PAD", "INT", "EMPTY"},
    "int": {"INT", "EMPTY"},
    "decimal": {"DECIMAL", "INT", "EMPTY"},
    "date": {"DATE", "EMPTY"},
    "categorical": {"CATEGORICAL", "TEXT", "EMPTY"},
    "empty": {"EMPTY"},
}


@dataclass
class ResultadoValidacion:
    columna: str
    nivel: NivelValidacion
    mensaje: str


def _leer_lineas(ruta: Path, max_lineas: int) -> tuple[list[str], str]:
    intentos = ("utf-8", "latin-1")
    for encoding in intentos:
        try:
            lineas: list[str] = []
            with ruta.open("r", encoding=encoding, errors="strict") as handle:
                for i, linea in enumerate(handle):
                    if i >= max_lineas:
                        break
                    lineas.append(linea.rstrip("\r\n"))
            return lineas, "UTF-8" if encoding == "utf-8" else "Latin1"
        except UnicodeDecodeError:
            continue
    lineas = []
    with ruta.open("r", encoding="latin-1", errors="replace") as handle:
        for i, linea in enumerate(handle):
            if i >= max_lineas:
                break
            lineas.append(linea.rstrip("\r\n"))
    return lineas, "Latin1"


def _separar_filas(
    lineas: list[str], delimitador: str, tiene_encabezados: bool, muestras: int
) -> tuple[list[str], list[list[str]]]:
    if not lineas:
        return [], []
    if tiene_encabezados:
        encabezados = [c.strip() for c in lineas[0].split(delimitador)]
        cuerpo = lineas[1 : 1 + muestras]
    else:
        encabezados = []
        cuerpo = lineas[:muestras]
    filas = [linea.split(delimitador) for linea in cuerpo]
    return encabezados, filas


def _resolver_indice(
    columna: LayoutColumna,
    encabezados_archivo: list[str],
    layout_tiene_encabezados: bool,
) -> int | None:
    if not layout_tiene_encabezados:
        return columna.posicion
    if columna.nombre in encabezados_archivo:
        return encabezados_archivo.index(columna.nombre)
    if columna.posicion is not None:
        return columna.posicion
    return None


def _valores_columna(
    indice: int, filas: list[list[str]]
) -> list[str | None]:
    valores: list[str | None] = []
    for fila in filas:
        if indice < len(fila):
            v = fila[indice].strip()
            valores.append(v if v else None)
        else:
            valores.append(None)
    return valores


def _tipo_compatible(tipo_layout: str, tipo_inferido: TipoInferido) -> bool:
    permitidos = TIPO_LAYOUT_A_INFERIDOS.get(tipo_layout, set())
    return tipo_inferido in permitidos


def _validar_columna(
    columna: LayoutColumna,
    encabezados_archivo: list[str],
    filas: list[list[str]],
    layout: Layout,
) -> ResultadoValidacion:
    indice = _resolver_indice(columna, encabezados_archivo, layout.tiene_encabezados)
    if indice is None:
        return ResultadoValidacion(
            columna=columna.nombre,
            nivel="ERROR",
            mensaje="no se pudo resolver posición en el archivo",
        )

    if filas and indice >= len(filas[0]):
        return ResultadoValidacion(
            columna=columna.nombre,
            nivel="ERROR",
            mensaje=(
                f"posición {indice} fuera de rango "
                f"(archivo tiene {len(filas[0])} columnas)"
            ),
        )

    valores = _valores_columna(indice, filas)
    no_vacios = [v for v in valores if v]
    porcentaje_llena = (
        100.0 * len(no_vacios) / max(len(valores), 1) if valores else 0.0
    )
    tipo_inferido = inferir_tipo(valores)

    if columna.requerido and porcentaje_llena < 100.0:
        return ResultadoValidacion(
            columna=columna.nombre,
            nivel="ERROR",
            mensaje=(
                f"requerida pero {porcentaje_llena:.1f}% llena "
                f"(faltan {len(valores) - len(no_vacios)} de {len(valores)})"
            ),
        )

    if not _tipo_compatible(columna.tipo, tipo_inferido):
        return ResultadoValidacion(
            columna=columna.nombre,
            nivel="WARNING",
            mensaje=(
                f"tipo declarado '{columna.tipo}' no coincide con inferido "
                f"'{tipo_inferido}' (pos {indice})"
            ),
        )

    return ResultadoValidacion(
        columna=columna.nombre,
        nivel="OK",
        mensaje=(
            f"pos {indice}, tipo {tipo_inferido}, llena {porcentaje_llena:.1f}%"
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Valida un archivo contra un layout declarado"
    )
    parser.add_argument("--archivo", type=Path, required=True)
    parser.add_argument("--layout", type=str, required=True)
    parser.add_argument("--muestras", type=int, default=500)
    args = parser.parse_args()

    if not args.archivo.exists():
        print(f"Archivo no encontrado: {args.archivo}", file=sys.stderr)
        sys.exit(1)

    try:
        layout = cargar_layout(args.layout)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)

    muestras = max(1, args.muestras)
    lineas, _ = _leer_lineas(args.archivo, muestras + 1)
    if not lineas:
        print(f"Archivo vacío: {args.archivo}", file=sys.stderr)
        sys.exit(1)

    encabezados_archivo, filas = _separar_filas(
        lineas, layout.delimitador, layout.tiene_encabezados, muestras
    )

    resultados: list[ResultadoValidacion] = [
        _validar_columna(col, encabezados_archivo, filas, layout)
        for col in layout.columnas
    ]

    print(f"Archivo: {args.archivo}")
    print(f"Layout:  {layout.nombre}")
    print(f"Filas muestreadas: {len(filas)}")
    print()
    for r in resultados:
        print(f"[{r.nivel:7}] {r.columna}: {r.mensaje}")

    errores = sum(1 for r in resultados if r.nivel == "ERROR")
    warnings = sum(1 for r in resultados if r.nivel == "WARNING")
    print()
    print(f"Resumen: {len(resultados) - errores - warnings} OK, {warnings} WARNING, {errores} ERROR")

    if errores > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
