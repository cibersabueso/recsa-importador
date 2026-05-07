from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from services.dashboard_html import (
    DASHBOARD_FILENAME,
    REPORTES_DIR,
    generar_dashboard,
)


def _configurar_logger() -> logging.Logger:
    log = logging.getLogger("recsa.dashboard.cli")
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    log.addHandler(handler)
    return log


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cli.dashboard",
        description=(
            "Genera el dashboard global RECSA Cargas en un HTML standalone. "
            "Hace fan-out a todas las BDs configuradas en databases.yml."
        ),
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=None,
        help=(
            f"Ruta de salida del HTML. Default: {REPORTES_DIR / DASHBOARD_FILENAME}"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    log = _configurar_logger()
    log.info("Generando dashboard RECSA Cargas...")
    try:
        ruta = generar_dashboard(args.salida)
    except Exception as error:  # noqa: BLE001
        log.error("No se pudo generar el dashboard: %s", error)
        return 1
    ruta_abs = ruta.resolve()
    log.info("Dashboard generado en: %s", ruta_abs)
    print()
    print(f"Dashboard: {ruta_abs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
