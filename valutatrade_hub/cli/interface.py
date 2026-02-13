import shlex
from typing import Optional

from valutatrade_hub.core.usecases import (
    register_user,
    login_user,
    show_portfolio,
    buy,
    sell,
    get_rate,
)

from valutatrade_hub.core.exceptions import (
    InsufficientFundsError,
    CurrencyNotFoundError,
    ApiRequestError,
)

PROMPT = "> "

_current_session: dict | None = None


def _get_arg(args: list[str], name: str) -> Optional[str]:
    """Простой парсер аргументов вида --key value."""
    if name in args:
        idx = args.index(name)
        if idx + 1 < len(args):
            return args[idx + 1]
    return None


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

                result = get_rate(frm, to)
                print(result)

            else:
                print(f"Неизвестная команда: {command}")

        except InsufficientFundsError as e:
            print(str(e))
        except CurrencyNotFoundError as e:
            print(str(e))
            print("Подсказка: используйте get-rate --from <CODE> --to <CODE> или проверьте список поддерживаемых валют.")
        except ApiRequestError as e:
            print(str(e))
            print("Повторите попытку позже или проверьте сеть/источник курсов.")
        except Exception as e:
            print(e)


