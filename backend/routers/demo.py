from __future__ import annotations

import logging
import shutil
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from cli.layouts._loader import Layout, cargar_layout
from db.postgres_client import ensure_schema_para_pais, get_connection
from services import job_registry, worker_service
from services.job_logger import configurar_logger
from services.job_runner import ejecutar_postgres
from services.payload_builder import construir_payload
from services.progress_tracker import ProgressTracker
from services.validador_carga import validar_archivo

router = APIRouter(prefix="/api/demo", tags=["demo"])
logger = logging.getLogger("recsa.api.demo")

BACKEND_ROOT: Path = Path(__file__).resolve().parent.parent
UPLOADS_DEMO_DIR: Path = BACKEND_ROOT / "uploads_demo"
CONFIGS_DIR: Path = BACKEND_ROOT / "cli" / "configs"

CONFIGS_PERMITIDOS: tuple[str, ...] = (
    "movistar_sample",
    "movistar_full",
    "movistar_full_v2",
    "recsa_peru",
)

CHUNK_SIZE: int = 1024 * 1024
TMP_PREFIX: str = "recsa_demo_validar_"


@dataclass
class MatchResultado:
    asignacion: dict[str, UploadFile] = field(default_factory=dict)
    extras: list[UploadFile] = field(default_factory=list)
    faltantes: list[str] = field(default_factory=list)
    ambiguos: list[tuple[str, list[str]]] = field(default_factory=list)


@dataclass
class ValidacionArchivo:
    nombre: str
    nombre_subido: str | None
    layout: str | None
    obligatorio: bool
    valido: bool
    errores: list[str]
    warnings: list[str]


def _cargar_config_yaml(tipo_carga: str) -> dict[str, Any]:
    ruta = CONFIGS_DIR / f"{tipo_carga}.yml"
    if not ruta.exists():
        raise ValueError(f"Config no encontrado: {ruta}")
    with ruta.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Config '{tipo_carga}' inválido: se esperaba un mapping")
    return data


def _es_obligatorio(archivo_raw: dict[str, Any]) -> bool:
    if "obligatorio" in archivo_raw:
        return bool(archivo_raw.get("obligatorio"))
    return archivo_raw.get("orden") == 1


def _hacer_match_tolerante(
    archivos_subidos: list[UploadFile], rutas_config: list[str]
) -> MatchResultado:
    resultado = MatchResultado()
    subidos: list[tuple[str, str, UploadFile]] = []
    for upload in archivos_subidos:
        nombre = upload.filename or ""
        if not nombre:
            continue
        subidos.append((nombre, Path(nombre).stem.lower(), upload))

    config_items: list[tuple[str, str]] = [
        (Path(ruta).name, Path(ruta).stem.lower()) for ruta in rutas_config
    ]

    usados: set[int] = set()
    for nombre_config, stem_config in config_items:
        if not stem_config:
            resultado.faltantes.append(nombre_config)
            continue
        candidatos: list[int] = []
        for idx, (_, stem_subido, _) in enumerate(subidos):
            if idx in usados:
                continue
            if stem_subido in stem_config or stem_config in stem_subido:
                candidatos.append(idx)
        if not candidatos:
            resultado.faltantes.append(nombre_config)
            continue
        if len(candidatos) > 1:
            resultado.ambiguos.append(
                (nombre_config, [subidos[i][0] for i in candidatos])
            )
            continue
        idx_match = candidatos[0]
        usados.add(idx_match)
        resultado.asignacion[nombre_config] = subidos[idx_match][2]

    resultado.extras = [
        subidos[idx][2] for idx in range(len(subidos)) if idx not in usados
    ]
    return resultado


async def _guardar_archivo(upload: UploadFile, destino: Path) -> int:
    total = 0
    try:
        await upload.seek(0)
    except Exception:  # noqa: BLE001
        pass
    with destino.open("wb") as out:
        while True:
            chunk = await upload.read(CHUNK_SIZE)
            if not chunk:
                break
            out.write(chunk)
            total += len(chunk)
    return total


def _construir_warnings(layout: Layout) -> list[str]:
    warnings: list[str] = []
    if not layout.tiene_encabezados:
        warnings.append(
            f"Archivo sin cabeceras: el layout '{layout.nombre}' resuelve "
            f"columnas por posición"
        )
    return warnings


