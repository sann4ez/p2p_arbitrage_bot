from dataclasses import dataclass


CURRENCY_TYPE_FIAT = "fiat"
CURRENCY_TYPE_CRYPTO = "crypto"


@dataclass(frozen=True)
class CurrencyOption:
    code: str
    name: str


@dataclass
class CurrencyUpsertResult:
    currency_type: str
    code: str
    name: str
    created: bool


FIAT_CURRENCY_OPTIONS = [
    CurrencyOption("UAH", "Ukrainian hryvnia"),
    CurrencyOption("USD", "United States dollar"),
    CurrencyOption("EUR", "Euro"),
    CurrencyOption("PLN", "Polish zloty"),
    CurrencyOption("GBP", "British pound"),
    CurrencyOption("TRY", "Turkish lira"),
    CurrencyOption("KZT", "Kazakhstani tenge"),
    CurrencyOption("GEL", "Georgian lari"),
    CurrencyOption("RON", "Romanian leu"),
    CurrencyOption("CZK", "Czech koruna"),
]

CRYPTO_CURRENCY_OPTIONS = [
    CurrencyOption("USDT", "Tether USD"),
    CurrencyOption("USDC", "USD Coin"),
    CurrencyOption("BTC", "Bitcoin"),
    CurrencyOption("ETH", "Ethereum"),
    CurrencyOption("BNB", "BNB"),
    CurrencyOption("TON", "Toncoin"),
    CurrencyOption("TRX", "TRON"),
    CurrencyOption("SOL", "Solana"),
    CurrencyOption("XRP", "XRP"),
    CurrencyOption("DOGE", "Dogecoin"),
]


def get_currency_options(currency_type: str) -> list[CurrencyOption]:
    if currency_type == CURRENCY_TYPE_FIAT:
        return FIAT_CURRENCY_OPTIONS

    if currency_type == CURRENCY_TYPE_CRYPTO:
        return CRYPTO_CURRENCY_OPTIONS

    return []


def get_currency_option(currency_type: str, code: str) -> CurrencyOption | None:
    normalized_code = str(code).upper()

    for option in get_currency_options(currency_type):
        if option.code == normalized_code:
            return option

    return None
