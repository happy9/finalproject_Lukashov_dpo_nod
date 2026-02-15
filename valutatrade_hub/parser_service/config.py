from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParserConfig:
    EXCHANGERATE_API_KEY: str = "16b22aada3355d80c812a29b"

    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple[str, ...] = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple[str, ...] = ("BTC", "ETH", "SOL")

    CRYPTO_ID_MAP: dict[str, str] = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )

    RATES_FILE_PATH: str = "data/rates.json"
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"
    REQUEST_TIMEOUT: int = 10

    def exchangerate_latest_url(self) -> str:
        return (
            f"{self.EXCHANGERATE_API_URL}/"
            f"{self.EXCHANGERATE_API_KEY}/latest/"
            f"{self.BASE_CURRENCY}"
        )
