from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path
from typing import Any

import yaml

from db.postgres_client import ensure_schema_para_pais, get_connection
from models.job import JobPayload
from services import job_registry, job_runner, queue_service, worker_service
from services._formato_tiempo import formatear_duracion
from services.job_logger import configurar_logger
from services.payload_builder import construir_payload
from services.progress_tracker import FaseRegistro, ProgressTracker
from services.validador_job import formatear_errores, validar_job


def _cargar_config(ruta: Path) -> dict[str, Any]:
    with ruta.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Config inválida en {ruta}: se esperaba un mapping en la raíz")
    return data


def _imprimir_reporte_tiempos(fases: list[FaseRegistro]) -> None:
    if not fases:
        return
    print()
    print("=== Reporte de tiempos ===")
    encabezados = ("Fase", "Duración", "Filas", "Vel.")
    filas: list[tuple[str, str, str, str]] = []
    total_filas = 0
    total_segundos = 0.0
    for fase in fases:
        duracion = formatear_duracion(fase.duracion_segundos)
        if fase.total > 0:
            filas_str = f"{fase.total:,}"
            total_filas += fase.total
        else:
            filas_str = "-"
        if fase.total > 0 and fase.duracion_segundos > 0:
            velocidad = f"{fase.total / fase.duracion_segundos:,.0f}/s"
        else:
            velocidad = "-"
        filas.append((fase.nombre, duracion, filas_str, velocidad))
        total_segundos += fase.duracion_segundos
    if total_segundos > 0 and total_filas > 0:
        total_vel = f"{total_filas / total_segundos:,.0f}/s"
    else:
        total_vel = "-"
    fila_total = (
        "TOTAL",
        formatear_duracion(total_segundos),
        f"{total_filas:,}" if total_filas > 0 else "-",
        total_vel,
    )

    columnas: list[list[str]] = list(
        list(c) for c in zip(*([encabezados] + filas + [fila_total]))
    )
    anchos = [max(len(v) for v in col) for col in columnas]
    sep = " "
    fmt = lambda valores: sep.join(
        v.ljust(anchos[i]) if i < 1 else v.ljust(anchos[i])
        for i, v in enumerate(valores)
    )
    print(fmt(encabezados))
    print(sep.join("-" * a for a in anchos))
    for fila in filas:
        print(fmt(fila))
    print("---")
    print(fmt(fila_total))
    print()


def _ejecutar_inline(
    job_id: str,
    payload: JobPayload,
    nombres_por_archivo: dict[str, list[str]],
    config_path: str,
    grupo_prueba: str | None,
) -> int:
    pais = payload.proceso.pais
    pais_label = pais.strip().upper() if pais else "default"
    logger = configurar_logger(job_id)
    logger.info("Iniciando job %s con config %s (modo inline)", job_id, config_path)
    logger.info(
        "Empresa: %s, país: %s, archivos: %d, grupo_prueba: %s",
        payload.proceso.empresa,
        pais_label,
        len(payload.archivos),
        grupo_prueba or "-",
    )

    ok_validacion, errores_validacion = validar_job(payload, nombres_por_archivo or None)
    if not ok_validacion:
        print("Carga rechazada por validación. Errores detectados:", file=sys.stderr)
        for err in errores_validacion:
            print(f"  - {err}", file=sys.stderr)
        resultado_rechazo, ruta_html_rechazo, db_config_rechazo = (
            job_runner.registrar_rechazo_validacion(
                job_id=job_id,
                payload=payload,
                config_path=config_path,
                grupo_prueba=grupo_prueba,
                errores=errores_validacion,
                logger=logger,
                ya_registrado=False,
            )
        )
        print()
        print(f"Job: {job_id}")
        print(f"Empresa: {payload.proceso.empresa}")
        print(f"País: {pais_label}")
        print(
            f"BD: {db_config_rechazo.host}:{db_config_rechazo.port}/{db_config_rechazo.database}"
        )
        print(f"Estado: ERROR (validación)")
        print(f"Mensaje: {formatear_errores(errores_validacion)}")
        print(f"Log: backend/logs/{job_id}.log")
        if ruta_html_rechazo is not None:
            print(f"Reporte HTML: {ruta_html_rechazo}")
        return 1

    total_estimado = worker_service._estimar_total_filas(payload.archivos, logger)
    secundarios = [a for a in payload.archivos if a.orden != 1]
    fase_total = 3 + len(secundarios) if secundarios else 2
    progress = ProgressTracker(
        total_estimado,
        "Procesando job",
        job_id=job_id,
        fase_total=fase_total,
    )

    resultado, transcurrido, ruta_html, db_config = job_runner.ejecutar_postgres(
        job_id=job_id,
        payload=payload,
        config_path=config_path,
        grupo_prueba=grupo_prueba,
        nombres_por_archivo=nombres_por_archivo or None,
        progress=progress,
        logger=logger,
        modo_registro="nuevo",
    )

    _imprimir_reporte_tiempos(progress.fases)

    print(f"Job: {job_id}")
    print(f"Empresa: {payload.proceso.empresa}")
    print(f"País: {pais_label}")
    print(f"BD: {db_config.host}:{db_config.port}/{db_config.database}")
    print(f"Grupo: {grupo_prueba or '-'}")
    print(f"Archivos: {len(payload.archivos)}")
    print(f"Total filas:  {resultado.total_filas}")
    print(f"Válidas:      {resultado.filas_validas}")
    print(f"Errores:      {resultado.filas_con_error}")
    print(f"Duplicados:   {resultado.duplicados}")
    print(f"Sin match:    {resultado.sin_match}")
    print(f"Tiempo:       {formatear_duracion(transcurrido)}")
    print(f"Resultado:    {resultado.archivo_resultado}")
    print(f"Log:          backend/logs/{job_id}.log")
    if ruta_html is not None:
        print(f"Reporte HTML: {ruta_html}")

    return 1 if resultado.estado == "error" else 0


