from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cli._inferencia import (
    RE_DATE,
    TipoInferido,
    inferir_tipo,
    parece_nombre_persona,
)

DELIMITADORES_CANDIDATOS: tuple[str, ...] = (";", "|", ",", "\t")
NOMBRES_DELIMITADORES: dict[str, str] = {
    ";": "punto y coma (;)",
    "|": "pipe (|)",
    ",": "coma (,)",
    "\t": "tabulación (\\t)",
}
LIMITE_MUESTRAS_MAX = 10000
LIMITE_LECTURA_LINEAS = 10000

ModoEncabezados = Literal["true", "false", "auto"]
LOGS_DIR: Path = Path(__file__).resolve().parent.parent / "logs"


@dataclass
class PerfilColumna:
    posicion: int
    nombre: str
    cantidad_llena: int
    porcentaje_llena: float
    valores_unicos: int
    longitud_minima: int
    longitud_maxima: int
    tipo: TipoInferido
    ejemplos: list[str]


@dataclass
class InfoArchivo:
    ruta: Path
    tamano_bytes: int
    lineas_totales_estimadas: int
    columnas: int
    delimitador: str
    tiene_encabezados: bool
    codificacion: str


def _leer_lineas(
    ruta: Path, max_lineas: int
) -> tuple[list[str], str]:
    intentos = ("utf-8", "latin-1")
    for encoding in intentos:
        lineas: list[str] = []
        try:
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


def _detectar_delimitador(primera_linea: str) -> str:
    conteos = {
        delim: primera_linea.count(delim) for delim in DELIMITADORES_CANDIDATOS
    }
    ganador = max(conteos, key=conteos.get)
    if conteos[ganador] == 0:
        return ","
    return ganador


def _autodetectar_encabezados(lineas: list[str], delimitador: str) -> bool:
    if len(lineas) < 2:
        return True
    primera = lineas[0].split(delimitador)
    siguientes = [linea.split(delimitador) for linea in lineas[1:11]]

    def es_texto_no_numerico(valor: str) -> bool:
        v = valor.strip()
        if not v:
            return False
        if RE_DATE.match(v):
            return False
        try:
            float(v.replace(",", "."))
            return False
        except ValueError:
            return True

    no_num_primera = sum(1 for v in primera if es_texto_no_numerico(v))
    if not primera:
        return False
    ratio_primera = no_num_primera / max(len(primera), 1)
    if ratio_primera < 0.6:
        return False

    if not siguientes:
        return ratio_primera >= 0.6
    valores_siguientes = [v for fila in siguientes for v in fila]
    if not valores_siguientes:
        return ratio_primera >= 0.6
    no_num_siguientes = sum(
        1 for v in valores_siguientes if es_texto_no_numerico(v)
    )
    ratio_siguientes = no_num_siguientes / max(len(valores_siguientes), 1)
    return ratio_primera > ratio_siguientes + 0.2


