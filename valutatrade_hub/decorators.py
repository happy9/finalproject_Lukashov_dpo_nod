import logging
from functools import wraps
from typing import Any, Callable

from valutatrade_hub.infra.settings import SettingsLoader


logger = logging.getLogger("valutatrade")


def log_action(action: str, verbose: bool = False) -> Callable:
    """Декоратор логирования доменных операций."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            username = kwargs.get("username")
            currency = kwargs.get("currency")
            amount = kwargs.get("amount")
            base = kwargs.get("base")

            try:
                result = func(*args, **kwargs)

                logger.info(
                    "%s user='%s' currency='%s' amount=%s base='%s' result=OK",
                    action,
                    username,
                    currency,
                    amount,
                    base,
                )

                return result

            except Exception as e:
                logger.info(
                    "%s user='%s' currency='%s' amount=%s base='%s' "
                    "result=ERROR error_type=%s error_message=\"%s\"",
                    action,
                    username,
                    currency,
                    amount,
                    base,
                    type(e).__name__,
                    str(e),
                )
                raise

        return wrapper

    return decorator
