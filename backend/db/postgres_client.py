from __future__ import annotations

import logging
import os
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from psycopg import Connection, sql

from db.conversiones import to_date_ddmmyyyy, to_decimal, to_int, to_text
from db.db_config import DBConfig, resolver_db

logger = logging.getLogger("recsa.db")

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

COLUMNAS_VISTA_UNIFICADA: tuple[str, ...] = (
    "id",
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
    "fecha_carga",
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

VISTA_UNIFICADA: str = "cargas_unificada"
PREFIJO_TABLA_CLIENTE: str = "cargas_"
TABLA_METADATOS_JOBS: str = "cargas_jobs"
PATRON_NOMBRE_TABLA: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9_]{0,62}$")

SCHEMA_JOBS_PATH: Path = Path(__file__).parent / "schema_jobs.sql"
SCHEMA_TEMPLATE_PATH: Path = Path(__file__).parent / "schema_template.sql"


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
    sql_text = SCHEMA_JOBS_PATH.read_text(encoding="utf-8")
    with get_connection(db_config) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_text)
        conn.commit()


def ensure_schema_para_pais(pais: str | None) -> DBConfig:
    db_config = resolver_db(pais)
    ensure_schema(db_config)
    return db_config


def _validar_nombre_tabla(nombre_tabla: str) -> None:
    if not PATRON_NOMBRE_TABLA.match(nombre_tabla):
        raise ValueError(
            f"Nombre de tabla inválido: '{nombre_tabla}'. Debe matchear "
            "^[a-z][a-z0-9_]{0,62}$"
        )
    if not nombre_tabla.startswith(PREFIJO_TABLA_CLIENTE):
        raise ValueError(
            f"Nombre de tabla debe iniciar con '{PREFIJO_TABLA_CLIENTE}': "
            f"'{nombre_tabla}'"
        )
    if nombre_tabla == TABLA_METADATOS_JOBS:
        raise ValueError(
            f"'{TABLA_METADATOS_JOBS}' está reservada para metadatos, no para cargas"
        )


def _tabla_existe(conn: Connection, nombre_tabla: str) -> bool:
    consulta = (
        "SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = %s"
    )
    with conn.cursor() as cur:
        cur.execute(consulta, (nombre_tabla,))
        return cur.fetchone() is not None


def ensure_tabla_cliente(conn: Connection, nombre_tabla: str) -> bool:
    _validar_nombre_tabla(nombre_tabla)
    ya_existia = _tabla_existe(conn, nombre_tabla)
    plantilla = SCHEMA_TEMPLATE_PATH.read_text(encoding="utf-8")
    ddl = plantilla.replace("{nombre_tabla}", nombre_tabla)
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()
    if not ya_existia:
        logger.info("Tabla creada para nuevo cliente: %s", nombre_tabla)
    return not ya_existia


def _listar_tablas_cargas(conn: Connection) -> list[str]:
    consulta = (
        "SELECT tablename FROM pg_tables "
        "WHERE schemaname = 'public' AND tablename LIKE %s AND tablename <> %s "
        "ORDER BY tablename"
    )
    with conn.cursor() as cur:
        cur.execute(consulta, (f"{PREFIJO_TABLA_CLIENTE}%", TABLA_METADATOS_JOBS))
        return [str(fila[0]) for fila in cur.fetchall()]


def regenerar_vista_cargas_unificada(conn: Connection) -> int:
    tablas = _listar_tablas_cargas(conn)
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("DROP VIEW IF EXISTS {}").format(sql.Identifier(VISTA_UNIFICADA))
        )
        if tablas:
            partes: list[sql.Composable] = []
            columnas_select = sql.SQL(", ").join(
                sql.Identifier(c) for c in COLUMNAS_VISTA_UNIFICADA
            )
            for tabla in tablas:
                origen = tabla[len(PREFIJO_TABLA_CLIENTE):]
                partes.append(
                    sql.SQL("SELECT {cols}, {origen} AS tabla_origen FROM {tabla}").format(
                        cols=columnas_select,
                        origen=sql.Literal(origen),
                        tabla=sql.Identifier(tabla),
                    )
                )
            cuerpo = sql.SQL(" UNION ALL ").join(partes)
            cur.execute(
                sql.SQL("CREATE VIEW {} AS {}").format(
                    sql.Identifier(VISTA_UNIFICADA), cuerpo
                )
            )
    conn.commit()
    logger.info(
        "Vista cargas_unificada regenerada con %d tablas", len(tablas)
    )
    return len(tablas)


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
    def __init__(
        self,
        conn: Connection,
        job_id: str,
        nombre_tabla: str,
        batch_size: int = 5000,
    ) -> None:
        _validar_nombre_tabla(nombre_tabla)
        self._conn: Connection = conn
        self._job_id: str = job_id
        self._nombre_tabla: str = nombre_tabla
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
        sentencia = sql.SQL("COPY {tabla} ({cols}) FROM STDIN").format(
            tabla=sql.Identifier(self._nombre_tabla),
            cols=sql.SQL(", ").join(sql.Identifier(c) for c in COLUMNAS_CARGAS),
        )
        with self._conn.cursor() as cur:
            with cur.copy(sentencia) as copy:
                for fila in lote:
                    copy.write_row(_convertir_fila(self._job_id, fila))
        self._conn.commit()