def _separar(
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
        ncols = len(lineas[0].split(delimitador))
        encabezados = [f"col_{i}" for i in range(ncols)]
        cuerpo = lineas[:muestras]
    filas = [linea.split(delimitador) for linea in cuerpo]
    return encabezados, filas


def _perfilar(
    encabezados: list[str], filas: list[list[str]]
) -> list[PerfilColumna]:
    total_muestras = max(len(filas), 1)
    perfiles: list[PerfilColumna] = []
    for idx, nombre in enumerate(encabezados):
        valores: list[str | None] = []
        for fila in filas:
            if idx < len(fila):
                v = fila[idx].strip()
                valores.append(v if v else None)
            else:
                valores.append(None)
        no_vacios = [v for v in valores if v]
        unicos_set: set[str] = set()
        for v in no_vacios:
            if len(unicos_set) >= LIMITE_MUESTRAS_MAX:
                break
            unicos_set.add(v)
        long_min = min((len(v) for v in no_vacios), default=0)
        long_max = max((len(v) for v in no_vacios), default=0)
        ejemplos = []
        seen: set[str] = set()
        for v in no_vacios:
            if v in seen:
                continue
            seen.add(v)
            ejemplos.append(v)
            if len(ejemplos) >= 3:
                break
        tipo = inferir_tipo(valores)
        perfiles.append(
            PerfilColumna(
                posicion=idx,
                nombre=nombre,
                cantidad_llena=len(no_vacios),
                porcentaje_llena=100.0 * len(no_vacios) / total_muestras,
                valores_unicos=len(unicos_set),
                longitud_minima=long_min,
                longitud_maxima=long_max,
                tipo=tipo,
                ejemplos=ejemplos,
            )
        )
    return perfiles


def _sugerir(
    perfiles: list[PerfilColumna], muestras_no_vacios_por_columna: list[list[str | None]]
) -> list[str]:
    sugerencias: list[str] = []
    for perfil, valores in zip(perfiles, muestras_no_vacios_por_columna):
        ratio_unicos = (
            perfil.valores_unicos / max(perfil.cantidad_llena, 1)
            if perfil.cantidad_llena > 0
            else 0.0
        )
        if (
            perfil.tipo == "NUM_PAD"
            and perfil.longitud_maxima == 8
            and 0.6 <= ratio_unicos <= 1.0
        ):
            sugerencias.append(
                f"{perfil.nombre} (pos {perfil.posicion}): NUM_PAD de 8 chars con "
                f"{ratio_unicos:.0%} de unicidad → candidato a código interno / join"
            )
            continue
        if (
            perfil.tipo == "INT"
            and perfil.longitud_maxima == 8
            and perfil.longitud_minima == 8
            and 0.6 <= ratio_unicos <= 1.0
        ):
            sugerencias.append(
                f"{perfil.nombre} (pos {perfil.posicion}): INT de 8 dígitos sin "
                f"padding con {ratio_unicos:.0%} unicidad → candidato a DNI peruano"
            )
            continue
        if (
            perfil.tipo == "DATE"
            and perfil.porcentaje_llena >= 99.0
            and perfil.valores_unicos == 1
        ):
            sugerencias.append(
                f"{perfil.nombre} (pos {perfil.posicion}): DATE constante → fecha de "
                f"proceso (no mapear)"
            )
            continue
        if perfil.tipo == "DATE" and perfil.valores_unicos > 5:
            sugerencias.append(
                f"{perfil.nombre} (pos {perfil.posicion}): DATE con varios valores → "
                f"candidato a fecha_vencimiento"
            )
            continue
        if perfil.tipo == "CATEGORICAL" and 5 <= perfil.valores_unicos <= 15:
            sugerencias.append(
                f"{perfil.nombre} (pos {perfil.posicion}): CATEGORICAL con "
                f"{perfil.valores_unicos} valores → candidato a tramo / categoría"
            )
            continue
        if perfil.tipo == "DECIMAL":
            sugerencias.append(
                f"{perfil.nombre} (pos {perfil.posicion}): DECIMAL → candidato a monto"
            )
            continue
        if perfil.tipo == "TEXT" and parece_nombre_persona(valores):
            sugerencias.append(
                f"{perfil.nombre} (pos {perfil.posicion}): TEXT con formato de nombres "
                f"→ candidato a nombre_completo"
            )
    return sugerencias


def _info_archivo(
    ruta: Path,
    delimitador: str,
    tiene_encabezados: bool,
    codificacion: str,
    columnas: int,
    lineas_leidas: int,
) -> InfoArchivo:
    tamano = ruta.stat().st_size
    if lineas_leidas == 0:
        total_estimado = 0
    else:
        muestra_path = ruta
        bytes_muestra = 0
        with muestra_path.open("rb") as handle:
            for i, linea in enumerate(handle):
                if i >= lineas_leidas:
                    break
                bytes_muestra += len(linea)
        if bytes_muestra > 0:
            total_estimado = int(tamano / bytes_muestra * lineas_leidas)
        else:
            total_estimado = lineas_leidas
    return InfoArchivo(
        ruta=ruta,
        tamano_bytes=tamano,
        lineas_totales_estimadas=total_estimado,
        columnas=columnas,
        delimitador=delimitador,
        tiene_encabezados=tiene_encabezados,
        codificacion=codificacion,
    )


def _formato_tamano(bytes_: int) -> str:
    unidades = ["B", "KB", "MB", "GB", "TB"]
    valor = float(bytes_)
    idx = 0
    while valor >= 1024 and idx < len(unidades) - 1:
        valor /= 1024
        idx += 1
    return f"{valor:.2f} {unidades[idx]}"


def _truncar(texto: str, limite: int = 30) -> str:
    if len(texto) <= limite:
        return texto
    return texto[: limite - 1] + "…"


def _render_tabla_consola(perfiles: list[PerfilColumna]) -> str:
    encabezados = ["Pos", "Nombre", "Llenas %", "Únicos", "Tipo", "Long max", "Ejemplos"]
    filas: list[list[str]] = []
    for p in perfiles:
        filas.append(
            [
                str(p.posicion),
                _truncar(p.nombre, 28),
                f"{p.porcentaje_llena:5.1f}%",
                str(p.valores_unicos),
                p.tipo,
                str(p.longitud_maxima),
                _truncar(" | ".join(p.ejemplos), 50),
            ]
        )
    anchos = [
        max(len(encabezados[i]), max((len(fila[i]) for fila in filas), default=0))
        for i in range(len(encabezados))
    ]
    sep = "  "
    lineas = [sep.join(h.ljust(anchos[i]) for i, h in enumerate(encabezados))]
    lineas.append(sep.join("-" * anchos[i] for i in range(len(encabezados))))
    for fila in filas:
        lineas.append(sep.join(fila[i].ljust(anchos[i]) for i in range(len(fila))))
    return "\n".join(lineas)


def _render_tabla_markdown(perfiles: list[PerfilColumna]) -> str:
    lineas = [
        "| Pos | Nombre | Llenas % | Únicos | Tipo | Long min | Long max | Ejemplos |",
        "|---:|---|---:|---:|---|---:|---:|---|",
    ]
    for p in perfiles:
        ejemplos = " \\| ".join(_truncar(e, 40) for e in p.ejemplos)
        lineas.append(
            f"| {p.posicion} | `{p.nombre}` | {p.porcentaje_llena:.1f}% | "
            f"{p.valores_unicos} | {p.tipo} | {p.longitud_minima} | "
            f"{p.longitud_maxima} | {ejemplos} |"
        )
    return "\n".join(lineas)


def _render_markdown(
    info: InfoArchivo, perfiles: list[PerfilColumna], sugerencias: list[str]
) -> str:
    delim_humano = NOMBRES_DELIMITADORES.get(info.delimitador, info.delimitador)
    encabezados_str = "Sí" if info.tiene_encabezados else "No"
    secciones: list[str] = []
    secciones.append(f"# Inspección: {info.ruta.name}")
    secciones.append("")
    secciones.append(f"- **Ruta:** `{info.ruta}`")
    secciones.append(f"- **Tamaño:** {_formato_tamano(info.tamano_bytes)}")
    secciones.append(f"- **Líneas totales (estimadas):** {info.lineas_totales_estimadas:,}")
    secciones.append(f"- **Columnas:** {info.columnas}")
    secciones.append(f"- **Delimitador:** {delim_humano}")
    secciones.append(f"- **Encabezados:** {encabezados_str}")
    secciones.append(f"- **Codificación:** {info.codificacion}")
    secciones.append("")
    secciones.append("## Columnas")
    secciones.append("")
    secciones.append(_render_tabla_markdown(perfiles))
    secciones.append("")
    secciones.append("## Sugerencias automáticas")
    secciones.append("")
    if not sugerencias:
        secciones.append("_Sin sugerencias automáticas para esta muestra._")
    else:
        for s in sugerencias:
            secciones.append(f"- {s}")
    secciones.append("")
    return "\n".join(secciones)


def _ruta_salida_default(archivo: Path) -> Path:
    return LOGS_DIR / f"inspeccion_{archivo.stem}.md"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Perfila columnas de un archivo y sugiere mapeos"
    )
    parser.add_argument("--archivo", type=Path, required=True)
    parser.add_argument("--delimitador", type=str, default=None)
    parser.add_argument(
        "--tiene-encabezados",
        type=str,
        choices=["true", "false"],
        default=None,
    )
    parser.add_argument("--muestras", type=int, default=1000)
    parser.add_argument("--salida", type=Path, default=None)
    args = parser.parse_args()

    if not args.archivo.exists():
        print(f"Archivo no encontrado: {args.archivo}", file=sys.stderr)
        sys.exit(1)

    muestras = max(1, min(LIMITE_MUESTRAS_MAX, args.muestras))
    lineas_a_leer = max(muestras + 1, LIMITE_LECTURA_LINEAS)
    lineas, codificacion = _leer_lineas(args.archivo, lineas_a_leer)
    if not lineas:
        print(f"Archivo vacío: {args.archivo}", file=sys.stderr)
        sys.exit(1)

    if args.delimitador:
        delimitador = args.delimitador.replace("\\t", "\t")
    else:
        delimitador = _detectar_delimitador(lineas[0])

    if args.tiene_encabezados is not None:
        tiene_encabezados = args.tiene_encabezados == "true"
    else:
        tiene_encabezados = _autodetectar_encabezados(lineas, delimitador)

    encabezados, filas = _separar(lineas, delimitador, tiene_encabezados, muestras)
    perfiles = _perfilar(encabezados, filas)

    valores_por_columna: list[list[str | None]] = []
    for idx in range(len(encabezados)):
        columna_valores: list[str | None] = []
        for fila in filas:
            if idx < len(fila):
                v = fila[idx].strip()
                columna_valores.append(v if v else None)
            else:
                columna_valores.append(None)
        valores_por_columna.append(columna_valores)
    sugerencias = _sugerir(perfiles, valores_por_columna)

    info = _info_archivo(
        args.archivo,
        delimitador,
        tiene_encabezados,
        codificacion,
        columnas=len(encabezados),
        lineas_leidas=len(lineas),
    )

    salida = args.salida or _ruta_salida_default(args.archivo)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(_render_markdown(info, perfiles, sugerencias), encoding="utf-8")

    delim_humano = NOMBRES_DELIMITADORES.get(delimitador, delimitador)
    print(f"Archivo:      {info.ruta}")
    print(f"Tamaño:       {_formato_tamano(info.tamano_bytes)}")
    print(f"Líneas est.:  {info.lineas_totales_estimadas:,}")
    print(f"Columnas:     {info.columnas}")
    print(f"Delimitador:  {delim_humano}")
    print(f"Encabezados:  {'Sí' if tiene_encabezados else 'No'}")
    print(f"Codificación: {codificacion}")
    print()
    print(_render_tabla_consola(perfiles))
    print()
    print("Sugerencias automáticas:")
    if not sugerencias:
        print("  (sin sugerencias)")
    else:
        for s in sugerencias:
            print(f"  - {s}")
    print()
    print(f"Reporte:      {salida}")


if __name__ == "__main__":
    main()
