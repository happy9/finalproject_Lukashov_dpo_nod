from abc import ABC, abstractmethod

from .exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Абстрактная базовая валюта"""

    def __init__(self, name: str, code: str) -> None:
        self.name = name
        self.code = code

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("name должен быть непустой строкой.")
        self._name = value.strip()

    @property
    def code(self) -> str:
        return self._code

    @code.setter
    def code(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("code должен быть строкой.")
        v = value.strip()
        if not v or " " in v or not (2 <= len(v) <= 5) or v != v.upper():
            raise ValueError(
                "code должен быть в " + "верхнем регистре, 2–5 символов, без пробелов."
            )
        self._code = v

    @abstractmethod
    def get_display_info(self) -> str:
        raise NotImplementedError


class FiatCurrency(Currency):
    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        super().__init__(name=name, code=code)
        self.issuing_country = issuing_country

    @property
    def issuing_country(self) -> str:
        return self._issuing_country

    @issuing_country.setter
    def issuing_country(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("issuing_country должен быть непустой строкой.")
        self._issuing_country = value.strip()

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    def __init__(self, name: str, code: str, algorithm: str, market_cap: float) -> None:
        super().__init__(name=name, code=code)
        self.algorithm = algorithm
        self.market_cap = market_cap

    @property
    def algorithm(self) -> str:
        return self._algorithm

    @algorithm.setter
    def algorithm(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("algorithm должен быть непустой строкой.")
        self._algorithm = value.strip()

    @property
    def market_cap(self) -> float:
        return self._market_cap

    @market_cap.setter
    def market_cap(self, value: float) -> None:
        if not isinstance(value, (int, float)):
            raise TypeError("market_cap должен быть числом.")
        if float(value) < 0:
            raise ValueError("market_cap не может быть отрицательным.")
        self._market_cap = float(value)

    def get_display_info(self) -> str:
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            + "(Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"
        )


_CURRENCY_REGISTRY: dict[str, Currency] = {
    "USD": FiatCurrency(name="US Dollar", code="USD", issuing_country="United States"),
    "EUR": FiatCurrency(name="Euro", code="EUR", issuing_country="Eurozone"),
    "BTC": CryptoCurrency(
        name="Bitcoin", code="BTC", algorithm="SHA-256", market_cap=1.12e12
    ),
    "ETH": CryptoCurrency(
        name="Ethereum", code="ETH", algorithm="Ethash", market_cap=4.50e11
    ),
}


def get_currency(code: str) -> Currency:
    if not isinstance(code, str) or not code.strip():
        raise CurrencyNotFoundError(code="")

    key = code.strip().upper()
    cur = _CURRENCY_REGISTRY.get(key)
    if cur is None:
        raise CurrencyNotFoundError(code=key)
    return cur
