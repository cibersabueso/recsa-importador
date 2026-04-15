from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.config import preview_router
from routers.config import router as config_router
from routers.mapeo import router as mapeo_router
from routers.proceso import router as proceso_router
from routers.upload import router as upload_router

app = FastAPI(
    title="RECSA Importador de Datos",
    description="API del módulo importador del CRM de RECSA",
    version="0.1.0",
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


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"estado": "ok", "servicio": "recsa-importador"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
