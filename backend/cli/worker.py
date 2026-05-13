from __future__ import annotations

import argparse
import logging
import multiprocessing as mp
import os
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from db.postgres_client import ensure_schema_para_pais, get_connection
from services import job_registry, job_runner, queue_service
from services.job_logger import configurar_logger
from services.progress_tracker import ProgressTracker
from services.validador_job import formatear_errores, validar_job
from services import worker_service

WORKER_LOGS_DIR: Path = Path(__file__).resolve().parent.parent / "logs"

DEFAULT_MAX_WORKERS = 20
DEFAULT_MIN_WORKERS = 0
DEFAULT_CHECK_INTERVAL = 2
DEFAULT_DEQUEUE_TIMEOUT = 5
DEFAULT_IDLE_CYCLES = 6
SHUTDOWN_GRACE_SECONDS = 30


def _configurar_logger_worker(pid: int) -> logging.Logger:
    WORKER_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    archivo = WORKER_LOGS_DIR / f"worker_{pid}.log"
    log = logging.getLogger(f"recsa.worker.{pid}")
    log.setLevel(logging.INFO)
    log.propagate = False
    if log.handlers:
        return log
    formato = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = logging.FileHandler(archivo, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(formato)
    log.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(formato)
    log.addHandler(sh)
    return log


def _configurar_logger_supervisor() -> logging.Logger:
    log = logging.getLogger("recsa.supervisor")
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    log.propagate = False
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] supervisor: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    log.addHandler(handler)
    return log


def _registrar_fallido(job_id: str, motivo: str, log: logging.Logger) -> None:
    log.error("Job %s marcado como fallido: %s", job_id, motivo)
    queue_service.mover_a_failed(job_id, motivo)
    job = queue_service.obtener_job(job_id)
    if job is None:
        return
    pais = job.payload.proceso.pais
    try:
        db_config = ensure_schema_para_pais(pais)
        conn = get_connection(db_config)
        try:
            job_registry.registrar_fallido(conn, job_id, motivo)
        finally:
            conn.close()
    except Exception as error:  # noqa: BLE001
        log.exception(
            "No se pudo registrar fallido en Postgres para job %s: %s", job_id, error
        )


def _procesar_job_id(
    job_id: str, worker_id: str, log: logging.Logger
) -> None:
    job = queue_service.obtener_job(job_id)
    if job is None:
        log.warning("Job %s no existe en Redis; descartando", job_id)
        queue_service.eliminar_de_processing(worker_id, job_id)
        return

    payload = job.payload
    grupo_prueba = job.grupo_prueba
    config_path = job.config_path or ""
    nombres_por_archivo = job.nombres_por_archivo

    job_logger = configurar_logger(job_id)

    ok_validacion, errores_validacion = validar_job(payload, nombres_por_archivo)
    if not ok_validacion:
        log.error(
            "Job %s rechazado por validación: %s",
            job_id,
            formatear_errores(errores_validacion),
        )
        resultado_rechazo, _, _ = job_runner.registrar_rechazo_validacion(
            job_id=job_id,
            payload=payload,
            config_path=config_path,
            grupo_prueba=grupo_prueba,
            errores=errores_validacion,
            logger=job_logger,
            ya_registrado=True,
        )
        queue_service.update_status(job_id, "error", resultado_rechazo)
        queue_service.eliminar_de_processing(worker_id, job_id)
        return

    queue_service.update_status(job_id, "procesando")

    total_estimado = worker_service._estimar_total_filas(payload.archivos, job_logger)
    fase_total = _estimar_fase_total(payload)
    progress = ProgressTracker(
        total_estimado,
        f"Job {job_id[:8]}",
        job_id=job_id,
        fase_total=fase_total,
    )
    try:
        resultado, _, _, _ = job_runner.ejecutar_postgres(
            job_id=job_id,
            payload=payload,
            config_path=config_path,
            grupo_prueba=grupo_prueba,
            nombres_por_archivo=nombres_por_archivo,
            progress=progress,
            logger=job_logger,
            modo_registro="actualizar",
        )
        if resultado.estado == "completado":
            queue_service.update_status(job_id, "completado", resultado)
        else:
            queue_service.update_status(job_id, "error", resultado)
    except Exception as error:  # noqa: BLE001
        log.exception("Worker %s falló procesando job %s: %s", worker_id, job_id, error)
        _registrar_fallido(job_id, str(error), log)
        return
    finally:
        queue_service.eliminar_de_processing(worker_id, job_id)


