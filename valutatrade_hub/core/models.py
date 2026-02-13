from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import Dict

from valutatrade_hub.core.exceptions import InsufficientFundsError

class User:
    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ) -> None:
        self._user_id = user_id
        self._username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым.")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    def get_user_info(self) -> dict:
        """Информация о пользователе"""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def change_password(self, new_password: str) -> None:
        """Смена пароля"""
        if not isinstance(new_password, str) or len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов.")

        new_salt = secrets.token_urlsafe(8)
        new_hash = self._hash_password(new_password, new_salt)

        self._salt = new_salt
        self._hashed_password = new_hash
        
        
class Wallet:
    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("Код валюты должен быть непустой строкой.")

        self._currency_code = currency_code.upper()
        self.balance = balance

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if not isinstance(value, (int, float)):
            raise TypeError("Баланс должен быть числом.")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным.")
        self._balance = float(value)

    @property
    def currency_code(self) -> str:
        return self._currency_code

    def deposit(self, amount: float) -> None:
        if not isinstance(amount, (int, float)):
            raise TypeError("Сумма пополнения должна быть числом.")
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной.")

        self._balance += float(amount)

    def withdraw(self, amount: float) -> None:
        if not isinstance(amount, (int, float)):
            raise TypeError("Сумма снятия должна быть числом.")
        if amount <= 0:
            raise ValueError("Сумма снятия должна быть положительной.")
        if amount > self._balance:
            def fmt(cur: str, v: float) -> str:
                return f"{v:.4f}" if cur in ("BTC", "ETH") else f"{v:.2f}"

            raise InsufficientFundsError(
                available=fmt(self.currency_code, self._balance),
                required=fmt(self.currency_code, float(amount)),
                code=self.currency_code,
            )

        self._balance -= float(amount)

    def get_balance_info(self) -> dict:
        return {
            "currency_code": self._currency_code,
            "balance": self._balance,
        }


class Portfolio:
    def __init__(
        self,
        user: User,
        user_id: int,
        wallets: dict[str, Wallet] | None = None,
    ) -> None:
        self._user = user
        self._user_id = user_id
        self._wallets: dict[str, Wallet] = wallets.copy() if wallets else {}

    @property
    def user(self) -> User:
        return self._user

    @property
    def wallets(self) -> dict[str, Wallet]:
        return self._wallets.copy()

    def add_currency(self, currency_code: str) -> None:
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("Код валюты должен быть непустой строкой.")

        code = currency_code.upper()

        if code in self._wallets:
            raise ValueError(f"Кошелёк для валюты {code} уже существует.")

        self._wallets[code] = Wallet(currency_code=code, balance=0.0)

    def get_wallet(self, currency_code: str) -> Wallet:
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("Код валюты должен быть непустой строкой.")

        code = currency_code.upper()

        try:
            return self._wallets[code]
        except KeyError as exc:
            raise KeyError(f"Кошелёк {code} не найден.") from exc

    def get_total_value(self, base_currency: str = "USD") -> float:
        if not isinstance(base_currency, str) or not base_currency.strip():
            raise ValueError("Базовая валюта должна быть строкой.")

        base = base_currency.upper()

        exchange_rates = {
            ("USD", "USD"): 1.0,
            ("EUR", "USD"): 1.1,
            ("BTC", "USD"): 40000.0,
        }

        total = 0.0

        for code, wallet in self._wallets.items():
            if code == base:
                total += wallet.balance
            else:
                rate = exchange_rates.get((code, base))
                if rate is None:
                    raise KeyError(f"Нет курса для {code} -> {base}")
                total += wallet.balance * rate

        return float(total)
