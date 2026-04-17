from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Any

import redis

from models.job import EstadoJob, Job, JobPayload, JobResumen
from models.resultado import ResultadoProceso

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
PENDING_QUEUE_KEY = "recsa:jobs:pending"
JOB_KEY_PREFIX = "recsa:job:"
DEQUEUE_TIMEOUT_SECONDS = 1

_lock = Lock()
_client: redis.Redis | None = None


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}"


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


def _hash_a_job(datos: dict[str, Any]) -> Job:
    payload_dict = json.loads(datos["payload"])
    resultado_raw = datos.get("resultado") or ""
    resultado: ResultadoProceso | None = None
    if resultado_raw:
        resultado = ResultadoProceso.model_validate(json.loads(resultado_raw))
    return Job(
        id=datos["id"],
        status=datos["status"],
        payload=JobPayload.model_validate(payload_dict),
        resultado=resultado,
        created_at=datos["created_at"],
        updated_at=datos["updated_at"],
    )


def enqueue(payload: JobPayload) -> Job:
    cliente = _cliente()
    job_id = uuid.uuid4().hex
    ahora = _ahora()
    payload_json = payload.model_dump_json()
    pipe = cliente.pipeline()
    pipe.hset(
        _job_key(job_id),
        mapping={
            "id": job_id,
            "status": "pending",
            "payload": payload_json,
            "resultado": "",
            "created_at": ahora,
            "updated_at": ahora,
        },
    )
    pipe.lpush(PENDING_QUEUE_KEY, job_id)
    pipe.execute()
    return Job(
        id=job_id,
        status="pending",
        payload=payload,
        resultado=None,
        created_at=ahora,
        updated_at=ahora,
    )


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
    cliente.hset(clave, mapping={"status": "processing", "updated_at": ahora})
    datos = cliente.hgetall(clave)
    if not datos:
        return None
    return _hash_a_job(datos)


def update_status(
    job_id: str,
    status: EstadoJob,
    resultado: ResultadoProceso | None = None,
) -> Job | None:
    cliente = _cliente()
    clave = _job_key(job_id)
    if not cliente.exists(clave):
        return None
    ahora = _ahora()
    mapping: dict[str, str] = {"status": status, "updated_at": ahora}
    if resultado is not None:
        mapping["resultado"] = resultado.model_dump_json()
    cliente.hset(clave, mapping=mapping)
    datos = cliente.hgetall(clave)
    if not datos:
        return None
    return _hash_a_job(datos)


def update_progreso(job_id: str, resultado: ResultadoProceso) -> None:
    cliente = _cliente()
    clave = _job_key(job_id)
    if not cliente.exists(clave):
        return
    cliente.hset(
        clave,
        mapping={
            "resultado": resultado.model_dump_json(),
            "updated_at": _ahora(),
        },
    )


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
