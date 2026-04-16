from __future__ import annotations

import os
from threading import Lock
from typing import Any

import certifi
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError
from pymongo.server_api import ServerApi

MONGO_URI_DEFAULT = (
    "mongodb+srv://enriquegarrido_db_user:BV7JDTvtNeMiigSv"
    "@recsa-cluster.mk2bieq.mongodb.net/?appName=recsa-cluster"
)
DB_NAME = "recsa_db"
COLECCION_EVENTOS = "eventos"

_client: MongoClient | None = None
_lock = Lock()


def _crear_client(uri: str) -> MongoClient:
    return MongoClient(
        uri,
        server_api=ServerApi("1"),
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        socketTimeoutMS=20000,
        retryWrites=True,
        tls=True,
        tlsCAFile=certifi.where(),
    )


def _obtener_client() -> MongoClient:
    global _client
    with _lock:
        if _client is None:
            uri = os.getenv("MONGODB_URI", MONGO_URI_DEFAULT)
            _client = _crear_client(uri)
        return _client


def _db() -> Database:
    return _obtener_client()[DB_NAME]


def _eventos() -> Collection:
    return _db()[COLECCION_EVENTOS]


def cerrar() -> None:
    global _client
    with _lock:
        if _client is not None:
            _client.close()
            _client = None


def estado_conexion() -> dict[str, Any]:
    try:
        respuesta = _obtener_client().admin.command("ping")
        return {"ok": True, "detalle": respuesta}
    except PyMongoError as error:
        return {
            "ok": False,
            "error": type(error).__name__,
            "mensaje": str(error),
        }
    except Exception as error:  # noqa: BLE001
        return {
            "ok": False,
            "error": type(error).__name__,
            "mensaje": str(error),
        }


def ping() -> bool:
    return estado_conexion()["ok"]


def contar_eventos() -> int:
    return _eventos().estimated_document_count()


def estadisticas_generales() -> dict[str, Any]:
    pipeline: list[dict[str, Any]] = [
        {
            "$group": {
                "_id": None,
                "total_eventos": {"$sum": 1},
                "empresas": {"$addToSet": "$empresa"},
                "campanas": {"$addToSet": "$campana"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "total_eventos": 1,
                "total_empresas": {"$size": "$empresas"},
                "total_campanas": {"$size": "$campanas"},
            }
        },
    ]
    resultado = list(_eventos().aggregate(pipeline))
    if not resultado:
        return {"total_eventos": 0, "total_empresas": 0, "total_campanas": 0}
    return resultado[0]


def eventos_por_empresa(empresa: str, limite: int = 100) -> list[dict[str, Any]]:
    cursor = _eventos().find({"empresa": empresa}, {"_id": 0}).limit(limite)
    return list(cursor)


def eventos_por_campana(campana: str, limite: int = 100) -> list[dict[str, Any]]:
    cursor = _eventos().find({"campana": campana}, {"_id": 0}).limit(limite)
    return list(cursor)


def conteo_por_empresa() -> list[dict[str, Any]]:
    pipeline: list[dict[str, Any]] = [
        {"$group": {"_id": "$empresa", "total": {"$sum": 1}}},
        {"$project": {"_id": 0, "empresa": "$_id", "total": 1}},
        {"$sort": {"total": -1}},
    ]
    return list(_eventos().aggregate(pipeline))


def conteo_por_campana() -> list[dict[str, Any]]:
    pipeline: list[dict[str, Any]] = [
        {"$group": {"_id": "$campana", "total": {"$sum": 1}}},
        {"$project": {"_id": 0, "campana": "$_id", "total": 1}},
        {"$sort": {"total": -1}},
    ]
    return list(_eventos().aggregate(pipeline))
