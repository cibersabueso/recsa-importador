from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Any

import redis
from pydantic import BaseModel

from models.job import EstadoJob, Job, JobPayload, JobResumen
from models.resultado import ResultadoProceso

logger = logging.getLogger("recsa.queue")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
PENDING_QUEUE_KEY = "recsa:queue:jobs"
FAILED_QUEUE_KEY = "recsa:queue:failed"
PROCESSING_KEY_PREFIX = "recsa:processing:"
JOB_KEY_PREFIX = "recsa:job:"
SUPERVISOR_META_KEY = "recsa:supervisor:meta"
DEQUEUE_TIMEOUT_SECONDS = 1
DEQUEUE_SEGURO_TIMEOUT_SECONDS = 5
SUPERVISOR_META_TTL_DEFAULT = 60

ESTADOS_VALIDOS: tuple[EstadoJob, ...] = (
    "encolado",
    "procesando",
    "completado",
    "error",
    "fallido",
)

_lock = Lock()
_client: redis.Redis | None = None


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}"


def processing_key(worker_id: str) -> str:
    return f"{PROCESSING_KEY_PREFIX}{worker_id}"


def inicializar() -> None:
    global _client
    with _lock:
        if _client is not None:
            return
        cliente = redis.from_url(REDIS_URL, decode_responses=True)
        cliente.ping()
        _client = cliente


def cerrar() -> None:
    global _client
    with _lock:
        if _client is None:
            return
        try:
            _client.close()
        finally:
            _client = None


def _cliente() -> redis.Redis:
    if _client is None:
        inicializar()
    assert _client is not None
    return _client


def ping() -> bool:
    try:
        return bool(_cliente().ping())
    except Exception:  # noqa: BLE001
        return False


def _serializar_para_redis(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, str):
        return valor
    if isinstance(valor, (bytes, bytearray)):
        return bytes(valor).decode("utf-8", errors="replace")
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, BaseModel):
        return valor.model_dump_json()
    if isinstance(valor, (dict, list, tuple, set)):
        plano = list(valor) if isinstance(valor, (set, tuple)) else valor
        return json.dumps(plano, ensure_ascii=False, default=str)
    return str(valor)


def _mapping_seguro(
    operacion: str, identificador: str, datos: dict[str, Any]
) -> dict[str, str]:
    mapping: dict[str, str] = {
        clave: _serializar_para_redis(valor)
        for clave, valor in datos.items()
        if valor is not None
    }
    omitidos = sorted(clave for clave, valor in datos.items() if valor is None)
    if omitidos:
        logger.debug(
            "%s %s: campos omitidos por None (no se persisten en Redis): %s",
            operacion,
            identificador,
            omitidos,
        )
    return mapping


def _hash_a_job(datos: dict[str, Any]) -> Job:
    payload_dict = json.loads(datos["payload"])
    resultado_raw = datos.get("resultado") or ""
    resultado: ResultadoProceso | None = None
    if resultado_raw:
        resultado = ResultadoProceso.model_validate(json.loads(resultado_raw))
    nombres_raw = datos.get("nombres_por_archivo") or ""
    nombres_por_archivo: dict[str, list[str]] | None = None
    if nombres_raw:
        decoded = json.loads(nombres_raw)
        if isinstance(decoded, dict) and decoded:
            nombres_por_archivo = {
                str(k): [str(x) for x in v] for k, v in decoded.items()
            }
    pais_raw = datos.get("pais") or ""
    grupo_raw = datos.get("grupo_prueba") or ""
    config_raw = datos.get("config_path") or ""
    return Job(
        id=datos["id"],
        status=datos["status"],
        payload=JobPayload.model_validate(payload_dict),
        resultado=resultado,
        pais=pais_raw or None,
        grupo_prueba=grupo_raw or None,
        config_path=config_raw or None,
        nombres_por_archivo=nombres_por_archivo,
        created_at=datos["created_at"],
        updated_at=datos["updated_at"],
    )


def _normalizar_pais(payload: JobPayload) -> str:
    pais = payload.proceso.pais
    if pais is None:
        return ""
    return pais.strip().upper()


def encolar_job(
    payload: JobPayload,
    job_id: str | None = None,
    grupo_prueba: str | None = None,
    config_path: str | None = None,
    nombres_por_archivo: dict[str, list[str]] | None = None,
) -> str:
    cliente = _cliente()
    job_id = job_id or uuid.uuid4().hex
    ahora = _ahora()
    pais = _normalizar_pais(payload)
    datos: dict[str, Any] = {
        "id": job_id,
        "status": "encolado",
        "payload": payload,
        "resultado": None,
        "pais": pais or None,
        "grupo_prueba": grupo_prueba,
        "config_path": config_path,
        "nombres_por_archivo": nombres_por_archivo or None,
        "created_at": ahora,
        "updated_at": ahora,
    }
    mapping = _mapping_seguro("encolar_job", job_id, datos)
    pipe = cliente.pipeline()
    pipe.hset(_job_key(job_id), mapping=mapping)
    pipe.lpush(PENDING_QUEUE_KEY, job_id)
    pipe.execute()
    return job_id


def enqueue(payload: JobPayload) -> Job:
    job_id = encolar_job(payload)
    job = obtener_job(job_id)
    assert job is not None
    return job


def dequeue() -> Job | None:
    cliente = _cliente()
    respuesta = cliente.brpop([PENDING_QUEUE_KEY], timeout=DEQUEUE_TIMEOUT_SECONDS)
    if respuesta is None:
        return None
    _, job_id = respuesta
    ahora = _ahora()
    clave = _job_key(job_id)
    if not cliente.exists(clave):
        return None
    cliente.hset(
        clave,
        mapping=_mapping_seguro(
            "dequeue", job_id, {"status": "procesando", "updated_at": ahora}
        ),
    )
    datos = cliente.hgetall(clave)
    if not datos:
        return None
    return _hash_a_job(datos)


