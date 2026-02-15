import shlex
from typing import Optional

from prettytable import PrettyTable

from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.usecases import (
    buy,
    get_rate,
    login_user,
    register_user,
    sell,
    show_portfolio,
)
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import JsonRatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater

PROMPT = "> "

_current_session: dict | None = None


def _get_arg(args: list[str], name: str) -> Optional[str]:
    """Простой парсер аргументов вида --key value."""
    if name in args:
        idx = args.index(name)
        if idx + 1 < len(args):
            return args[idx + 1]
    return None


def _load_cached_rates() -> tuple[dict[str, dict], str | None]:
    db = DatabaseManager()
    raw = db.read("RATES_JSON", default={})

    if not isinstance(raw, dict) or not raw:
        return {}, None

    last_refresh = raw.get("last_refresh")

    if "pairs" in raw and isinstance(raw["pairs"], dict):
        return raw["pairs"], last_refresh

    pairs = {}
    for k, v in raw.items():
        if isinstance(k, str) and "_" in k and isinstance(v, dict):
            pairs[k] = v

    return pairs, last_refresh


def run_cli() -> None:
    print("Введите команду")

    while True:
        try:
            raw = input(PROMPT).strip()
            if not raw:
                continue

            parts = shlex.split(raw)
            command = parts[0]
            args = parts[1:]

            if command == "exit":
                print("Выход из программы.")
                break

            elif command == "register":
                username = _get_arg(args, "--username")
                password = _get_arg(args, "--password")

                if username is None or password is None:
                    print("Использование: register --username <str> --password <str>")
                    continue

                result = register_user(username, password)
                print(result)

            elif command == "login":
                username = _get_arg(args, "--username")
                password = _get_arg(args, "--password")

                if username is None or password is None:
                    print("Использование: login --username <str> --password <str>")
                    continue

                global _current_session
                _current_session = login_user(username, password)
                print(f"Вы вошли как '{_current_session['username']}'")

            elif command == "show-portfolio":
                if _current_session is None:
                    print("Сначала выполните login")
                    continue
                if _current_session is None:
                    print("Сначала выполните login")
                    continue

                base = _get_arg(args, "--base")
                result = show_portfolio(user_id=_current_session["user_id"], base=base)
                print(result)

            elif command == "buy":
                if _current_session is None:
                    print("Сначала выполните login")
                    continue

                currency = _get_arg(args, "--currency")
                amount_str = _get_arg(args, "--amount")

                if currency is None or amount_str is None:
                    print("Использование: buy --currency <str> --amount <float>")
                    continue

                try:
                    amount = float(amount_str)
                except ValueError:
                    print("'amount' должен быть положительным числом")
                    continue

                if _current_session is None:
                    print("Сначала выполните login")
                    continue

                result = buy(
                    user_id=_current_session["user_id"],
                    currency_code=currency,
                    amount=amount,
                )
                print(result)

            elif command == "sell":
                if _current_session is None:
                    print("Сначала выполните login")
                    continue

                currency = _get_arg(args, "--currency")
                amount_str = _get_arg(args, "--amount")

                if currency is None or amount_str is None:
                    print("Использование: sell --currency <str> --amount <float>")
                    continue

                try:
                    amount = float(amount_str)
                except ValueError:
                    print("'amount' должен быть положительным числом")
                    continue

                if _current_session is None:
                    print("Сначала выполните login")
                    continue

                result = sell(
                    user_id=_current_session["user_id"],
                    currency_code=currency,
                    amount=amount,
                )
                print(result)

            elif command == "get-rate":
                frm = _get_arg(args, "--from")
                to = _get_arg(args, "--to")

                if frm is None or to is None:
                    print("Использование: get-rate --from <str> --to <str>")
                    continue

                rate, updated_at = get_rate(frm, to)
                print(
                    f"Курс {frm.upper()}→{to.upper()}: {rate:.8f} "+\
                    "(обновлено: {updated_at})"
                )

                if rate > 0:
                    reverse = 1.0 / rate
                    print(f"Обратный курс {to.upper()}→{frm.upper()}: {reverse:.8f}")

            elif command == "show-rates":
                currency = _get_arg(args, "--currency")
                top_str = _get_arg(args, "--top")
                base = _get_arg(args, "--base")

                currency = currency.upper() if currency else None
                base = base.upper() if base else None

                top_n: int | None = None
                if top_str:
                    try:
                        top_n = int(top_str)
                        if top_n <= 0:
                            raise ValueError
                    except ValueError:
                        print("Параметр --top должен быть целым числом > 0")
                        continue

                pairs, last_refresh = _load_cached_rates()

                if not pairs:
                    print(
                        "Локальный кеш курсов пуст. "
                        "Выполните 'update-rates', чтобы загрузить данные."
                    )
                    continue

                rows: list[tuple[str, float, str, str]] = []

                for pair, payload in pairs.items():
                    if not isinstance(payload, dict):
                        continue

                    rate = payload.get("rate")
                    updated_at = payload.get("updated_at")
                    source = payload.get("source", "-")

                    if not isinstance(rate, (int, float)):
                        continue
                    if not isinstance(updated_at, str):
                        continue

                    pair = pair.upper()

                    if base and not pair.endswith(f"_{base}"):
                        continue

                    if currency:
                        frm, to = pair.split("_", 1)
                        if currency not in (frm, to):
                            continue

                    rows.append((pair, float(rate), updated_at, source))

                if not rows:
                    if currency:
                        print(f"Курс для '{currency}' не найден в кеше.")
                    else:
                        print("Нет данных для отображения.")
                    continue

                if top_n is not None:
                    rows.sort(key=lambda x: x[1], reverse=True)
                    rows = rows[:top_n]
                else:
                    rows.sort(key=lambda x: x[0])

                table = PrettyTable()
                table.field_names = ["PAIR", "RATE", "UPDATED AT", "SOURCE"]
                table.align["PAIR"] = "l"

                for pair, rate, updated_at, source in rows:
                    table.add_row([pair, f"{rate:,.6f}", updated_at, source])

                if last_refresh:
                    print(f"Rates from cache (updated at {last_refresh}):")
                else:
                    print("Rates from cache:")

                print(table)

            elif command == "update-rates":
                source = _get_arg(args, "--source")
                if source is not None:
                    source = source.strip().lower()

                print("INFO: Starting rates update...")

                cfg = ParserConfig()
                storage = JsonRatesStorage(cfg)

                clients = []
                if source is None:
                    clients = [CoinGeckoClient(cfg), ExchangeRateApiClient(cfg)]
                elif source == "coingecko":
                    clients = [CoinGeckoClient(cfg)]
                elif source == "exchangerate":
                    clients = [ExchangeRateApiClient(cfg)]
                else:
                    print(
                        "Использование: update-rates "
                        + "[--source coingecko|exchangerate]"
                    )
                    continue

                updater = RatesUpdater(clients=clients, storage=storage)

                try:
                    snapshot = updater.run_update()
                    pairs = snapshot.get("pairs", {})
                    last_refresh = snapshot.get("last_refresh")

                    total = len(pairs) if isinstance(pairs, dict) else 0
                    print(f"INFO: Writing {total} rates to data/rates.json...")
                    print(
                        f"Update successful. Total rates updated: {total}. "
                        f"Last refresh: {last_refresh}"
                    )

                except ApiRequestError as e:
                    print(f"ERROR: {e}")
                    print(
                        "Update completed with errors. "
                        + "Check logs/actions.log for details."
                    )

            else:
                print(f"Неизвестная команда: {command}")

        except InsufficientFundsError as e:
            print(str(e))
        except CurrencyNotFoundError as e:
            print(str(e))
            print(
                "Подсказка: используйте get-rate --from "
                + "<CODE> --to <CODE> или проверьте список поддерживаемых валют."
            )
        except ApiRequestError as e:
            print(str(e))
            print("Повторите попытку позже или проверьте сеть/источник курсов.")
        except Exception as e:
            print(e)