def _validar_uno(
    archivo_raw: dict[str, Any],
    upload: UploadFile | None,
    ruta_disco: Path | None,
    layouts_cache: dict[str, Layout],
) -> ValidacionArchivo:
    nombre_config = Path(str(archivo_raw.get("ruta", ""))).name or "(sin nombre)"
    layout_nombre_raw = archivo_raw.get("layout")
    layout_nombre = (
        layout_nombre_raw if isinstance(layout_nombre_raw, str) else None
    )
    obligatorio = _es_obligatorio(archivo_raw)
    nombre_subido = upload.filename if upload is not None else None

    if upload is None or ruta_disco is None:
        return ValidacionArchivo(
            nombre=nombre_config,
            nombre_subido=None,
            layout=layout_nombre,
            obligatorio=obligatorio,
            valido=False,
            errores=[
                f"No se subió un archivo que coincida con '{nombre_config}'"
            ],
            warnings=[],
        )

    if layout_nombre is None:
        return ValidacionArchivo(
            nombre=nombre_config,
            nombre_subido=nombre_subido,
            layout=None,
            obligatorio=obligatorio,
            valido=False,
            errores=[
                f"El archivo '{nombre_config}' del config no declara 'layout'"
            ],
            warnings=[],
        )

    try:
        if layout_nombre not in layouts_cache:
            layouts_cache[layout_nombre] = cargar_layout(layout_nombre)
        layout = layouts_cache[layout_nombre]
    except (ValueError, OSError) as error:
        return ValidacionArchivo(
            nombre=nombre_config,
            nombre_subido=nombre_subido,
            layout=layout_nombre,
            obligatorio=obligatorio,
            valido=False,
            errores=[f"Layout '{layout_nombre}' no se pudo cargar: {error}"],
            warnings=[],
        )

    ok, errores = validar_archivo(ruta_disco, layout)
    warnings = _construir_warnings(layout)

    return ValidacionArchivo(
        nombre=nombre_config,
        nombre_subido=nombre_subido,
        layout=layout_nombre,
        obligatorio=obligatorio,
        valido=ok,
        errores=list(errores),
        warnings=warnings,
    )


def _validar_archivos_guardados(
    archivos_config_raw: list[dict[str, Any]],
    asignacion: dict[str, UploadFile],
    rutas_finales: dict[str, Path],
    extras: list[UploadFile],
) -> list[ValidacionArchivo]:
    layouts_cache: dict[str, Layout] = {}
    resultados: list[ValidacionArchivo] = []

    for archivo_raw in archivos_config_raw:
        nombre_config = Path(str(archivo_raw.get("ruta", ""))).name
        upload = asignacion.get(nombre_config)
        ruta_disco = rutas_finales.get(nombre_config)
        resultados.append(
            _validar_uno(archivo_raw, upload, ruta_disco, layouts_cache)
        )

    for upload in extras:
        nombre = upload.filename or "(sin nombre)"
        resultados.append(
            ValidacionArchivo(
                nombre=nombre,
                nombre_subido=nombre,
                layout=None,
                obligatorio=False,
                valido=False,
                errores=[
                    f"El archivo '{nombre}' no coincide con ningún archivo "
                    f"esperado del config (matching case-insensitive substring)"
                ],
                warnings=[],
            )
        )
    return resultados


def _to_dict(v: ValidacionArchivo) -> dict[str, Any]:
    return {
        "nombre": v.nombre,
        "nombre_subido": v.nombre_subido,
        "layout": v.layout,
        "obligatorio": v.obligatorio,
        "valido": v.valido,
        "errores": v.errores,
        "warnings": v.warnings,
    }


