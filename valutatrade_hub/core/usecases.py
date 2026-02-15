import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader

_current_user: dict | None = None

settings = SettingsLoader()
db = DatabaseManager()

RATES_TTL_SECONDS = int(settings.get("RATES_TTL_SECONDS", 300))
DEFAULT_BASE = str(settings.get("DEFAULT_BASE_CURRENCY", "USD")).upper()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


def _get_rate_to_base(code: str, base_code: str, rates: dict) -> float:
    if code == base_code:
        return 1.0

    pair = f"{code}_{base_code}"
    pair_data = rates.get(pair)

    if not isinstance(pair_data, dict) or "rate" not in pair_data:
        raise ValueError(f"Не удалось получить курс для {code}→{base_code}")

    rate = pair_data["rate"]
    if not isinstance(rate, (int, float)) or rate <= 0:
        raise ValueError(f"Не удалось получить курс для {code}→{base_code}")

    return float(rate)


def _find_user(user_id: int) -> dict:
    users = db.read("USERS_JSON", default=[])
    for u in users:
        if u.get("user_id") == user_id:
            return u
    raise ValueError(f"Пользователь с id={user_id} не найден")


def _get_or_create_portfolio(user_id: int) -> tuple[list[dict], dict]:
    portfolios = db.read("PORTFOLIOS_JSON", default=[])
    for p in portfolios:
        if p.get("user_id") == user_id:
            if "wallets" not in p or not isinstance(p["wallets"], dict):
                p["wallets"] = {}
            return portfolios, p

    new_p = {"user_id": user_id, "wallets": {}}
    portfolios.append(new_p)
    return portfolios, new_p


def _get_wallet_balance(wallets: dict, code: str) -> float:
    w = wallets.get(code)
    if not isinstance(w, dict):
        return 0.0
    bal = w.get("balance", 0.0)
    return float(bal) if isinstance(bal, (int, float)) else 0.0


def _set_wallet_balance(wallets: dict, code: str, balance: float) -> None:
    if code not in wallets or not isinstance(wallets.get(code), dict):
        wallets[code] = {"balance": 0.0}
    wallets[code]["balance"] = float(balance)


def _is_fresh(updated_at_iso: str, now: datetime) -> bool:
    try:
        s = updated_at_iso.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"

        ts = datetime.fromisoformat(s)

        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

    except Exception:
        return False

    return (now - ts) <= timedelta(seconds=RATES_TTL_SECONDS)



def _update_rate_stub(
    frm: str, to: str, now: datetime, rates: dict
) -> tuple[float, str]:
    exchange_rates_stub = {
        "EUR_USD": 1.0786,
        "BTC_USD": 59337.21,
        "RUB_USD": 0.01016,
        "ETH_USD": 3720.00,
    }

    direct = exchange_rates_stub.get(f"{frm}_{to}")
    if direct is not None:
        rate = float(direct)
    else:
        rev = exchange_rates_stub.get(f"{to}_{frm}")
        if rev is None or float(rev) <= 0:
            raise ApiRequestError(
                f"Курс {frm}→{to} недоступен. " + "Повторите попытку позже."
            )
        rate = 1.0 / float(rev)

    updated_iso = now.isoformat()
    rates.setdefault("pairs", {})
    rates["pairs"][f"{frm}_{to}"] = {
        "rate": rate,
        "updated_at": updated_iso,
        "source": "Stub",
    }
    rates["last_refresh"] = updated_iso

    return rate, updated_iso


