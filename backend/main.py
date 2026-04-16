from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.config import preview_router
from routers.config import router as config_router
from routers.mapeo import router as mapeo_router
from routers.proceso import router as proceso_router
from routers.queue import router as queue_router
from routers.upload import router as upload_router
from services import mongo_service, queue_service, worker_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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
    description="API del módulo importador del CRM de RECSA",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(config_router)
app.include_router(preview_router)
app.include_router(mapeo_router)
app.include_router(proceso_router)
app.include_router(queue_router)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, object]:
    estado_mongo = mongo_service.estado_conexion()
    respuesta: dict[str, object] = {
        "estado": "ok",
        "servicio": "recsa-importador",
        "mongo": "ok" if estado_mongo["ok"] else "error",
    }
    if estado_mongo["ok"]:
        try:
            respuesta["eventos_total"] = mongo_service.contar_eventos()
        except Exception as error:  # noqa: BLE001
            respuesta["eventos_total"] = None
            respuesta["eventos_error"] = str(error)
    else:
        respuesta["mongo_error"] = estado_mongo.get("mensaje")
        respuesta["mongo_error_tipo"] = estado_mongo.get("error")
    return respuesta


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
