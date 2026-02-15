from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import requests

from valutatrade_hub.core.exceptions import ApiRequestError

from .config import ParserConfig


class BaseApiClient(ABC):
    """Единый интерфейс клиентов внешних API."""

    def __init__(self, config: ParserConfig) -> None:
        self._config = config

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Возвращает стандартизированный словарь курсов вида {'BTC_USD': 59337.21}."""
        raise NotImplementedError


class CoinGeckoClient(BaseApiClient):
    """Клиент CoinGecko для криптовалют."""

    name = "CoinGecko"

    def fetch_rates(self) -> dict[str, float]:
        cfg = self._config

        ids: list[str] = []
        for code in cfg.CRYPTO_CURRENCIES:
            coin_id = cfg.CRYPTO_ID_MAP.get(code)
            if coin_id:
                ids.append(coin_id)

        if not ids:
            raise ApiRequestError(
                "CoinGecko: список crypto ids пуст "+\
                "(проверь CRYPTO_ID_MAP/CRYPTO_CURRENCIES)."
            )

        vs_key = cfg.BASE_CURRENCY.lower()
        params = {"ids": ",".join(ids), "vs_currencies": vs_key}

        try:
            resp = requests.get(
                cfg.COINGECKO_URL, params=params, timeout=cfg.REQUEST_TIMEOUT
            )
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"CoinGecko недоступен: {e}") from e

        if resp.status_code != 200:
            body = (resp.text or "").strip()
            snippet = body[:200] + ("..." if len(body) > 200 else "")
            raise ApiRequestError(
                f"CoinGecko вернул статус {resp.status_code}: {snippet}"
            )

        try:
            data: Any = resp.json()
        except ValueError as e:
            raise ApiRequestError("CoinGecko: не удалось распарсить JSON-ответ.") from e

        if not isinstance(data, dict):
            raise ApiRequestError(
                "CoinGecko: неожиданный формат ответа (ожидался JSON object)."
            )

        out: dict[str, float] = {}

        for code in cfg.CRYPTO_CURRENCIES:
            coin_id = cfg.CRYPTO_ID_MAP.get(code)
            if not coin_id:
                continue

            coin_block = data.get(coin_id)
            if not isinstance(coin_block, dict):
                continue

            rate_val = coin_block.get(vs_key)
            if isinstance(rate_val, (int, float)) and float(rate_val) > 0:
                out[f"{code.upper()}_{cfg.BASE_CURRENCY.upper()}"] = float(rate_val)

        if not out:
            raise ApiRequestError(
                "CoinGecko: не удалось извлечь ни одного курса из ответа."
            )

        return out


class ExchangeRateApiClient(BaseApiClient):
    """Клиент ExchangeRate-API для фиатных валют."""

    name = "ExchangeRate-API"

    def fetch_rates(self) -> dict[str, float]:
        cfg = self._config

        if not getattr(cfg, "EXCHANGERATE_API_KEY", ""):
            raise ApiRequestError(
                "ExchangeRate-API: API key не задан (EXCHANGERATE_API_KEY)."
            )

        try:
            url = cfg.exchangerate_latest_url()
        except Exception as e:
            raise ApiRequestError(
                f"ExchangeRate-API: не удалось сформировать URL: {e}"
            ) from e

        try:
            resp = requests.get(url, timeout=cfg.REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"ExchangeRate-API недоступен: {e}") from e

        if resp.status_code != 200:
            body = (resp.text or "").strip()
            snippet = body[:200] + ("..." if len(body) > 200 else "")
            raise ApiRequestError(
                f"ExchangeRate-API вернул статус {resp.status_code}: {snippet}"
            )

        try:
            data: Any = resp.json()
        except ValueError as e:
            raise ApiRequestError(
                "ExchangeRate-API: не удалось распарсить JSON-ответ."
            ) from e

        if not isinstance(data, dict):
            raise ApiRequestError(
                "ExchangeRate-API: неожиданный формат ответа (ожидался JSON object)."
            )

        result = data.get("result")
        if isinstance(result, str) and result.lower() != "success":
            reason = data.get("error-type") or data.get("error") or "unknown"
            raise ApiRequestError(
                f"ExchangeRate-API: result='{result}', reason='{reason}'"
            )

        rates_block = data.get("rates")
        if not isinstance(rates_block, dict):
            raise ApiRequestError(
                "ExchangeRate-API: поле 'rates' отсутствует или имеет неверный тип."
            )

        base = cfg.BASE_CURRENCY.upper()
        out: dict[str, float] = {}

        for code in cfg.FIAT_CURRENCIES:
            c = str(code).upper()
            if c == base:
                continue

            val = rates_block.get(c)
            if isinstance(val, (int, float)) and float(val) > 0:
                out[f"{c}_{base}"] = 1.0 / float(val)

        if not out:
            raise ApiRequestError(
                "ExchangeRate-API: не удалось извлечь ни одного курса из ответа."
            )

        return out