@log_action("REGISTER")
def register_user(username: str, password: str) -> str:
    if not username or not username.strip():
        raise ValueError("Имя пользователя не может быть пустым.")

    if not password or len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")

    username = username.strip()

    users = db.read("USERS_JSON", default=[])

    for user in users:
        if user["username"] == username:
            raise ValueError(f"Имя пользователя '{username}' уже занято")

    if users:
        new_id = max(u["user_id"] for u in users) + 1
    else:
        new_id = 1

    salt = secrets.token_urlsafe(8)
    hashed_password = _hash_password(password, salt)

    registration_date = datetime.now().isoformat()

    new_user = {
        "user_id": new_id,
        "username": username,
        "hashed_password": hashed_password,
        "salt": salt,
        "registration_date": registration_date,
    }

    users.append(new_user)
    db.write("USERS_JSON", users)

    portfolios = db.read("PORTFOLIOS_JSON", default=[])

    portfolios.append(
        {
            "user_id": new_id,
            "wallets": {},
        }
    )

    db.write("PORTFOLIOS_JSON", portfolios)

    return (
        f"Пользователь '{username}' зарегистрирован (id={new_id}). "
        f"Войдите: login --username {username} --password ****"
    )


@log_action("LOGIN")
def login_user(username: str, password: str) -> dict:
    global _current_user

    if not username or not username.strip():
        raise ValueError("Имя пользователя обязателено.")

    if not password:
        raise ValueError("Пароль обязателен.")

    users = db.read("USERS_JSON", default=[])

    user_data = None
    for user in users:
        if user["username"] == username:
            user_data = user
            break

    if user_data is None:
        raise ValueError(f"Пользователь '{username}' не найден")

    salt = user_data["salt"]
    expected_hash = user_data["hashed_password"]
    entered_hash = _hash_password(password, salt)

    if entered_hash != expected_hash:
        raise ValueError("Неверный пароль")

    _current_user = user_data

    return {"user_id": user_data["user_id"], "username": user_data["username"]}


def show_portfolio(user_id: int, base: str | None = None) -> str:
    if not base:
        base = DEFAULT_BASE
    if not isinstance(base, str) or not base.strip():
        raise ValueError("Неизвестная базовая валюта ''")
    base = base.upper()

    user = _find_user(user_id)
    username = user.get("username", f"id={user_id}")

    portfolios = db.read("PORTFOLIOS_JSON", default=[])
    portfolio_data = None
    for p in portfolios:
        if p.get("user_id") == user_id:
            portfolio_data = p
            break

    if portfolio_data is None:
        portfolio_data = {"user_id": user_id, "wallets": {}}

    wallets_data: dict = portfolio_data.get("wallets", {})
    if not wallets_data:
        return f"Портфель пользователя '{username}' пуст."

    rates_json = db.read("RATES_JSON", default={})
    pairs = rates_json.get("pairs", {}) if isinstance(rates_json, dict) else {}

    lines: list[str] = []
    total = 0.0

    lines.append(f"Портфель пользователя '{username}' (база: {base}):")

    codes_sorted = sorted(wallets_data.keys())
    if base in codes_sorted:
        codes_sorted.remove(base)
        codes_sorted = [base] + codes_sorted

    for code in codes_sorted:
        wallet_info = wallets_data.get(code, {})
        bal = wallet_info.get("balance", 0.0)
        bal = float(bal) if isinstance(bal, (int, float)) else 0.0

        rate = _get_rate_to_base(code, base, pairs)
        value_in_base = bal * rate
        total += value_in_base

        bal_str = f"{bal:.4f}" if code in ("BTC", "ETH") else f"{bal:.2f}"
        lines.append(f"- {code}: {bal_str}  → {value_in_base:,.2f} {base}")

    lines.append("---------------------------------")
    lines.append(f"ИТОГО: {total:,.2f} {base}")

    return "\n".join(lines)


@log_action("BUY")
def buy(
    user_id: int, currency_code: str, amount: float, base: str | None = None
) -> str:
    if not isinstance(amount, (int, float)) or float(amount) <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    base_code = (base or DEFAULT_BASE).upper()
    code = currency_code.strip().upper() if isinstance(currency_code, str) else ""

    get_currency(code)
    get_currency(base_code)

    portfolios, portfolio = _get_or_create_portfolio(user_id)
    wallets = portfolio["wallets"]

    old_balance = _get_wallet_balance(wallets, code)
    new_balance = old_balance + float(amount)
    _set_wallet_balance(wallets, code, new_balance)

    rate, _updated_at = get_rate(code, base_code)
    estimated_cost = float(amount) * rate

    db.write("PORTFOLIOS_JSON", portfolios)

    def fmt_bal(cur: str, v: float) -> str:
        return f"{v:.4f}" if cur in ("BTC", "ETH") else f"{v:.2f}"

    return (
        f"Покупка выполнена: {fmt_bal(code, float(amount))} {code} "
        f"по курсу {rate:,.2f} {base_code}/{code}\n"
        f"Изменения в портфеле:\n"
        f"- {code}: было {fmt_bal(code, old_balance)} "
        f"→ стало {fmt_bal(code, new_balance)}\n"
        f"Оценочная стоимость покупки: {estimated_cost:,.2f} {base_code}"
    )


