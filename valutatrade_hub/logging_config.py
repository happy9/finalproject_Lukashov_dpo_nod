import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader


def setup_logging() -> None:
    """Настройка логирования доменных операций."""

    settings = SettingsLoader()

    log_dir = Path(settings.get("LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "actions.log"
    log_level = settings.get("LOG_LEVEL", "INFO")

    formatter = logging.Formatter(
        "%(levelname)s %(asctime)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handler = RotatingFileHandler(
        log_file,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(formatter)

    root = logging.getLogger("valutatrade")
    root.setLevel(log_level)
    root.handlers.clear()
    root.addHandler(handler)