def _estimar_fase_total(payload: object) -> int:
    archivos = getattr(payload, "archivos", [])
    if not archivos:
        return 2
    secundarios = [a for a in archivos if getattr(a, "orden", 1) != 1]
    if not secundarios:
        return 2
    return 3 + len(secundarios)


def _loop_worker(idx: int, dequeue_timeout: int, idle_cycles: int) -> None:
    pid = os.getpid()
    worker_id = str(pid)
    log = _configurar_logger_worker(pid)

    log.info(
        "Worker #%d (pid=%d) iniciado, dequeue_timeout=%ds, idle_cycles=%d",
        idx,
        pid,
        dequeue_timeout,
        idle_cycles,
    )

    stop_event = threading.Event()

    def _shutdown(signum: int, _frame: object) -> None:
        log.info("Worker #%d recibió señal %d, drenando...", idx, signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    queue_service.inicializar()

    pendientes = queue_service.reencolar_de_processing(worker_id)
    if pendientes > 0:
        log.warning(
            "Worker #%d reencoló %d job(s) huérfanos de processing", idx, pendientes
        )

    ciclos_vacios = 0

    while not stop_event.is_set():
        try:
            job_id = queue_service.dequeue_seguro(
                worker_id, timeout=dequeue_timeout
            )
        except Exception as error:  # noqa: BLE001
            log.exception("Worker #%d falló al hacer dequeue: %s", idx, error)
            time.sleep(1.0)
            continue

        if job_id is None:
            ciclos_vacios += 1
            if ciclos_vacios >= idle_cycles:
                log.info(
                    "Worker #%d sin trabajo durante %d ciclo(s) (%ds), terminando",
                    idx,
                    ciclos_vacios,
                    ciclos_vacios * dequeue_timeout,
                )
                break
            continue

        ciclos_vacios = 0
        log.info("Worker #%d tomó job %s", idx, job_id)
        try:
            _procesar_job_id(job_id, worker_id, log)
        except Exception as error:  # noqa: BLE001
            log.exception(
                "Worker #%d crash procesando %s: %s", idx, job_id, error
            )
            try:
                _registrar_fallido(job_id, f"crash: {error}", log)
            except Exception:  # noqa: BLE001
                log.exception("No se pudo marcar fallido tras crash")
            queue_service.eliminar_de_processing(worker_id, job_id)

    drenados = queue_service.reencolar_de_processing(worker_id)
    if drenados > 0:
        log.info("Worker #%d reencoló %d job(s) al apagarse", idx, drenados)
    queue_service.cerrar()
    log.info("Worker #%d (pid=%d) terminado", idx, pid)


def _decidir_spawn(
    cola: int, vivos: int, max_workers: int, min_workers: int
) -> int:
    objetivo = max(min_workers, min(max_workers, cola))
    if objetivo <= vivos:
        return 0
    return objetivo - vivos


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _supervisor(
    max_workers: int,
    min_workers: int,
    check_interval: int,
    dequeue_timeout: int,
    idle_cycles: int,
) -> None:
    log = _configurar_logger_supervisor()

    queue_service.inicializar()
    try:
        queue_service.set_supervisor_meta(
            max_workers,
            min_workers,
            ttl_segundos=max(check_interval * 3, 30),
        )
    except Exception as error:  # noqa: BLE001
        log.warning("No se pudo publicar supervisor meta inicial: %s", error)

    log.info(
        "Supervisor iniciado (max=%d, min=%d, check=%ds, dequeue=%ds, idle_cycles=%d)",
        max_workers,
        min_workers,
        check_interval,
        dequeue_timeout,
        idle_cycles,
    )

    procesos: list[mp.Process] = []
    detener = threading.Event()
    proximo_idx = 0

    def _spawn() -> mp.Process:
        nonlocal proximo_idx
        idx = proximo_idx
        proximo_idx += 1
        proceso = mp.Process(
            target=_loop_worker,
            args=(idx, dequeue_timeout, idle_cycles),
            name=f"recsa-worker-{idx}",
        )
        proceso.start()
        procesos.append(proceso)
        log.info("Spawn worker idx=%d pid=%s", idx, proceso.pid)
        return proceso

    def _shutdown(signum: int, _frame: object) -> None:
        log.info("Supervisor recibió señal %d, drenando workers...", signum)
        detener.set()
        for proceso in procesos:
            if proceso.is_alive() and proceso.pid is not None:
                try:
                    os.kill(proceso.pid, signal.SIGTERM)
                except OSError as error:
                    log.warning(
                        "No se pudo enviar SIGTERM a pid=%d: %s",
                        proceso.pid,
                        error,
                    )

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    for _ in range(min_workers):
        _spawn()

    inicio_idle: float | None = None

    while not detener.is_set():
        muertos: list[mp.Process] = []
        vivos_lista: list[mp.Process] = []
        for p in procesos:
            if p.is_alive():
                vivos_lista.append(p)
            else:
                muertos.append(p)
        for p in muertos:
            exitcode = p.exitcode
            motivo = "ok" if exitcode == 0 else f"exitcode={exitcode}"
            log.info("Reap worker pid=%s name=%s (%s)", p.pid, p.name, motivo)
        procesos[:] = vivos_lista

        try:
            cola = queue_service.tamano_cola()
        except Exception as error:  # noqa: BLE001
            log.warning("No se pudo leer tamaño de cola: %s", error)
            cola = 0

        vivos = len(procesos)
        nuevos = _decidir_spawn(cola, vivos, max_workers, min_workers)

        if cola > 0 and vivos == 0 and nuevos == 0:
            log.warning(
                "Cola=%d sin workers vivos pero spawn=0 (max=%d, min=%d)",
                cola,
                max_workers,
                min_workers,
            )

        if nuevos > 0:
            for _ in range(nuevos):
                _spawn()
            inicio_idle = None
            sys.stdout.write(
                f"[{_ts()}] cola={cola}  workers={vivos + nuevos}  "
                f"-> levantando {nuevos} nuevos\n"
            )
        elif cola == 0 and vivos == 0:
            ahora = time.monotonic()
            if inicio_idle is None:
                inicio_idle = ahora
                sys.stdout.write(
                    f"[{_ts()}] cola=0  workers=0  -> idle (inicio)\n"
                )
            else:
                segundos_idle = int(ahora - inicio_idle)
                sys.stdout.write(
                    f"[{_ts()}] cola=0  workers=0  -> idle ({segundos_idle}s)\n"
                )
        elif cola == 0:
            inicio_idle = None
            sys.stdout.write(
                f"[{_ts()}] cola=0  workers={vivos}  -> drenando\n"
            )
        else:
            inicio_idle = None
            if vivos >= max_workers:
                log.warning(
                    "Cola=%d con %d workers (saturado en max=%d)",
                    cola,
                    vivos,
                    max_workers,
                )
                estado = "saturado"
            else:
                estado = "estable"
            sys.stdout.write(
                f"[{_ts()}] cola={cola}  workers={vivos}  -> {estado}\n"
            )
        sys.stdout.flush()

        try:
            queue_service.set_supervisor_meta(
                max_workers,
                min_workers,
                ttl_segundos=max(check_interval * 3, 30),
            )
        except Exception as error:  # noqa: BLE001
            log.warning("No se pudo refrescar supervisor meta: %s", error)

        detener.wait(check_interval)

    log.info(
        "Supervisor: esperando workers hasta %ds...", SHUTDOWN_GRACE_SECONDS
    )
    deadline = time.monotonic() + SHUTDOWN_GRACE_SECONDS
    for proceso in procesos:
        if not proceso.is_alive():
            continue
        timeout = max(0.0, deadline - time.monotonic())
        proceso.join(timeout=timeout)
        if proceso.is_alive():
            log.warning(
                "Worker pid=%s colgado tras grace, force-kill", proceso.pid
            )
            proceso.terminate()
            proceso.join(timeout=5)

    for proceso in procesos:
        pid = proceso.pid
        if pid is None:
            continue
        try:
            cant = queue_service.reencolar_de_processing(str(pid))
            if cant > 0:
                log.warning(
                    "Drené %d job(s) huérfanos de pid=%d", cant, pid
                )
        except Exception as error:  # noqa: BLE001
            log.warning("No se pudo drenar pid=%s: %s", pid, error)

    try:
        queue_service.clear_supervisor_meta()
    except Exception as error:  # noqa: BLE001
        log.warning("No se pudo limpiar supervisor meta: %s", error)
    queue_service.cerrar()
    log.info("Supervisor apagado")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Supervisor de workers RECSA Cargas. Escala dinámicamente la "
            "cantidad de workers según el tamaño de la cola Redis."
        )
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help=f"Máximo de workers concurrentes (default {DEFAULT_MAX_WORKERS})",
    )
    parser.add_argument(
        "--min-workers",
        type=int,
        default=DEFAULT_MIN_WORKERS,
        help=f"Workers mínimos siempre vivos (default {DEFAULT_MIN_WORKERS})",
    )
    parser.add_argument(
        "--check-interval",
        type=int,
        default=DEFAULT_CHECK_INTERVAL,
        help=(
            f"Segundos entre chequeos de la cola "
            f"(default {DEFAULT_CHECK_INTERVAL})"
        ),
    )
    parser.add_argument(
        "--dequeue-timeout",
        type=int,
        default=DEFAULT_DEQUEUE_TIMEOUT,
        help=(
            f"Segundos del BRPOP del worker "
            f"(default {DEFAULT_DEQUEUE_TIMEOUT})"
        ),
    )
    parser.add_argument(
        "--idle-cycles",
        type=int,
        default=DEFAULT_IDLE_CYCLES,
        help=(
            f"Ciclos consecutivos sin job antes de que un worker termine "
            f"(default {DEFAULT_IDLE_CYCLES} = "
            f"{DEFAULT_IDLE_CYCLES * DEFAULT_DEQUEUE_TIMEOUT}s con dequeue por defecto)"
        ),
    )
    args = parser.parse_args()

    if args.max_workers < 1:
        print("--max-workers debe ser >= 1", file=sys.stderr)
        sys.exit(1)
    if args.min_workers < 0 or args.min_workers > args.max_workers:
        print(
            "--min-workers debe ser >= 0 y <= --max-workers", file=sys.stderr
        )
        sys.exit(1)
    if args.check_interval < 1:
        print("--check-interval debe ser >= 1", file=sys.stderr)
        sys.exit(1)
    if args.dequeue_timeout < 1:
        print("--dequeue-timeout debe ser >= 1", file=sys.stderr)
        sys.exit(1)
    if args.idle_cycles < 1:
        print("--idle-cycles debe ser >= 1", file=sys.stderr)
        sys.exit(1)

    print("Supervisor RECSA Cargas")
    print(f"  max_workers     = {args.max_workers}")
    print(f"  min_workers     = {args.min_workers}")
    print(f"  check_interval  = {args.check_interval}s")
    print(f"  dequeue_timeout = {args.dequeue_timeout}s")
    print(f"  idle_cycles     = {args.idle_cycles}")
    print(
        f"  idle_total      = "
        f"{args.idle_cycles * args.dequeue_timeout}s sin job antes de terminar"
    )
    print(f"  logs por worker = {WORKER_LOGS_DIR / 'worker_<pid>.log'}")
    print("  Ctrl+C para terminar")
    print()

    _supervisor(
        max_workers=args.max_workers,
        min_workers=args.min_workers,
        check_interval=args.check_interval,
        dequeue_timeout=args.dequeue_timeout,
        idle_cycles=args.idle_cycles,
    )


if __name__ == "__main__":
    main()
