from pathlib import Path
from typing import Any

import tomllib


class SettingsLoader:
    """
    Singleton (через __new__):
    - простой и читаемый способ
    - гарантирует один экземпляр на приложение
    - исключает создание дополнительных экземпляров при повторных импортах/создании объекта
    """

    _instance: "SettingsLoader | None" = None

    def __new__(cls) -> "SettingsLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
            cls._instance._config: dict[str, Any] = {}
        return cls._instance

    def _load_defaults(self) -> dict[str, Any]:
        project_root = Path.cwd()
        data_dir = project_root / "data"

        return {
            "DATA_DIR": str(data_dir),
            "USERS_JSON": str(data_dir / "users.json"),
            "PORTFOLIOS_JSON": str(data_dir / "portfolios.json"),
            "RATES_JSON": str(data_dir / "rates.json"),
            "RATES_TTL_SECONDS": 300,
            "DEFAULT_BASE_CURRENCY": "USD",
            "LOG_DIR": str(project_root / "logs"),
            "LOG_LEVEL": "INFO",
            "LOG_FORMAT": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        }

    def _load_from_pyproject(self) -> dict[str, Any]:
        pyproject_path = Path.cwd() / "pyproject.toml"
        if not pyproject_path.exists():
            return {}

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        tool = data.get("tool", {})
        vt = tool.get("valutatrade", {})
        if not isinstance(vt, dict):
            return {}

        normalized: dict[str, Any] = {}
        for k, v in vt.items():
            if isinstance(k, str):
                normalized[k.upper()] = v
        return normalized

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return

        cfg = self._load_defaults()
        cfg.update(self._load_from_pyproject())
        self._config = cfg
        self._loaded = True

    def get(self, key: str, default: Any = None) -> Any:
        self._ensure_loaded()
        if not isinstance(key, str):
            return default
        return self._config.get(key.upper(), default)

    def reload(self) -> None:
        self._loaded = False
        self._config = {}
        self._ensure_loaded()