def dequeue_seguro(
    worker_id: str, timeout: int = DEQUEUE_SEGURO_TIMEOUT_SECONDS
) -> str | None:
    cliente = _cliente()
    job_id = cliente.brpoplpush(
        PENDING_QUEUE_KEY, processing_key(worker_id), timeout=timeout
    )
    if job_id is None:
        return None
    return str(job_id)


def eliminar_de_processing(worker_id: str, job_id: str) -> None:
    cliente = _cliente()
    cliente.lrem(processing_key(worker_id), 1, job_id)


def jobs_en_processing(worker_id: str) -> list[str]:
    cliente = _cliente()
    return [str(x) for x in cliente.lrange(processing_key(worker_id), 0, -1)]


def reencolar_de_processing(worker_id: str) -> int:
    cliente = _cliente()
    pendientes = jobs_en_processing(worker_id)
    if not pendientes:
        return 0
    pipe = cliente.pipeline()
    for job_id in pendientes:
        pipe.lpush(PENDING_QUEUE_KEY, job_id)
        pipe.lrem(processing_key(worker_id), 1, job_id)
    pipe.execute()
    return len(pendientes)


def mover_a_failed(job_id: str, motivo: str) -> None:
    cliente = _cliente()
    entrada = json.dumps(
        {"job_id": job_id, "motivo": motivo, "ts": _ahora()}, ensure_ascii=False
    )
    pipe = cliente.pipeline()
    pipe.lpush(FAILED_QUEUE_KEY, entrada)
    pipe.hset(
        _job_key(job_id),
        mapping=_mapping_seguro(
            "mover_a_failed",
            job_id,
            {"status": "fallido", "updated_at": _ahora()},
        ),
    )
    pipe.execute()


def contar_workers_activos() -> int:
    cliente = _cliente()
    total = 0
    for _ in cliente.scan_iter(match=f"{PROCESSING_KEY_PREFIX}*"):
        total += 1
    return total


def tamano_cola() -> int:
    cliente = _cliente()
    return int(cliente.llen(PENDING_QUEUE_KEY))


def set_supervisor_meta(
    max_workers: int,
    min_workers: int,
    ttl_segundos: int = SUPERVISOR_META_TTL_DEFAULT,
) -> None:
    cliente = _cliente()
    datos: dict[str, Any] = {
        "max_workers": max_workers,
        "min_workers": min_workers,
        "updated_at": _ahora(),
    }
    mapping = _mapping_seguro("set_supervisor_meta", SUPERVISOR_META_KEY, datos)
    if not mapping:
        return
    pipe = cliente.pipeline()
    pipe.hset(SUPERVISOR_META_KEY, mapping=mapping)
    pipe.expire(SUPERVISOR_META_KEY, ttl_segundos)
    pipe.execute()


def get_supervisor_meta() -> dict[str, str] | None:
    cliente = _cliente()
    datos = cliente.hgetall(SUPERVISOR_META_KEY)
    if not datos:
        return None
    return {str(k): str(v) for k, v in datos.items()}


def clear_supervisor_meta() -> None:
    cliente = _cliente()
    cliente.delete(SUPERVISOR_META_KEY)


def update_status(
    job_id: str,
    status: EstadoJob,
    resultado: ResultadoProceso | None = None,
) -> Job | None:
    cliente = _cliente()
    clave = _job_key(job_id)
    if not cliente.exists(clave):
        return None
    datos: dict[str, Any] = {
        "status": status,
        "updated_at": _ahora(),
        "resultado": resultado,
    }
    mapping = _mapping_seguro("update_status", job_id, datos)
    if mapping:
        cliente.hset(clave, mapping=mapping)
    salida = cliente.hgetall(clave)
    if not salida:
        return None
    return _hash_a_job(salida)


def update_progreso(job_id: str, resultado: ResultadoProceso) -> None:
    cliente = _cliente()
    clave = _job_key(job_id)
    if not cliente.exists(clave):
        return
    datos: dict[str, Any] = {
        "resultado": resultado,
        "updated_at": _ahora(),
    }
    mapping = _mapping_seguro("update_progreso", job_id, datos)
    if not mapping:
        return
    cliente.hset(clave, mapping=mapping)


def obtener_job(job_id: str) -> Job | None:
    cliente = _cliente()
    datos = cliente.hgetall(_job_key(job_id))
    if not datos:
        return None
    return _hash_a_job(datos)


def listar_jobs() -> list[JobResumen]:
    cliente = _cliente()
    resumenes: list[JobResumen] = []
    for clave in cliente.scan_iter(match=f"{JOB_KEY_PREFIX}*"):
        datos = cliente.hgetall(clave)
        if not datos:
            continue
        payload_dict = json.loads(datos["payload"])
        proceso = payload_dict.get("proceso", {})
        archivos = payload_dict.get("archivos", [])
        resumenes.append(
            JobResumen(
                id=datos["id"],
                status=datos["status"],
                empresa=proceso.get("empresa", ""),
                tipo_carga=proceso.get("tipo_carga", ""),
                responsable=proceso.get("responsable", ""),
                total_archivos=len(archivos),
                created_at=datos["created_at"],
                updated_at=datos["updated_at"],
            )
        )
    resumenes.sort(key=lambda r: r.created_at, reverse=True)
    return resumenes
