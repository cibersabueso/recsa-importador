from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from psycopg import Connection

from models.job import JobPayload
from models.resultado import ResultadoProceso

ESTADOS_VALIDOS: tuple[str, ...] = (
    "encolado",
    "iniciado",
    "procesando",
    "completado",
    "error",
    "fallido",
)


def _archivos_metadata(payload: JobPayload) -> list[dict[str, Any]]:
    metadata: list[dict[str, Any]] = []
    for archivo in payload.archivos:
        entrada: dict[str, Any] = {
            "nombre": archivo.nombre,
            "ruta": archivo.ruta,
            "orden": archivo.orden,
        }
        try:
            ruta = Path(archivo.ruta)
            if ruta.exists():
                entrada["tamano_bytes"] = ruta.stat().st_size
        except OSError:
            pass
        metadata.append(entrada)
    return metadata


def registrar_inicio(
    conn: Connection,
    job_id: str,
    payload: JobPayload,
    config_path: str,
    grupo_prueba: str | None = None,
    estado: str = "iniciado",
) -> None:
    archivos_meta = _archivos_metadata(payload)
    proceso = payload.proceso
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO cargas_jobs (
                job_id, empresa, tipo_carga, tipo_proceso, nombre_interfaz,
                responsable, grupo_prueba, estado, archivos_procesados, config_path
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                job_id,
                proceso.empresa,
                proceso.tipo_carga,
                proceso.tipo_proceso,
                proceso.nombre_interfaz,
                proceso.responsable,
                grupo_prueba,
                estado,
                json.dumps(archivos_meta, ensure_ascii=False),
                config_path,
            ),
        )
    conn.commit()


def registrar_procesando(conn: Connection, job_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE cargas_jobs
            SET estado = %s,
                iniciado_en = NOW()
            WHERE job_id = %s
            """,
            ("procesando", job_id),
        )
    conn.commit()


def registrar_fin(
    conn: Connection,
    job_id: str,
    resultado: ResultadoProceso,
    duracion_segundos: int,
) -> None:
    estado = "completado" if resultado.estado == "completado" else "error"
    error_mensaje = " | ".join(resultado.errores) if resultado.errores else None
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE cargas_jobs
            SET estado = %s,
                terminado_en = NOW(),
                duracion_segundos = %s,
                total_filas = %s,
                filas_validas = %s,
                filas_con_error = %s,
                duplicados = %s,
                sin_match = %s,
                error_mensaje = %s
            WHERE job_id = %s
            """,
            (
                estado,
                duracion_segundos,
                resultado.total_filas,
                resultado.filas_validas,
                resultado.filas_con_error,
                resultado.duplicados,
                resultado.sin_match,
                error_mensaje,
                job_id,
            ),
        )
    conn.commit()


def registrar_fallido(conn: Connection, job_id: str, motivo: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE cargas_jobs
            SET estado = %s,
                terminado_en = NOW(),
                error_mensaje = %s
            WHERE job_id = %s
            """,
            ("fallido", motivo, job_id),
        )
    conn.commit()


COLUMNAS_RESUMEN: tuple[str, ...] = (
    "job_id",
    "empresa",
    "tipo_carga",
    "tipo_proceso",
    "nombre_interfaz",
    "responsable",
    "grupo_prueba",
    "estado",
    "iniciado_en",
    "terminado_en",
    "duracion_segundos",
    "total_filas",
    "filas_validas",
    "filas_con_error",
    "duplicados",
    "sin_match",
    "error_mensaje",
    "config_path",
)


def _fila_a_dict(fila: tuple[Any, ...]) -> dict[str, Any]:
    resultado: dict[str, Any] = {}
    for clave, valor in zip(COLUMNAS_RESUMEN, fila):
        if isinstance(valor, datetime):
            resultado[clave] = valor.isoformat()
        else:
            resultado[clave] = valor
    return resultado


def consultar_job(conn: Connection, job_id: str) -> dict[str, Any] | None:
    columnas_sql = ", ".join(COLUMNAS_RESUMEN)
    sql = f"SELECT {columnas_sql} FROM cargas_jobs WHERE job_id = %s"
    with conn.cursor() as cur:
        cur.execute(sql, (job_id,))
        fila = cur.fetchone()
    if fila is None:
        return None
    return _fila_a_dict(fila)


def listar_jobs(
    conn: Connection,
    grupo: str | None = None,
    estado: str | None = None,
) -> list[dict[str, Any]]:
    columnas_sql = ", ".join(COLUMNAS_RESUMEN)
    where: list[str] = []
    params: list[Any] = []
    if grupo is not None:
        where.append("grupo_prueba = %s")
        params.append(grupo)
    if estado is not None:
        where.append("estado = %s")
        params.append(estado)
    sql = f"SELECT {columnas_sql} FROM cargas_jobs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY iniciado_en DESC"
    with conn.cursor() as cur:
        cur.execute(sql, params)
        filas = cur.fetchall()
    return [_fila_a_dict(fila) for fila in filas]
