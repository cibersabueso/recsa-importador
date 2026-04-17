from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import chardet
import pandas as pd

EXTENSIONES_SOPORTADAS = {"csv", "txt", "xlsx", "xml", "json"}
DELIMITADORES_POSIBLES = [";", ",", "|", "\t"]
TIPOS_DELIMITADOS = {"csv", "txt"}
CHUNK_SIZE_DEFAULT = 10000


def detectar_tipo(nombre: str) -> str:
    extension = Path(nombre).suffix.lower().lstrip(".")
    if extension not in EXTENSIONES_SOPORTADAS:
        raise ValueError(f"Formato no soportado: {extension}")
    return extension


def detectar_codificacion(ruta: Path) -> str:
    with ruta.open("rb") as handle:
        muestra = handle.read(65536)
    resultado = chardet.detect(muestra)
    codificacion = resultado.get("encoding") or "UTF-8"
    normalizada = codificacion.upper().replace("_", "-")
    if normalizada in {"UTF-8", "ASCII"}:
        return "UTF-8"
    if normalizada in {"ISO-8859-1", "LATIN-1", "LATIN1"}:
        return "Latin1"
    if normalizada in {"WINDOWS-1252", "CP1252"}:
        return "Windows-1252"
    return "UTF-8"


def detectar_delimitador(ruta: Path, codificacion: str) -> str:
    encoding = _mapear_codificacion(codificacion)
    with ruta.open("r", encoding=encoding, errors="replace") as handle:
        muestra = handle.read(8192)
    if not muestra:
        return ","
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters="".join(DELIMITADORES_POSIBLES))
        if dialecto.delimiter in DELIMITADORES_POSIBLES:
            return dialecto.delimiter
    except csv.Error:
        pass
    conteos = {delim: muestra.count(delim) for delim in DELIMITADORES_POSIBLES}
    return max(conteos, key=conteos.get) if any(conteos.values()) else ","


def _mapear_codificacion(codificacion: str) -> str:
    tabla = {"UTF-8": "utf-8", "Latin1": "latin-1", "Windows-1252": "cp1252"}
    return tabla.get(codificacion, "utf-8")


def leer_archivo(
    ruta: Path,
    tipo: str,
    delimitador: str,
    codificacion: str,
    tiene_encabezados: bool,
) -> tuple[list[str], list[dict[str, Any]]]:
    encoding = _mapear_codificacion(codificacion)
    match tipo:
        case "csv" | "txt":
            return _leer_delimitado(ruta, delimitador, encoding, tiene_encabezados)
        case "xlsx":
            return _leer_xlsx(ruta, tiene_encabezados)
        case "json":
            return _leer_json(ruta, encoding)
        case "xml":
            return _leer_xml(ruta, encoding)
        case _:
            raise ValueError(f"Tipo no soportado: {tipo}")


def _leer_delimitado(
    ruta: Path,
    delimitador: str,
    encoding: str,
    tiene_encabezados: bool,
) -> tuple[list[str], list[dict[str, Any]]]:
    header: int | None = 0 if tiene_encabezados else None
    dataframe = pd.read_csv(
        ruta,
        sep=delimitador,
        encoding=encoding,
        header=header,
        dtype=str,
        keep_default_na=False,
        na_values=[""],
        engine="python",
    )
    return _dataframe_a_registros(dataframe, tiene_encabezados)


def _leer_xlsx(
    ruta: Path, tiene_encabezados: bool
) -> tuple[list[str], list[dict[str, Any]]]:
    header: int | None = 0 if tiene_encabezados else None
    dataframe = pd.read_excel(ruta, header=header, dtype=str, engine="openpyxl")
    return _dataframe_a_registros(dataframe, tiene_encabezados)


