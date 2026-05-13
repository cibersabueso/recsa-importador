from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import PlainTextResponse, RedirectResponse

from db.db_config import DBConfig, cargar_config, resolver_db
from db.postgres_client import ensure_schema_para_pais, get_connection
from services import job_registry, progress_reader, queue_service
from services.dashboard_html import (
    DASHBOARD_FILENAME,
    generar_dashboard,
)
from services.payload_builder import construir_payload

router = APIRouter(prefix="/api", tags=["jobs"])
logger = logging.getLogger("recsa.api.jobs")

LOGS_DIR: Path = Path(__file__).resolve().parent.parent / "logs"
REPORTES_DIR: Path = Path(__file__).resolve().parent.parent / "reportes"


def _configs_paises() -> list[tuple[str, DBConfig]]:
    try:
        paises, default = cargar_config()
    except FileNotFoundError:
        return [("default", resolver_db(None))]
    items: list[tuple[str, DBConfig]] = [
        (codigo, cfg) for codigo, cfg in paises.items()
    ]
    items.append(("default", default))
    return items


def _normalizar_pais(pais: str | None) -> str:
    if not pais:
        return "default"
    return pais.strip().upper() or "default"


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
def crear_job(body: dict[str, Any]) -> dict[str, Any]:
    """
    Encola un nuevo job de procesamiento. Body equivalente al YAML
    de configs (proceso + archivos[] con layouts y mapeos).
    """
    try:
        payload, nombres_por_archivo, grupo_yaml = construir_payload(body)
    except (ValueError, KeyError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payload inválido: {error}",
        ) from error

    grupo_body = body.get("grupo_prueba") if isinstance(body, dict) else None
    grupo_prueba = (
        grupo_body if isinstance(grupo_body, str) and grupo_body else grupo_yaml
    )

    pais = payload.proceso.pais
    pais_label = _normalizar_pais(pais)
    job_id = uuid.uuid4().hex

    db_config = ensure_schema_para_pais(pais)
    conn = get_connection(db_config)
    try:
        job_registry.registrar_inicio(
            conn,
            job_id,
            payload,
            config_path="",
            grupo_prueba=grupo_prueba,
            estado="encolado",
        )
    finally:
        conn.close()

    queue_service.encolar_job(
        payload,
        job_id=job_id,
        grupo_prueba=grupo_prueba,
        config_path="",
        nombres_por_archivo=nombres_por_archivo or None,
    )

    logger.info(
        "Job %s encolado vía REST (empresa=%s, pais=%s, grupo=%s)",
        job_id,
        payload.proceso.empresa,
        pais_label,
        grupo_prueba or "-",
    )

    return {
        "jobId": job_id,
        "estado": "encolado",
        "pais": pais_label,
        "consultarEn": f"/api/jobs/{job_id}",
    }


def _enriquecer(fila: dict[str, Any], pais_label: str) -> dict[str, Any]:
    fila["pais"] = pais_label
    return fila


