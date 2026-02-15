import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from valutatrade_hub.core.exceptions import ApiRequestError

logger = logging.getLogger("valutatrade")


def utc_now_iso() -> str:
    """UTC timestamp в ISO-формате с суффиксом Z."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


class RatesStorage(Protocol):
    """
    Протокол хранилища (storage.py)
    """

    def save_snapshot(self, snapshot: dict) -> None: ...

    def append_history(self, records: list[dict]) -> None: ...


class ApiClient(Protocol):
    """Протокол клиента API"""

    name: str

    def fetch_rates(self) -> dict[str, float]: ...


@dataclass
class RatesUpdater:
    """
    Точка входа логики парсинга
    """

    clients: list[ApiClient]
    storage: RatesStorage

    def run_update(self) -> dict:
        """
        Обновляет курсы и сохраняет
        """
        started_at = utc_now_iso()
        logger.info(
            "ParserService update start at %s " + "(clients=%d)",
            started_at,
            len(self.clients),
        )

        pairs_snapshot: dict[str, dict] = {}
        history_records: list[dict] = []

        for client in self.clients:
            source = getattr(client, "name", client.__class__.__name__)
            logger.info("Fetching rates from %s ...", source)

            try:
                rates = client.fetch_rates()
                if not isinstance(rates, dict):
                    raise ApiRequestError(
                        f"{source}: " + "fetch_rates() вернул некорректный тип"
                    )

                now_iso = utc_now_iso()

                added = 0
                for pair, rate in rates.items():
                    if not isinstance(pair, str) or not pair.strip():
                        continue
                    if not isinstance(rate, (int, float)) or float(rate) <= 0:
                        continue

                    pair_key = pair.strip().upper()

                    current = pairs_snapshot.get(pair_key)
                    if current is None or current.get("updated_at", "") < now_iso:
                        pairs_snapshot[pair_key] = {
                            "rate": float(rate),
                            "updated_at": now_iso,
                            "source": source,
                        }

                    history_records.append(
                        {
                            "id": f"{pair_key}_{now_iso}",
                            "from_currency": pair_key.split("_", 1)[0],
                            "to_currency": pair_key.split("_", 1)[1]
                            if "_" in pair_key
                            else "",
                            "rate": float(rate),
                            "timestamp": now_iso,
                            "source": source,
                            "meta": {},
                        }
                    )

                    added += 1

                logger.info("Fetched %d rates from %s (OK)", added, source)

            except ApiRequestError as e:
                logger.info("Fetching from %s failed: %s", source, str(e))
                continue
            except Exception as e:
                logger.info("Fetching from %s failed (unexpected): %s", source, str(e))
                continue

        finished_at = utc_now_iso()

        snapshot = {
            "pairs": pairs_snapshot,
            "last_refresh": finished_at,
        }

        if not pairs_snapshot:
            logger.info(
                "ParserService update finished: " + "NO DATA (last_refresh=%s)",
                finished_at,
            )
            raise ApiRequestError("Не удалось получить курсы ни от одного источника.")

        logger.info("Saving snapshot to rates.json (pairs=%d)...", len(pairs_snapshot))
        self.storage.save_snapshot(snapshot)

        logger.info("Appending history records (count=%d)...", len(history_records))
        self.storage.append_history(history_records)

        logger.info("ParserService update finished OK at %s", finished_at)
        return snapshot
