from __future__ import annotations

import logging
import sys
from pathlib import Path

LOGS_DIR: Path = Path(__file__).resolve().parent.parent / "logs"


def configurar_logger(job_id: str) -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    archivo_log = LOGS_DIR / f"{job_id}.log"

    logger = logging.getLogger(f"recsa.job.{job_id}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    formato = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(archivo_log, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formato)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formato)
    logger.addHandler(stream_handler)

    return logger