def _resumen_validaciones(
    validaciones: list[ValidacionArchivo],
    ambiguos: list[tuple[str, list[str]]],
) -> dict[str, Any]:
    obligatorios_invalidos = [
        v for v in validaciones if v.obligatorio and not v.valido
    ]
    archivos_validos = sum(1 for v in validaciones if v.valido)
    archivos_rechazados = sum(1 for v in validaciones if not v.valido)
    puede_procesar = not obligatorios_invalidos and not ambiguos

    if ambiguos:
        mensaje = (
            f"{archivos_validos} válidos, {archivos_rechazados} rechazados. "
            f"Hay {len(ambiguos)} archivo(s) con candidatos ambiguos; "
            f"renombrar para que el matching sea unívoco."
        )
    elif puede_procesar and archivos_rechazados == 0:
        mensaje = f"{archivos_validos} archivos válidos. Listo para procesar."
    elif puede_procesar:
        mensaje = (
            f"{archivos_validos} válidos, {archivos_rechazados} rechazados "
            f"(opcionales). Se puede procesar excluyendo los rechazados."
        )
    else:
        mensaje = (
            f"{archivos_validos} válidos, {archivos_rechazados} rechazados. "
            f"No se puede procesar: {len(obligatorios_invalidos)} archivo(s) "
            f"obligatorio(s) inválido(s)."
        )

    return {
        "puede_procesar": puede_procesar,
        "archivos_validos": archivos_validos,
        "archivos_rechazados": archivos_rechazados,
        "mensaje": mensaje,
    }


def _correr_job(
    job_id: str,
    payload: Any,
    config_path: str,
    grupo_prueba: str | None,
    nombres_por_archivo: dict[str, list[str]] | None,
    progress: ProgressTracker,
    job_logger: logging.Logger,
    job_dir: Path,
) -> None:
    try:
        ejecutar_postgres(
            job_id=job_id,
            payload=payload,
            config_path=config_path,
            grupo_prueba=grupo_prueba,
            nombres_por_archivo=nombres_por_archivo,
            progress=progress,
            logger=job_logger,
            modo_registro="actualizar",
        )
    except Exception as error:  # noqa: BLE001
        job_logger.exception("Job demo %s falló: %s", job_id, error)
    finally:
        progress.cerrar()
        logger.info(
            "Job demo %s terminado, archivos en %s", job_id, job_dir
        )


def _extraer_archivos_config(
    config: dict[str, Any], tipo_carga: str
) -> list[dict[str, Any]]:
    archivos_config_raw = config.get("archivos")
    if not isinstance(archivos_config_raw, list) or not archivos_config_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Config '{tipo_carga}' sin sección 'archivos'",
        )
    for archivo_raw in archivos_config_raw:
        if not isinstance(archivo_raw, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Config '{tipo_carga}': cada archivo debe ser un mapping",
            )
        ruta_raw = archivo_raw.get("ruta")
        if not isinstance(ruta_raw, str) or not ruta_raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Config '{tipo_carga}': archivo sin 'ruta'",
            )
    return archivos_config_raw


