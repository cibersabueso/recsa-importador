from __future__ import annotations

from pathlib import Path

from cli._inferencia import RE_DATE, RE_DECIMAL, RE_INT, RE_NUM_PAD
from cli.layouts._loader import Layout, LayoutColumna

UMBRAL_NO_MATCH_TIPO = 0.30


def _leer_lineas(ruta: Path, max_lineas: int) -> list[str]:
    intentos = ("utf-8", "latin-1")
    for encoding in intentos:
        try:
            lineas: list[str] = []
            with ruta.open("r", encoding=encoding, errors="strict") as handle:
                for i, linea in enumerate(handle):
                    if i >= max_lineas:
                        break
                    lineas.append(linea.rstrip("\r\n"))
            return lineas
        except UnicodeDecodeError:
            continue
    lineas = []
    with ruta.open("r", encoding="latin-1", errors="replace") as handle:
        for i, linea in enumerate(handle):
            if i >= max_lineas:
                break
            lineas.append(linea.rstrip("\r\n"))
    return lineas


def _separar_filas(
    lineas: list[str],
    delimitador: str,
    tiene_encabezados: bool,
    muestras: int,
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


def _valores_columna(indice: int, filas: list[list[str]]) -> list[str | None]:
    valores: list[str | None] = []
    for fila in filas:
        if indice < len(fila):
            v = fila[indice].strip()
            valores.append(v if v else None)
        else:
            valores.append(None)
    return valores


def _columnas_esperadas(layout: Layout) -> int:
    if layout.tiene_encabezados:
        return len(layout.columnas)
    posiciones = [c.posicion for c in layout.columnas if c.posicion is not None]
    if not posiciones:
        return len(layout.columnas)
    return max(posiciones) + 1


def _valor_compatible(valor: str, tipo: str) -> bool:
    if tipo in ("string", "categorical"):
        return True
    if tipo == "empty":
        return False
    if tipo == "int":
        return bool(RE_INT.match(valor)) or bool(RE_NUM_PAD.match(valor))
    if tipo == "decimal":
        return bool(RE_DECIMAL.match(valor)) or bool(RE_INT.match(valor))
    if tipo == "date":
        return bool(RE_DATE.match(valor))
    return True


def validar_archivo(
    ruta: Path, layout: Layout, muestras: int = 500
) -> tuple[bool, list[str]]:
    errores: list[str] = []
    nombre = ruta.name

    if not ruta.exists():
        errores.append(
            f"el archivo '{nombre}' no existe en la ruta declarada: {ruta}"
        )
        return False, errores

    muestras = max(1, muestras)
    lineas = _leer_lineas(ruta, muestras + 1)
    if not lineas:
        errores.append(f"el archivo '{nombre}' está vacío")
        return False, errores

    encabezados, filas = _separar_filas(
        lineas, layout.delimitador, layout.tiene_encabezados, muestras
    )

    if layout.tiene_encabezados and not encabezados:
        errores.append(
            f"el archivo '{nombre}' no tiene fila de encabezados pero el "
            f"layout '{layout.nombre}' la requiere"
        )
        return False, errores

    if not filas:
        errores.append(
            f"el archivo '{nombre}' no contiene filas de datos después de los "
            f"encabezados"
        )
        return False, errores

    cols_archivo = len(filas[0])
    cols_esperadas = _columnas_esperadas(layout)
    if cols_archivo < cols_esperadas:
        errores.append(
            f"el archivo '{nombre}' tiene {cols_archivo} columnas pero el "
            f"layout '{layout.nombre}' espera al menos {cols_esperadas}. "
            f"Verificar con el cliente si cambió el formato."
        )

    if layout.tiene_encabezados and encabezados:
        nombres_layout = {col.nombre for col in layout.columnas}
        faltantes = sorted(nombres_layout - set(encabezados))
        if faltantes:
            errores.append(
                f"el archivo '{nombre}' no contiene la(s) columna(s) "
                f"esperada(s) por el layout '{layout.nombre}': "
                f"{', '.join(faltantes)}"
            )

    for col in layout.columnas:
        if col.solo_join:
            continue
        indice = _resolver_indice(col, encabezados, layout.tiene_encabezados)
        if indice is None:
            errores.append(
                f"la columna '{col.nombre}' del layout '{layout.nombre}' no "
                f"se puede ubicar en el archivo '{nombre}'"
            )
            continue
        if indice >= cols_archivo:
            continue

        valores = _valores_columna(indice, filas)
        no_vacios = [v for v in valores if v]

        if col.requerido and not no_vacios:
            errores.append(
                f"la columna requerida '{col.nombre}' del archivo '{nombre}' "
                f"está vacía en el 100% de las {len(valores)} filas muestreadas"
            )
            continue

        if no_vacios:
            no_match = sum(
                1 for v in no_vacios if not _valor_compatible(v, col.tipo)
            )
            ratio = no_match / len(no_vacios)
            if ratio > UMBRAL_NO_MATCH_TIPO:
                pct = 100.0 * ratio
                umbral_pct = 100.0 * UMBRAL_NO_MATCH_TIPO
                errores.append(
                    f"la columna '{col.nombre}' del archivo '{nombre}' tiene "
                    f"{no_match} de {len(no_vacios)} valores que no son del "
                    f"tipo declarado '{col.tipo}' ({pct:.0f}%, umbral "
                    f"{umbral_pct:.0f}%)"
                )

    return len(errores) == 0, errores