def _leer_json(ruta: Path, encoding: str) -> tuple[list[str], list[dict[str, Any]]]:
    with ruta.open("r", encoding=encoding) as handle:
        datos = json.load(handle)
    if isinstance(datos, dict):
        for valor in datos.values():
            if isinstance(valor, list):
                datos = valor
                break
    if not isinstance(datos, list) or not datos:
        return [], []
    columnas: list[str] = []
    for registro in datos:
        if isinstance(registro, dict):
            for clave in registro.keys():
                if clave not in columnas:
                    columnas.append(clave)
    filas = [
        {col: _a_texto(reg.get(col)) for col in columnas}
        for reg in datos
        if isinstance(reg, dict)
    ]
    return columnas, filas


def _leer_xml(ruta: Path, encoding: str) -> tuple[list[str], list[dict[str, Any]]]:
    tree = ET.parse(ruta)
    raiz = tree.getroot()
    registros = list(raiz)
    if not registros:
        return [], []
    columnas: list[str] = []
    filas: list[dict[str, Any]] = []
    for elemento in registros:
        fila: dict[str, Any] = {}
        for hijo in elemento:
            clave = hijo.tag
            if clave not in columnas:
                columnas.append(clave)
            fila[clave] = _a_texto(hijo.text)
        for atributo, valor in elemento.attrib.items():
            if atributo not in columnas:
                columnas.append(atributo)
            fila[atributo] = _a_texto(valor)
        filas.append(fila)
    filas_normalizadas = [{col: fila.get(col) for col in columnas} for fila in filas]
    return columnas, filas_normalizadas


def _dataframe_a_registros(
    dataframe: pd.DataFrame, tiene_encabezados: bool
) -> tuple[list[str], list[dict[str, Any]]]:
    if not tiene_encabezados:
        dataframe.columns = [f"columna_{i + 1}" for i in range(len(dataframe.columns))]
    columnas = [str(col) for col in dataframe.columns]
    dataframe = dataframe.where(dataframe.notna(), None)
    filas = [
        {col: _a_texto(valor) for col, valor in registro.items()}
        for registro in dataframe.to_dict(orient="records")
    ]
    return columnas, filas


def _a_texto(valor: Any) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None
    texto = str(valor).strip()
    return texto if texto else None


def contar_lineas(ruta: Path) -> int:
    total = 0
    with ruta.open("rb") as handle:
        for _ in handle:
            total += 1
    return total


def es_tipo_delimitado(tipo: str) -> bool:
    return tipo in TIPOS_DELIMITADOS


def leer_archivo_chunks(
    ruta: Path,
    tipo: str,
    delimitador: str,
    codificacion: str,
    tiene_encabezados: bool,
    chunksize: int = CHUNK_SIZE_DEFAULT,
) -> Iterator[tuple[list[str], list[dict[str, Any]]]]:
    encoding = _mapear_codificacion(codificacion)
    if tipo in TIPOS_DELIMITADOS:
        yield from _leer_delimitado_chunks(
            ruta, delimitador, encoding, tiene_encabezados, chunksize
        )
        return
    columnas, filas = leer_archivo(
        ruta, tipo, delimitador, codificacion, tiene_encabezados
    )
    if not filas:
        return
    for inicio in range(0, len(filas), chunksize):
        yield columnas, filas[inicio : inicio + chunksize]


def _leer_delimitado_chunks(
    ruta: Path,
    delimitador: str,
    encoding: str,
    tiene_encabezados: bool,
    chunksize: int,
) -> Iterator[tuple[list[str], list[dict[str, Any]]]]:
    header: int | None = 0 if tiene_encabezados else None
    iterador = pd.read_csv(
        ruta,
        sep=delimitador,
        encoding=encoding,
        encoding_errors="replace",
        header=header,
        dtype=str,
        keep_default_na=False,
        na_values=[""],
        engine="c",
        chunksize=chunksize,
        on_bad_lines="skip",
    )
    for chunk in iterador:
        yield _dataframe_a_registros(chunk, tiene_encabezados)
