from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from psycopg import Connection

from db.conversiones import to_date_ddmmyyyy, to_decimal, to_int, to_text
from db.db_config import DBConfig, resolver_db


COLUMNAS_CARGAS: tuple[str, ...] = (
    "job_id",
    "root_cliente",
    "nombre_completo",
    "direccion",
    "telefono_principal",
    "telefono_secundario",
    "email",
    "monto_deuda_original",
    "monto_deuda_actual",
    "fecha_vencimiento",
    "numero_documento",
    "producto",
    "sucursal_origen",
    "dias_mora",
    "tramo_mora",
)

LIMITES_TEXTO: dict[str, int] = {
    "root_cliente": 50,
    "nombre_completo": 200,
    "telefono_principal": 30,
    "telefono_secundario": 30,
    "email": 150,
    "numero_documento": 100,
    "producto": 100,
    "sucursal_origen": 100,
    "tramo_mora": 50,
}

CAMPOS_DECIMAL: frozenset[str] = frozenset({"monto_deuda_original", "monto_deuda_actual"})
CAMPOS_FECHA: frozenset[str] = frozenset({"fecha_vencimiento"})
CAMPOS_INT: frozenset[str] = frozenset({"dias_mora"})


def get_connection(db_config: DBConfig | None = None) -> Connection:
    if db_config is None:
        host = os.environ.get("POSTGRES_HOST", "localhost")
        port = int(os.environ.get("POSTGRES_PORT", "5432"))
        user = os.environ.get("POSTGRES_USER", "recsa")
        password = os.environ.get("POSTGRES_PASSWORD", "recsa123")
        dbname = os.environ.get("POSTGRES_DB", "recsa_cargas")
    else:
        host = db_config.host
        port = db_config.port
        user = db_config.user
        password = db_config.password
        dbname = db_config.database
    return psycopg.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname,
        autocommit=False,
    )


def ensure_schema(db_config: DBConfig | None = None) -> None:
    schema_path = Path(__file__).parent / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    with get_connection(db_config) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


def ensure_schema_para_pais(pais: str | None) -> DBConfig:
    db_config = resolver_db(pais)
    ensure_schema(db_config)
    return db_config


def _convertir_fila(
    job_id: str, fila: dict[str, str | None]
) -> tuple[str | Decimal | date | int | None, ...]:
    valores: list[Any] = []
    for columna in COLUMNAS_CARGAS:
        if columna == "job_id":
            valores.append(job_id)
            continue
        crudo = fila.get(columna)
        if columna in CAMPOS_DECIMAL:
            valores.append(to_decimal(crudo))
        elif columna in CAMPOS_FECHA:
            valores.append(to_date_ddmmyyyy(crudo))
        elif columna in CAMPOS_INT:
            valores.append(to_int(crudo))
        else:
            valores.append(to_text(crudo, LIMITES_TEXTO.get(columna)))
    return tuple(valores)


class BulkWriter:
    def __init__(self, conn: Connection, job_id: str, batch_size: int = 5000) -> None:
        self._conn: Connection = conn
        self._job_id: str = job_id
        self._batch_size: int = batch_size
        self._buffer: list[dict[str, str | None]] = []
        self._cerrado: bool = False

    def write(self, filas: list[dict[str, str | None]]) -> None:
        if self._cerrado:
            raise RuntimeError("BulkWriter ya fue cerrado")
        if not filas:
            return
        self._buffer.extend(filas)
        while len(self._buffer) >= self._batch_size:
            lote = self._buffer[: self._batch_size]
            del self._buffer[: self._batch_size]
            self._flush(lote)

    def close(self) -> None:
        if self._cerrado:
            return
        if self._buffer:
            pendientes = self._buffer
            self._buffer = []
            self._flush(pendientes)
        self._cerrado = True

    def _flush(self, lote: list[dict[str, str | None]]) -> None:
        if not lote:
            return
        columnas = ", ".join(COLUMNAS_CARGAS)
        sentencia = f"COPY cargas ({columnas}) FROM STDIN"
        with self._conn.cursor() as cur:
            with cur.copy(sentencia) as copy:
                for fila in lote:
                    copy.write_row(_convertir_fila(self._job_id, fila))
        self._conn.commit()
