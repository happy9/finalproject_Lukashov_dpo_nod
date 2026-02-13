import json
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from .models import User


DATA_DIR = Path("data")
USERS_FILE = DATA_DIR / "users.json"
PORTFOLIOS_FILE = DATA_DIR / "portfolios.json"
RATES_FILE = DATA_DIR / "rates.json"

_current_user: dict | None = None


def _load_json(path: Path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


def _get_rate_to_base(code: str, base_code: str) -> float:
        if code == base_code:
            return 1.0
        pair = f"{code}_{base_code}"
        pair_data = rates.get(pair)
        if not isinstance(pair_data, dict) or "rate" not in pair_data:
            raise ValueError(f"Неизвестная базовая валюта '{base_code}'")
        rate = pair_data["rate"]
        if not isinstance(rate, (int, float)) or rate <= 0:
            raise ValueError(f"Неизвестная базовая валюта '{base_code}'")
        return float(rate)
        
        
def register_user(username: str, password: str) -> str:
    if not username or not username.strip():
        raise ValueError("Имя пользователя не может быть пустым.")

    if not password or len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")

    username = username.strip()

    users = _load_json(USERS_FILE)

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
    _save_json(USERS_FILE, users)

    portfolios = _load_json(PORTFOLIOS_FILE)

    portfolios.append(
        {
            "user_id": new_id,
            "wallets": {},
        }
    )

    _save_json(PORTFOLIOS_FILE, portfolios)

    return (
        f"Пользователь '{username}' зарегистрирован (id={new_id}). "
        f"Войдите: login --username {username} --password ****"
    )


def login_user(username: str, password: str) -> str:
    global _current_user

    if not username or not username.strip():
        raise ValueError("Имя пользователя обязателено.")

    if not password:
        raise ValueError("Пароль обязателен.")

    users = _load_json(USERS_FILE)

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

    return f"Вы вошли как '{username}'"
    
    
def show_portfolio(base: str = "USD") -> str:
    if _current_user is None:
        raise ValueError("Сначала выполните авторизацию")

    if not isinstance(base, str) or not base.strip():
        raise ValueError("Неизвестная базовая валюта ''")

    base = base.upper()

    portfolios = _load_json(PORTFOLIOS_FILE)
    portfolio_data = None
    for p in portfolios:
        if p.get("user_id") == _current_user["user_id"]:
            portfolio_data = p
            break

    if portfolio_data is None:
        portfolio_data = {"user_id": _current_user["user_id"], "wallets": {}}

    wallets_data: dict = portfolio_data.get("wallets", {})

    if not wallets_data:
        return f"Портфель пользователя '{_current_user['username']}' пуст."

    rates = _load_json(RATES_FILE) if "RATES_FILE" in globals() else None
    
    lines = []
    total = 0.0
    username = _current_user["username"]

    header = f"Портфель пользователя '{username}' (база: {base}):"
    lines.append(header)

    codes = list(wallets_data.keys())
    codes_sorted = sorted(codes)
    if base in codes_sorted:
        codes_sorted.remove(base)
        codes_sorted = [base] + codes_sorted

    for code in codes_sorted:
        wallet_info = wallets_data[code]
        bal = wallet_info.get("balance", 0.0)

        if not isinstance(bal, (int, float)):
            bal = 0.0
        bal = float(bal)

        rate = _get_rate_to_base(code, base)
        value_in_base = bal * rate
        total += value_in_base

        if code in ("BTC", "ETH"):
            bal_str = f"{bal:.4f}"
        else:
            bal_str = f"{bal:.2f}"

        lines.append(f"- {code}: {bal_str}  → {value_in_base:,.2f} {base}")

    lines.append("---------------------------------")
    lines.append(f"ИТОГО: {total:,.2f} {base}")

    return "\n".join(lines)
    

def buy_currency(currency: str, amount: float, base: str = "USD") -> str:
    if _current_user is None:
        raise ValueError("Сначала выполните login")

    if not isinstance(currency, str) or not currency.strip():
        raise ValueError("Некорректный код валюты")
    code = currency.strip().upper()

    if not isinstance(amount, (int, float)) or float(amount) <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    amount = float(amount)

    base = base.upper()

    portfolios = _load_json(PORTFOLIOS_FILE)
    portfolio_data = None
    for p in portfolios:
        if p.get("user_id") == _current_user["user_id"]:
            portfolio_data = p
            break

    if portfolio_data is None:
        portfolio_data = {"user_id": _current_user["user_id"], "wallets": {}}
        portfolios.append(portfolio_data)

    wallets: dict = portfolio_data.get("wallets", {})
    portfolio_data["wallets"] = wallets

    if code not in wallets:
        wallets[code] = {"balance": 0.0}

    old_balance = wallets[code].get("balance", 0.0)
    if not isinstance(old_balance, (int, float)):
        old_balance = 0.0
    old_balance = float(old_balance)

    new_balance = old_balance + amount
    wallets[code]["balance"] = new_balance

    _save_json(PORTFOLIOS_FILE, portfolios)

    try:
        if RATES_FILE.exists():
            with open(RATES_FILE, "r", encoding="utf-8") as f:
                rates = json.load(f)
        else:
            rates = {}
    except Exception:
        rates = {}

    pair_key = f"{code}_{base}"
    pair_data = rates.get(pair_key)

    if not isinstance(pair_data, dict) or "rate" not in pair_data:
        raise ValueError(f"Не удалось получить курс для {code}→{base}")

    rate = pair_data["rate"]
    if not isinstance(rate, (int, float)) or float(rate) <= 0:
        raise ValueError(f"Не удалось получить курс для {code}→{base}")
    rate = float(rate)

    estimated_cost = amount * rate

    def fmt_bal(cur_code: str, value: float) -> str:
        return f"{value:.4f}" if cur_code in ("BTC", "ETH") else f"{value:.2f}"

    amount_str = fmt_bal(code, amount)
    old_str = fmt_bal(code, old_balance)
    new_str = fmt_bal(code, new_balance)

    return (
        f"Покупка выполнена: {amount_str} {code} по курсу {rate:,.2f} {base}/{code}\n"
        f"Изменения в портфеле:\n"
        f"- {code}: было {old_str} → стало {new_str}\n"
        f"Оценочная стоимость покупки: {estimated_cost:,.2f} {base}"
    )


def sell_currency(currency: str, amount: float, base: str = "USD") -> str:
    if _current_user is None:
        raise ValueError("Сначала выполните login")

    if not isinstance(currency, str) or not currency.strip():
        raise ValueError("Некорректный код валюты")
    code = currency.strip().upper()

    if not isinstance(amount, (int, float)) or float(amount) <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    amount = float(amount)

    base = base.upper()

    portfolios = _load_json(PORTFOLIOS_FILE)
    portfolio_data = None
    for p in portfolios:
        if p.get("user_id") == _current_user["user_id"]:
            portfolio_data = p
            break

    if portfolio_data is None:
        portfolio_data = {"user_id": _current_user["user_id"], "wallets": {}}
        portfolios.append(portfolio_data)

    wallets: dict = portfolio_data.get("wallets", {})
    portfolio_data["wallets"] = wallets

    if code not in wallets:
        raise ValueError(
            f"У вас нет кошелька '{code}'. Добавьте валюту: она создаётся автоматически при первой покупке."
        )

    old_balance = wallets[code].get("balance", 0.0)
    if not isinstance(old_balance, (int, float)):
        old_balance = 0.0
    old_balance = float(old_balance)

    if old_balance < amount:
        def fmt_bal(cur_code: str, value: float) -> str:
            return f"{value:.4f}" if cur_code in ("BTC", "ETH") else f"{value:.2f}"

        raise ValueError(
            f"Недостаточно средств: доступно {fmt_bal(code, old_balance)} {code}, "
            f"требуется {fmt_bal(code, amount)} {code}"
        )

    new_balance = old_balance - amount
    wallets[code]["balance"] = new_balance

    try:
        if RATES_FILE.exists():
            with open(RATES_FILE, "r", encoding="utf-8") as f:
                rates = json.load(f)
        else:
            rates = {}
    except Exception:
        rates = {}

    pair_key = f"{code}_{base}"
    pair_data = rates.get(pair_key)

    if not isinstance(pair_data, dict) or "rate" not in pair_data:
        raise ValueError(f"Не удалось получить курс для {code}→{base}")

    rate = pair_data["rate"]
    if not isinstance(rate, (int, float)) or float(rate) <= 0:
        raise ValueError(f"Не удалось получить курс для {code}→{base}")
    rate = float(rate)

    revenue = amount * rate

    if base in wallets:
        usd_bal = wallets[base].get("balance", 0.0)
        if not isinstance(usd_bal, (int, float)):
            usd_bal = 0.0
        wallets[base]["balance"] = float(usd_bal) + revenue

    _save_json(PORTFOLIOS_FILE, portfolios)

    def fmt_bal(cur_code: str, value: float) -> str:
        return f"{value:.4f}" if cur_code in ("BTC", "ETH") else f"{value:.2f}"

    amount_str = fmt_bal(code, amount)
    old_str = fmt_bal(code, old_balance)
    new_str = fmt_bal(code, new_balance)

    return (
        f"Продажа выполнена: {amount_str} {code} по курсу {rate:,.2f} {base}/{code}\n"
        f"Изменения в портфеле:\n"
        f"- {code}: было {old_str} → стало {new_str}\n"
        f"Оценочная выручка: {revenue:,.2f} {base}"
    )
    

def get_rate(from_currency: str, to_currency: str) -> str:
    if not isinstance(from_currency, str) or not from_currency.strip():
        raise ValueError("Курс недоступен. Повторите попытку позже.")
    if not isinstance(to_currency, str) or not to_currency.strip():
        raise ValueError("Курс недоступен. Повторите попытку позже.")

    frm = from_currency.strip().upper()
    to = to_currency.strip().upper()

    pair_key = f"{frm}_{to}"
    reverse_key = f"{to}_{frm}"

    if RATES_FILE.exists():
        try:
            with open(RATES_FILE, "r", encoding="utf-8") as f:
                rates = json.load(f)
        except Exception:
            rates = {}
    else:
        rates = {}

    now = datetime.now()
    max_age = timedelta(minutes=5)

    def _is_fresh(updated_at_iso: str) -> bool:
        try:
            ts = datetime.fromisoformat(updated_at_iso)
        except Exception:
            return False
        return (now - ts) <= max_age

    pair_data = rates.get(pair_key)
    if isinstance(pair_data, dict) and "rate" in pair_data and "updated_at" in pair_data:
        rate_val = pair_data["rate"]
        updated_at = pair_data["updated_at"]

        if isinstance(rate_val, (int, float)) and float(rate_val) > 0 and isinstance(updated_at, str):
            if _is_fresh(updated_at):
                rate = float(rate_val)
                reverse_rate = 1.0 / rate
                updated_fmt = datetime.fromisoformat(updated_at).strftime("%Y-%m-%d %H:%M:%S")
                return (
                    f"Курс {frm}→{to}: {rate:.8f} (обновлено: {updated_fmt})\n"
                    f"Обратный курс {to}→{frm}: {reverse_rate:,.2f}"
                )

    exchange_rates_stub = {
        "EUR_USD": 1.0786,
        "BTC_USD": 59337.21,
        "RUB_USD": 0.01016,
        "ETH_USD": 3720.00,
    }

    def _get_from_stub(frm_code: str, to_code: str) -> float | None:
        direct = exchange_rates_stub.get(f"{frm_code}_{to_code}")
        if direct is not None:
            return float(direct)
        rev = exchange_rates_stub.get(f"{to_code}_{frm_code}")
        if rev is not None and float(rev) > 0:
            return 1.0 / float(rev)
        return None

    stub_rate = _get_from_stub(frm, to)
    if stub_rate is None:
        raise ValueError(f"Курс {frm}→{to} недоступен. Повторите попытку позже.")

    updated_iso = now.isoformat()
    rates[pair_key] = {"rate": stub_rate, "updated_at": updated_iso}
    rates["source"] = "Stub"
    rates["last_refresh"] = updated_iso

    with open(RATES_FILE, "w", encoding="utf-8") as f:
        json.dump(rates, f, indent=2)

    reverse_rate = 1.0 / stub_rate
    updated_fmt = now.strftime("%Y-%m-%d %H:%M:%S")

    return (
        f"Курс {frm}→{to}: {stub_rate:.8f} (обновлено: {updated_fmt})\n"
        f"Обратный курс {to}→{frm}: {reverse_rate:,.2f}"
    )