def _ejecutar_async(
    job_id: str,
    payload: JobPayload,
    nombres_por_archivo: dict[str, list[str]],
    config_path: str,
    grupo_prueba: str | None,
) -> int:
    pais = payload.proceso.pais
    pais_label = pais.strip().upper() if pais else "default"
    logger = configurar_logger(job_id)
    logger.info(
        "Encolando job %s (config=%s, empresa=%s, país=%s, grupo=%s)",
        job_id,
        config_path,
        payload.proceso.empresa,
        pais_label,
        grupo_prueba or "-",
    )

    db_config = ensure_schema_para_pais(pais)
    conn = get_connection(db_config)
    try:
        job_registry.registrar_inicio(
            conn,
            job_id,
            payload,
            config_path,
            grupo_prueba=grupo_prueba,
            estado="encolado",
        )
    finally:
        conn.close()

    queue_service.encolar_job(
        payload,
        job_id=job_id,
        grupo_prueba=grupo_prueba,
        config_path=config_path,
        nombres_por_archivo=nombres_por_archivo or None,
    )

    logger.info(
        "Job %s encolado en BD %s (%s); esperando worker",
        job_id,
        db_config.database,
        pais_label,
    )

    print(f"Job encolado: {job_id}")
    print(f"Empresa: {payload.proceso.empresa}")
    print(f"País: {pais_label}")
    print(f"BD: {db_config.host}:{db_config.port}/{db_config.database}")
    print(f"Grupo: {grupo_prueba or '-'}")
    print(f"Archivos: {len(payload.archivos)}")
    print(f"Estado: encolado")
    print(f"Consultar en: /api/jobs/{job_id}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Procesa una carga RECSA desde un YAML",
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Ruta al archivo YAML de configuración",
    )
    parser.add_argument(
        "--grupo",
        type=str,
        default=None,
        help="Grupo de prueba (sobrescribe proceso.grupo_prueba del YAML)",
    )
    parser.add_argument(
        "--modo",
        choices=("inline", "async"),
        default="async",
        help="inline: procesa en este proceso; async: encola en Redis y termina",
    )
    args = parser.parse_args()

    if not args.config.exists():
        print(f"Config no encontrado: {args.config}", file=sys.stderr)
        sys.exit(1)

    try:
        config = _cargar_config(args.config)
        payload, nombres_por_archivo, grupo_yaml = construir_payload(config)
    except (ValueError, KeyError) as error:
        print(f"Config inválida: {error}", file=sys.stderr)
        sys.exit(1)

    grupo_prueba: str | None = args.grupo or grupo_yaml

    job_id = uuid.uuid4().hex
    config_path = str(args.config.resolve())

    if args.modo == "inline":
        codigo = _ejecutar_inline(
            job_id, payload, nombres_por_archivo, config_path, grupo_prueba
        )
    else:
        codigo = _ejecutar_async(
            job_id, payload, nombres_por_archivo, config_path, grupo_prueba
        )

    if codigo != 0:
        sys.exit(codigo)


if __name__ == "__main__":
    main()