@log_action("SELL")
def sell(
    user_id: int, currency_code: str, amount: float, base: str | None = None
) -> str:
    if not isinstance(amount, (int, float)) or float(amount) <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    base_code = (base or DEFAULT_BASE).upper()
    code = currency_code.strip().upper() if isinstance(currency_code, str) else ""

    get_currency(code)
    get_currency(base_code)

    portfolios, portfolio = _get_or_create_portfolio(user_id)
    wallets = portfolio["wallets"]

    if code not in wallets:
        raise ValueError(
            f"У вас нет кошелька '{code}'. "
            + "Добавьте валюту: она создаётся автоматически при первой покупке."
        )

    old_balance = _get_wallet_balance(wallets, code)

    def fmt_bal(cur: str, v: float) -> str:
        return f"{v:.4f}" if cur in ("BTC", "ETH") else f"{v:.2f}"

    if old_balance < float(amount):
        raise InsufficientFundsError(
            available=fmt_bal(code, old_balance),
            required=fmt_bal(code, float(amount)),
            code=code,
        )

    new_balance = old_balance - float(amount)
    _set_wallet_balance(wallets, code, new_balance)

    rate, _updated_at = get_rate(code, base_code)
    revenue = float(amount) * rate

    db.write("PORTFOLIOS_JSON", portfolios)

    return (
        f"Продажа выполнена: {fmt_bal(code, float(amount))} {code} "
        f"по курсу {rate:,.2f} {base_code}/{code}\n"
        f"Изменения в портфеле:\n"
        f"- {code}: было {fmt_bal(code, old_balance)} → "
        f"стало {fmt_bal(code, new_balance)}\n"
        f"Оценочная выручка: {revenue:,.2f} {base_code}"
    )


def get_rate(from_code: str, to_code: str) -> tuple[float, str]:
    if not isinstance(from_code, str) or not from_code.strip():
        raise CurrencyNotFoundError("")
    if not isinstance(to_code, str) or not to_code.strip():
        raise CurrencyNotFoundError("")

    frm = from_code.strip().upper()
    to = to_code.strip().upper()

    get_currency(frm)
    get_currency(to)

    now = datetime.now(timezone.utc)

    rates_json = db.read("RATES_JSON", default={})
    if not isinstance(rates_json, dict):
        rates_json = {"pairs": {}, "last_refresh": None}

    pairs = rates_json.get("pairs", {})
    if not isinstance(pairs, dict):
        pairs = {}
        rates_json["pairs"] = pairs

    pair_key = f"{frm}_{to}"
    pair_data = pairs.get(pair_key)

    if (
        isinstance(pair_data, dict)
        and "rate" in pair_data
        and "updated_at" in pair_data
    ):
        rate_val = pair_data["rate"]
        updated_at = pair_data["updated_at"]
        if (
            isinstance(rate_val, (int, float))
            and float(rate_val) > 0
            and isinstance(updated_at, str)
        ):
            if _is_fresh(updated_at, now):
                return float(rate_val), updated_at

    rate, updated_iso = _update_rate_stub(frm, to, now, rates_json)

    if "pairs" not in rates_json or not isinstance(rates_json["pairs"], dict):
        rates_json["pairs"] = {}
    rates_json["last_refresh"] = updated_iso

    db.write("RATES_JSON", rates_json)
    return rate, updated_iso
