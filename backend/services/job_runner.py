from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Literal

from psycopg import Connection

from db.db_config import DBConfig
from db.postgres_client import ensure_schema_para_pais, get_connection
from models.job import JobPayload
from models.resultado import ResultadoProceso
from services import job_registry, worker_service
from services.progress_tracker import FaseRegistro, ProgressTracker
from services.report_html import (
    consultar_calidad_datos,
    consultar_muestra,
    generar_reporte_html,
)
from services.validador_job import formatear_errores, validar_job

ModoRegistro = Literal["nuevo", "actualizar"]


def _generar_reporte_seguro(
    *,
    job_id: str,
    payload: JobPayload,
    resultado: ResultadoProceso,
    fases: list[FaseRegistro],
    grupo_prueba: str | None,
    pais: str | None,
    conn: Connection | None,
    logger: logging.Logger,
) -> Path | None:
    try:
        if resultado.estado == "completado" and conn is not None:
            calidad = consultar_calidad_datos(conn, job_id)
            muestra = consultar_muestra(conn, job_id, 20)
        else:
            calidad = None
            muestra = []
        ruta_html = generar_reporte_html(
            job_id=job_id,
            payload=payload,
            resultado=resultado,
            fases=fases,
            datos_muestra=muestra,
            calidad=calidad,
            grupo_prueba=grupo_prueba,
            pais=pais,
        )
        logger.info("Reporte HTML generado: %s", ruta_html)
        return ruta_html
    except Exception as error:  # noqa: BLE001
        logger.warning("No se pudo generar reporte HTML: %s", error)
        return None


def registrar_rechazo_validacion(
    *,
    job_id: str,
    payload: JobPayload,
    config_path: str | None,
    grupo_prueba: str | None,
    errores: list[str],
    logger: logging.Logger,
    ya_registrado: bool,
    conn: Connection | None = None,
) -> tuple[ResultadoProceso, Path | None, DBConfig]:
    pais = payload.proceso.pais
    db_config = ensure_schema_para_pais(pais)
    own_conn = conn is None
    if own_conn:
        conn = get_connection(db_config)
    resultado = ResultadoProceso(job_id=job_id, estado="error", errores=list(errores))
    ruta_html: Path | None = None
    try:
        if not ya_registrado:
            job_registry.registrar_inicio(
                conn,
                job_id,
                payload,
                config_path or "",
                grupo_prueba=grupo_prueba,
                estado="iniciado",
            )
        job_registry.registrar_fin(conn, job_id, resultado, 0)
        logger.error(
            "Job %s rechazado por validación: %s",
            job_id,
            formatear_errores(errores),
        )
        ruta_html = _generar_reporte_seguro(
            job_id=job_id,
            payload=payload,
            resultado=resultado,
            fases=[],
            grupo_prueba=grupo_prueba,
            pais=pais,
            conn=None,
            logger=logger,
        )
    finally:
        if own_conn and conn is not None:
            conn.close()
    return resultado, ruta_html, db_config


def ejecutar_postgres(
    *,
    job_id: str,
    payload: JobPayload,
    config_path: str,
    grupo_prueba: str | None,
    nombres_por_archivo: dict[str, list[str]] | None,
    progress: ProgressTracker,
    logger: logging.Logger,
    modo_registro: ModoRegistro = "nuevo",
) -> tuple[ResultadoProceso, float, Path | None, DBConfig]:
    pais = payload.proceso.pais
    db_config = ensure_schema_para_pais(pais)
    conn = get_connection(db_config)
    resultado = ResultadoProceso(job_id=job_id, estado="procesando")
    transcurrido = 0.0
    ruta_html: Path | None = None
    try:
        if modo_registro == "nuevo":
            job_registry.registrar_inicio(
                conn,
                job_id,
                payload,
                config_path,
                grupo_prueba=grupo_prueba,
                estado="iniciado",
            )
        else:
            job_registry.registrar_procesando(conn, job_id)

        ok, errores_validacion = validar_job(payload, nombres_por_archivo)
        if not ok:
            logger.error(
                "Job %s rechazado por validación: %s",
                job_id,
                formatear_errores(errores_validacion),
            )
            resultado.estado = "error"
            resultado.errores = list(errores_validacion)
            job_registry.registrar_fin(conn, job_id, resultado, 0)
            ruta_html = _generar_reporte_seguro(
                job_id=job_id,
                payload=payload,
                resultado=resultado,
                fases=[],
                grupo_prueba=grupo_prueba,
                pais=pais,
                conn=None,
                logger=logger,
            )
            return resultado, 0.0, ruta_html, db_config

        t0 = time.monotonic()
        try:
            worker_service._ejecutar(
                payload,
                resultado,
                sink="postgres",
                logger=logger,
                nombres_por_archivo=nombres_por_archivo,
                progress=progress,
            )
            resultado.estado = "completado"
            resultado.progreso_porcentaje = 100
        except Exception as error:  # noqa: BLE001
            logger.exception("Job %s falló durante _ejecutar", job_id)
            resultado.estado = "error"
            resultado.errores.append(str(error))
        finally:
            progress.cerrar()
        transcurrido = time.monotonic() - t0
        duracion = int(transcurrido)
        job_registry.registrar_fin(conn, job_id, resultado, duracion)
        logger.info(
            "Job %s terminado en %ds, estado=%s", job_id, duracion, resultado.estado
        )
        ruta_html = _generar_reporte_seguro(
            job_id=job_id,
            payload=payload,
            resultado=resultado,
            fases=progress.fases,
            grupo_prueba=grupo_prueba,
            pais=pais,
            conn=conn,
            logger=logger,
        )
    finally:
        conn.close()
    return resultado, transcurrido, ruta_html, db_config
