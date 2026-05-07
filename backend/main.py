from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers.config import preview_router
from routers.config import router as config_router
from routers.jobs import router as jobs_router
from routers.mapeo import router as mapeo_router
from routers.proceso import router as proceso_router
from routers.queue import router as queue_router
from routers.upload import router as upload_router
from services import mongo_service, queue_service, worker_service

REPORTES_DIR: Path = Path(__file__).resolve().parent / "reportes"
LOGS_DIR: Path = Path(__file__).resolve().parent / "logs"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    REPORTES_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    queue_service.inicializar()
    worker_service.iniciar_worker()
    try:
        yield
    finally:
        worker_service.detener_worker()
        queue_service.cerrar()
        mongo_service.cerrar()


app = FastAPI(
    title="RECSA Importador de Datos",
    description=(
        "Motor de cargas RECSA. Encola jobs de procesamiento por país en Redis "
        "y los persiste en la BD Postgres del país correspondiente. La API "
        "REST documentada acá es consumida por Laravel/Dante."
    ),
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://localhost(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router)
app.include_router(upload_router)
app.include_router(config_router)
app.include_router(preview_router)
app.include_router(mapeo_router)
app.include_router(proceso_router)
app.include_router(queue_router)

REPORTES_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    "/static/reportes",
    StaticFiles(directory=str(REPORTES_DIR), check_dir=False),
    name="reportes",
)
app.mount(
    "/static/logs",
    StaticFiles(directory=str(LOGS_DIR), check_dir=False),
    name="logs",
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
