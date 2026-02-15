class InsufficientFundsError(Exception):
    """Недостаточно средств для операции."""

    def __init__(self, available: str, required: str, code: str) -> None:
        super().__init__(
            f"Недостаточно средств: доступно {available} {code}, "
            f"требуется {required} {code}"
        )


class CurrencyNotFoundError(Exception):
    """Неизвестная валюта."""

    def __init__(self, code: str) -> None:
        super().__init__(f"Неизвестная валюта '{code}'")


class ApiRequestError(Exception):
    """Сбой внешнего API / Parser Service."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")