@router.post(
    "/validar-archivos",
    responses={
        200: {"description": "Resultado de la validación de los archivos subidos"},
        400: {"description": "Tipo de carga inválido o config corrupto"},
    },
)
async def validar_archivos_endpoint(
    tipo_carga: str = Form(...),
    archivos: list[UploadFile] = File(...),
) -> dict[str, Any]:
    """
    Valida cada archivo subido contra su layout sin procesar nada. Guarda los
    archivos en un dir temporal, llama validador_carga.validar_archivo por
    cada uno, devuelve por archivo (válido / errores / warnings) y limpia el
    dir al terminar. No persiste ni dispara jobs.
    """
    if tipo_carga not in CONFIGS_PERMITIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"tipo_carga inválido. Permitidos: {list(CONFIGS_PERMITIDOS)}",
        )
    if not archivos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe subir al menos un archivo",
        )

    try:
        config = _cargar_config_yaml(tipo_carga)
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo leer el config '{tipo_carga}': {error}",
        ) from error

    archivos_config_raw = _extraer_archivos_config(config, tipo_carga)
    rutas_config = [str(a.get("ruta", "")) for a in archivos_config_raw]

    match = _hacer_match_tolerante(archivos, rutas_config)

    tmp_dir = Path(tempfile.mkdtemp(prefix=TMP_PREFIX))
    rutas_finales: dict[str, Path] = {}
    try:
        for nombre_config, upload in match.asignacion.items():
            destino = tmp_dir / nombre_config
            await _guardar_archivo(upload, destino)
            rutas_finales[nombre_config] = destino

        validaciones = _validar_archivos_guardados(
            archivos_config_raw,
            match.asignacion,
            rutas_finales,
            match.extras,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    resumen = _resumen_validaciones(validaciones, match.ambiguos)
    ambiguos_response = [
        {"nombre_config": nombre, "candidatos": candidatos}
        for nombre, candidatos in match.ambiguos
    ]

    return {
        "tipo_carga": tipo_carga,
        "archivos": [_to_dict(v) for v in validaciones],
        "ambiguos": ambiguos_response,
        **resumen,
    }


@router.post(
    "/upload-y-procesar",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Job aceptado y disparado en background"},
        400: {"description": "Validación falló o archivos no coinciden"},
        500: {"description": "Error guardando archivos o construyendo payload"},
    },
)
async def upload_y_procesar(
    tipo_carga: str = Form(...),
    archivos: list[UploadFile] = File(...),
) -> dict[str, Any]:
    """
    Sube archivos vía multipart, los valida contra el layout de cada uno y
    dispara un job de procesamiento si los obligatorios pasan validación.
    Si solo fallan archivos opcionales, los excluye del payload y procesa
    los válidos. Si falla alguno obligatorio, devuelve 400 con el detalle.
    """
    if tipo_carga not in CONFIGS_PERMITIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"tipo_carga inválido. Permitidos: {list(CONFIGS_PERMITIDOS)}",
        )
    if not archivos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe subir al menos un archivo",
        )

    try:
        config = _cargar_config_yaml(tipo_carga)
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo leer el config '{tipo_carga}': {error}",
        ) from error

    archivos_config_raw = _extraer_archivos_config(config, tipo_carga)
    rutas_config = [str(a.get("ruta", "")) for a in archivos_config_raw]

    match = _hacer_match_tolerante(archivos, rutas_config)

    if match.ambiguos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "mensaje": (
                    "Hay archivos subidos con candidatos ambiguos. "
                    "Renombrar para que el matching sea unívoco."
                ),
                "ambiguos": [
                    {"nombre_config": n, "candidatos": c}
                    for n, c in match.ambiguos
                ],
            },
        )

    job_id = uuid.uuid4().hex
    job_dir = UPLOADS_DEMO_DIR / job_id
    try:
        job_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo crear directorio del job: {error}",
        ) from error

    rutas_finales: dict[str, Path] = {}
    try:
        for nombre_config, upload in match.asignacion.items():
            destino = job_dir / nombre_config
            await _guardar_archivo(upload, destino)
            rutas_finales[nombre_config] = destino
    except OSError as error:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error guardando archivos: {error}",
        ) from error

    validaciones = _validar_archivos_guardados(
        archivos_config_raw,
        match.asignacion,
        rutas_finales,
        match.extras,
    )

    obligatorios_invalidos = [
        v for v in validaciones if v.obligatorio and not v.valido
    ]
    if obligatorios_invalidos:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "mensaje": (
                    f"{len(obligatorios_invalidos)} archivo(s) obligatorio(s) "
                    f"fallaron la validación. No se procesa."
                ),
                "archivos": [_to_dict(v) for v in validaciones],
                "ambiguos": [],
            },
        )

    excluidos = [
        v
        for v in validaciones
        if v.layout is not None and not v.obligatorio and not v.valido
    ]
    excluidos_nombres = {v.nombre for v in excluidos}

    archivos_filtrados: list[dict[str, Any]] = []
    for archivo_raw in archivos_config_raw:
        nombre_config = Path(str(archivo_raw.get("ruta", ""))).name
        if nombre_config in excluidos_nombres:
            continue
        nueva_ruta = rutas_finales.get(nombre_config)
        if nueva_ruta is None:
            continue
        archivo_raw = dict(archivo_raw)
        archivo_raw["ruta"] = str(nueva_ruta)
        archivos_filtrados.append(archivo_raw)

    if not archivos_filtrados:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "mensaje": (
                    "Después de excluir los archivos rechazados no queda "
                    "ningún archivo para procesar."
                ),
                "archivos": [_to_dict(v) for v in validaciones],
            },
        )

    config_para_payload = dict(config)
    config_para_payload["archivos"] = archivos_filtrados

    try:
        payload, nombres_por_archivo, grupo_prueba = construir_payload(
            config_para_payload
        )
    except (ValueError, KeyError) as error:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payload inválido tras sustituir rutas: {error}",
        ) from error

    config_path = str((CONFIGS_DIR / f"{tipo_carga}.yml").resolve())
    pais = payload.proceso.pais
    pais_label = pais.strip().upper() if pais else "default"

    try:
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
    except Exception as error:  # noqa: BLE001
        shutil.rmtree(job_dir, ignore_errors=True)
        logger.exception("No se pudo registrar el job demo %s en Postgres", job_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo registrar el job en Postgres: {error}",
        ) from error

    job_logger = configurar_logger(job_id)
    job_logger.info(
        "Job demo %s lanzado (tipo_carga=%s, archivos=%d, excluidos=%d, "
        "pais=%s, dir=%s)",
        job_id,
        tipo_carga,
        len(payload.archivos),
        len(excluidos),
        pais_label,
        job_dir,
    )

    total_estimado = worker_service._estimar_total_filas(
        payload.archivos, job_logger
    )
    secundarios = [a for a in payload.archivos if a.orden != 1]
    fase_total = 3 + len(secundarios) if secundarios else 2
    progress = ProgressTracker(
        total_estimado,
        f"Demo {job_id[:8]}",
        job_id=job_id,
        fase_total=fase_total,
    )

    thread = threading.Thread(
        target=_correr_job,
        kwargs={
            "job_id": job_id,
            "payload": payload,
            "config_path": config_path,
            "grupo_prueba": grupo_prueba,
            "nombres_por_archivo": nombres_por_archivo or None,
            "progress": progress,
            "job_logger": job_logger,
            "job_dir": job_dir,
        },
        name=f"demo-{job_id[:8]}",
        daemon=True,
    )
    thread.start()

    logger.info(
        "Job demo %s aceptado (tipo_carga=%s, pais=%s, excluidos=%d)",
        job_id,
        tipo_carga,
        pais_label,
        len(excluidos),
    )

    return {
        "jobId": job_id,
        "estado": "procesando",
        "tipoCarga": tipo_carga,
        "pais": pais_label,
        "archivos": len(payload.archivos),
        "excluidos": [_to_dict(v) for v in excluidos],
        "validaciones": [_to_dict(v) for v in validaciones],
        "consultarEn": f"/api/jobs/{job_id}/progreso",
    }


