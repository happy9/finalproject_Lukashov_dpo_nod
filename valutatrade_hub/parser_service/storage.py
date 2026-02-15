# valutatrade_hub/parser_service/storage.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ParserConfig


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _atomic_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


@dataclass
class JsonRatesStorage:
    config: ParserConfig

    def save_snapshot(self, snapshot: dict) -> None:
        _atomic_write(Path(self.config.RATES_FILE_PATH), snapshot)

    def append_history(self, records: list[dict]) -> None:
        path = Path(self.config.HISTORY_FILE_PATH)
        data = _read_json(path, default=[])
        if not isinstance(data, list):
            data = []
        data.extend(records)
        _atomic_write(path, data)
