import json
from pathlib import Path
from typing import Any

from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    _instance: "DatabaseManager | None" = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._settings = SettingsLoader()
        return cls._instance

    def _path(self, key: str) -> Path:
        # key: USERS_JSON / PORTFOLIOS_JSON / RATES_JSON
        p = self._settings.get(key)
        if not p:
            # fallback на data/<name>.json
            data_dir = Path(self._settings.get("DATA_DIR", "data"))
            fallback = {
                "USERS_JSON": "users.json",
                "PORTFOLIOS_JSON": "portfolios.json",
                "RATES_JSON": "rates.json",
            }.get(key, "data.json")
            return data_dir / fallback
        return Path(p)

    def read(self, key: str, default: Any) -> Any:
        """
        Читает JSON из файла, заданного ключом.
        Если файла нет или JSON битый — возвращает default.
        """
        path = self._path(key)
        if not path.exists():
            return default

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def write(self, key: str, data: Any) -> None:
        """
        Записывает JSON в файл, заданный ключом.
        Создаёт директорию при необходимости.
        """
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