@router.get(
    "/configs",
    responses={200: {"description": "Lista de tipos de carga permitidos"}},
)
def listar_configs_demo() -> dict[str, Any]:
    """
    Lista los tipos de carga aceptados por POST /api/demo/upload-y-procesar y,
    para cada uno, los nombres base de los archivos que el config espera.
    Útil para que el HTML de demo arme el formulario de subida.
    """
    salida: list[dict[str, Any]] = []
    for tipo_carga in CONFIGS_PERMITIDOS:
        try:
            config = _cargar_config_yaml(tipo_carga)
        except (OSError, ValueError) as error:
            salida.append(
                {
                    "tipo_carga": tipo_carga,
                    "error": str(error),
                    "archivos": [],
                }
            )
            continue
        archivos_raw = config.get("archivos") or []
        archivos_meta: list[dict[str, Any]] = []
        for archivo_raw in archivos_raw:
            if not isinstance(archivo_raw, dict):
                continue
            ruta_raw = archivo_raw.get("ruta")
            if not isinstance(ruta_raw, str) or not ruta_raw:
                continue
            archivos_meta.append(
                {
                    "nombre": Path(ruta_raw).name,
                    "layout": archivo_raw.get("layout"),
                    "orden": archivo_raw.get("orden"),
                    "obligatorio": _es_obligatorio(archivo_raw),
                }
            )
        proceso = config.get("proceso") or {}
        salida.append(
            {
                "tipo_carga": tipo_carga,
                "empresa": proceso.get("empresa"),
                "pais": proceso.get("pais"),
                "grupo_prueba": proceso.get("grupo_prueba"),
                "archivos": archivos_meta,
            }
        )
    return {"configs": salida}
