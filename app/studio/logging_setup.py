"""Configuration du journal applicatif en console et en fichier JSON."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any

from studio.config import AppConfig


class JsonFormatter(logging.Formatter):
    """Formateur JSON, une ligne par événement."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(config: AppConfig, *, console: bool = True) -> None:
    """Configure les logs locaux. `console=False` convient au lanceur sans fenêtre."""

    log_dir = config.path_for("paths", "logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "studio.log"

    level_name = str(config.get("logging", "level", default="INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
        root.addHandler(console_handler)

    max_bytes = int(config.get("logging", "max_bytes", default=5_242_880))
    backup_count = int(config.get("logging", "backup_count", default=3))
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(JsonFormatter())
    root.addHandler(file_handler)
