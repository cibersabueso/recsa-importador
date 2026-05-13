from __future__ import annotations

import csv
from pathlib import Path
from typing import Protocol, TextIO

from psycopg import Connection

from db.postgres_client import (
    BulkWriter,
    ensure_tabla_cliente,
    regenerar_vista_cargas_unificada,
)
from utils.validators import CAMPOS_ESTANDAR


class FilaSink(Protocol):
    def write(self, fila: dict[str, str | None]) -> None: ...

    def close(self) -> None: ...


class CsvSink:
    def __init__(self, archivo_salida: Path) -> None:
        self._handle: TextIO = archivo_salida.open(
            "w", encoding="utf-8", newline=""
        )
        self._writer: csv.DictWriter = csv.DictWriter(
            self._handle, fieldnames=CAMPOS_ESTANDAR, delimiter=";"
        )
        self._writer.writeheader()
        self._cerrado: bool = False

    def write(self, fila: dict[str, str | None]) -> None:
        self._writer.writerow(
            {campo: (fila.get(campo) or "") for campo in CAMPOS_ESTANDAR}
        )

    def close(self) -> None:
        if self._cerrado:
            return
        self._handle.close()
        self._cerrado = True


class PostgresSink:
    def __init__(
        self,
        conn: Connection,
        job_id: str,
        nombre_tabla: str,
        batch_size: int = 5000,
    ) -> None:
        ensure_tabla_cliente(conn, nombre_tabla)
        regenerar_vista_cargas_unificada(conn)
        self._nombre_tabla: str = nombre_tabla
        self._writer: BulkWriter = BulkWriter(
            conn, job_id, nombre_tabla, batch_size=batch_size
        )
        self._cerrado: bool = False

    @property
    def nombre_tabla(self) -> str:
        return self._nombre_tabla

    def write(self, fila: dict[str, str | None]) -> None:
        self._writer.write([fila])

    def close(self) -> None:
        if self._cerrado:
            return
        self._writer.close()
        self._cerrado = True
