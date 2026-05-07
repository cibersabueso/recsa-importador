from __future__ import annotations

import argparse
import sys

from db.db_config import DBConfig, cargar_config, resolver_db
from db.postgres_client import ensure_schema


def _aplicar(db_config: DBConfig, etiqueta: str) -> None:
    ensure_schema(db_config)
    print(
        f"Schema OK en {db_config.host}:{db_config.port}/{db_config.database} ({etiqueta})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inicializa el schema de RECSA en una o varias BDs",
    )
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument(
        "--pais",
        type=str,
        default=None,
        help="Inicializa solo la BD del país indicado (ej: PERU, CHILE)",
    )
    grupo.add_argument(
        "--todos",
        action="store_true",
        help="Inicializa la BD default y todas las BDs configuradas en databases.yml",
    )
    args = parser.parse_args()

    if args.todos:
        try:
            paises, default_config = cargar_config()
        except FileNotFoundError as error:
            print(f"databases.yml no encontrado: {error}", file=sys.stderr)
            sys.exit(1)
        _aplicar(default_config, "default")
        for codigo, cfg in paises.items():
            _aplicar(cfg, codigo)
        return

    if args.pais:
        cfg = resolver_db(args.pais)
        etiqueta = args.pais.strip().upper()
        _aplicar(cfg, etiqueta)
        return

    cfg = resolver_db(None)
    _aplicar(cfg, "default")


if __name__ == "__main__":
    main()