@router.get("/jobs")
def listar_jobs(
    pais: str | None = Query(None, description="Filtrar por código de país"),
    grupo: str | None = Query(None, description="Filtrar por grupo de prueba"),
    estado: str | None = Query(None, description="Filtrar por estado"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """
    Lista jobs. Si `pais` se especifica, consulta solo esa BD.
    Sin `pais`, hace fan-out a todas las BDs configuradas y agrega.
    """
    if pais is not None:
        codigo = pais.strip().upper()
        try:
            db_config = resolver_db(codigo)
        except Exception as error:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"País inválido: {error}",
            ) from error
        configs: list[tuple[str, DBConfig]] = [(codigo, db_config)]
    else:
        configs = _configs_paises()

    todos: list[dict[str, Any]] = []
    for pais_codigo, cfg in configs:
        try:
            ensure_schema_para_pais(pais_codigo if pais_codigo != "default" else None)
            conn = get_connection(cfg)
            try:
                jobs = job_registry.listar_jobs(conn, grupo=grupo, estado=estado)
            finally:
                conn.close()
        except Exception as error:  # noqa: BLE001
            logger.warning(
                "No se pudo consultar BD '%s' (%s): %s",
                pais_codigo,
                cfg.database,
                error,
            )
            continue
        for fila in jobs:
            todos.append(_enriquecer(fila, pais_codigo))

    todos.sort(
        key=lambda j: j.get("iniciado_en") or "",
        reverse=True,
    )
    total = len(todos)
    paginados = todos[offset : offset + limit]
    return {
        "jobs": paginados,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/jobs/{job_id}")
def obtener_job(job_id: str) -> dict[str, Any]:
    """
    Devuelve los campos de cargas_jobs del job + país.
    Busca en todas las BDs hasta encontrarlo. 404 si no existe.
    """
    for pais_codigo, cfg in _configs_paises():
        try:
            ensure_schema_para_pais(pais_codigo if pais_codigo != "default" else None)
            conn = get_connection(cfg)
            try:
                fila = job_registry.consultar_job(conn, job_id)
            finally:
                conn.close()
        except Exception as error:  # noqa: BLE001
            logger.warning(
                "No se pudo consultar BD '%s' (%s): %s",
                pais_codigo,
                cfg.database,
                error,
            )
            continue
        if fila is not None:
            return _enriquecer(fila, pais_codigo)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Job no encontrado: {job_id}",
    )


@router.get(
    "/jobs/{job_id}/progreso",
    responses={
        200: {"description": "Progreso del job (vivo o snapshot final)"},
        404: {"description": "Job no encontrado en ninguna BD"},
    },
)
def obtener_progreso(job_id: str) -> dict[str, Any]:
    """
    Devuelve el progreso del job. Si está en estado 'procesando' lee el
    hash 'recsa:progress:{id}' de Redis (fase, %, velocidad, ETA). Si está
    en otro estado, devuelve los totales finales de cargas_jobs.
    """
    fila: dict[str, Any] | None = None
    pais_codigo = "default"
    for codigo, cfg in _configs_paises():
        try:
            ensure_schema_para_pais(codigo if codigo != "default" else None)
            conn = get_connection(cfg)
            try:
                fila = job_registry.consultar_job(conn, job_id)
            finally:
                conn.close()
        except Exception as error:  # noqa: BLE001
            logger.warning(
                "No se pudo consultar BD '%s' (%s): %s",
                codigo,
                cfg.database,
                error,
            )
            continue
        if fila is not None:
            pais_codigo = codigo
            break

    if fila is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job no encontrado: {job_id}",
        )

    estado = str(fila.get("estado") or "")
    respuesta: dict[str, Any] = {
        "job_id": job_id,
        "pais": pais_codigo,
        "estado": estado,
    }

    if estado == "procesando":
        progreso = progress_reader.leer_progreso(job_id)
        if progreso is None:
            respuesta.update(
                {
                    "fase_actual": None,
                    "fase_indice": 0,
                    "fase_total": 0,
                    "porcentaje_fase": 0.0,
                    "filas_procesadas": 0,
                    "filas_totales": 0,
                    "velocidad_filas_seg": 0,
                    "tiempo_transcurrido_seg": 0,
                    "tiempo_estimado_restante_seg": None,
                }
            )
        else:
            respuesta.update(progreso)
            respuesta["job_id"] = job_id
        return respuesta

    respuesta.update(
        {
            "iniciado_en": fila.get("iniciado_en"),
            "terminado_en": fila.get("terminado_en"),
            "duracion_segundos": fila.get("duracion_segundos"),
            "total_filas": fila.get("total_filas"),
            "filas_validas": fila.get("filas_validas"),
            "filas_con_error": fila.get("filas_con_error"),
            "duplicados": fila.get("duplicados"),
            "sin_match": fila.get("sin_match"),
            "error_mensaje": fila.get("error_mensaje"),
        }
    )
    return respuesta


@router.get(
    "/jobs/{job_id}/log",
    response_class=PlainTextResponse,
    responses={
        200: {"content": {"text/plain": {}}},
        404: {"description": "Log no encontrado"},
    },
)
def obtener_log(job_id: str) -> PlainTextResponse:
    """
    Devuelve el log del job como texto plano.
    """
    archivo = LOGS_DIR / f"{job_id}.log"
    if not archivo.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log no encontrado para job {job_id}",
        )
    contenido = archivo.read_text(encoding="utf-8", errors="replace")
    return PlainTextResponse(content=contenido)


@router.get(
    "/jobs/{job_id}/report",
    responses={
        302: {"description": "Redirige al HTML del reporte"},
        404: {"description": "Reporte no encontrado"},
    },
)
def obtener_reporte(job_id: str) -> RedirectResponse:
    """
    Redirige al HTML del reporte servido en /static/reportes/{job_id}.html.
    """
    archivo = REPORTES_DIR / f"{job_id}.html"
    if not archivo.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reporte HTML no encontrado para job {job_id}",
        )
    return RedirectResponse(
        url=f"/static/reportes/{job_id}.html",
        status_code=status.HTTP_302_FOUND,
    )


@router.get(
    "/dashboard",
    responses={
        302: {"description": "Redirige al HTML del dashboard regenerado"},
        500: {"description": "Error inesperado al generar el dashboard"},
    },
)
def obtener_dashboard() -> RedirectResponse:
    """
    Regenera el dashboard global (fan-out a todas las BDs configuradas)
    y redirige al HTML servido en /static/reportes/dashboard.html.
    Si una BD falla, el dashboard se genera igual con los países que sí
    responden y muestra una sección de advertencia con los errores.
    """
    try:
        generar_dashboard(REPORTES_DIR / DASHBOARD_FILENAME)
    except Exception as error:  # noqa: BLE001
        logger.exception("No se pudo generar el dashboard global")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo generar el dashboard: {error}",
        ) from error
    return RedirectResponse(
        url=f"/static/reportes/{DASHBOARD_FILENAME}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/health")
def health() -> dict[str, Any]:
    """
    Health check del motor: redis + cada BD configurada + cantidad de workers
    activos (claves recsa:processing:* en Redis).
    """
    redis_ok = queue_service.ping()
    paises_estado: list[dict[str, Any]] = []
    for pais_codigo, cfg in _configs_paises():
        estado_pais: dict[str, Any] = {
            "pais": pais_codigo,
            "db": cfg.database,
        }
        try:
            conn = get_connection(cfg)
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            finally:
                conn.close()
            estado_pais["estado"] = "ok"
        except Exception as error:  # noqa: BLE001
            estado_pais["estado"] = "error"
            estado_pais["error"] = str(error)
        paises_estado.append(estado_pais)

    workers_activos = 0
    cola_pendiente = 0
    workers_max: int | None = None
    if redis_ok:
        try:
            workers_activos = queue_service.contar_workers_activos()
        except Exception as error:  # noqa: BLE001
            logger.warning("No se pudo contar workers activos: %s", error)
        try:
            cola_pendiente = queue_service.tamano_cola()
        except Exception as error:  # noqa: BLE001
            logger.warning("No se pudo leer tamaño de cola: %s", error)
        try:
            meta = queue_service.get_supervisor_meta()
            if meta and meta.get("max_workers"):
                workers_max = int(meta["max_workers"])
        except Exception as error:  # noqa: BLE001
            logger.warning("No se pudo leer supervisor meta: %s", error)

    return {
        "estado": "ok",
        "servicio": "recsa-cargas",
        "redis": "ok" if redis_ok else "error",
        "paises": paises_estado,
        "cola_pendiente": cola_pendiente,
        "workers_activos": workers_activos,
        "workers_max": workers_max,
    }
