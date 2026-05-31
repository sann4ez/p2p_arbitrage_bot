from dataclasses import dataclass

from db.dto.p2p import (
    PAYMENT_CATEGORY_FOP,
    PAYMENT_CATEGORY_OTHER,
    PAYMENT_CATEGORY_PERSON,
)


@dataclass(frozen=True)
class PaymentMethodOption:
    code: str
    name: str
    category: str


@dataclass
class PaymentMethodUpsertResult:
    fiat_code: str
    code: str
    name: str
    category: str
    created: bool


@dataclass(frozen=True)
class UserPaymentMethodOption:
    payment_method_id: int
    fiat_currency_id: int
    fiat_code: str
    code: str
    name: str
    category: str | None = None
    is_selected: bool = False


@dataclass
class UserPaymentMethodToggleResult:
    methods: list[UserPaymentMethodOption]
    changed: bool = True
    message: str = "Оновлено"


COMMON_PAYMENT_METHOD_OPTIONS = [
    PaymentMethodOption("BANK_TRANSFER", "Bank transfer", PAYMENT_CATEGORY_PERSON),
    PaymentMethodOption("SEPA", "SEPA transfer", PAYMENT_CATEGORY_PERSON),
    PaymentMethodOption("REVOLUT", "Revolut", PAYMENT_CATEGORY_PERSON),
    PaymentMethodOption("WISE", "Wise", PAYMENT_CATEGORY_PERSON),
    PaymentMethodOption("WESTERN_UNION", "Western Union", PAYMENT_CATEGORY_OTHER),
]

PAYMENT_METHOD_OPTIONS_BY_FIAT = {
    "UAH": [
        PaymentMethodOption("MONOBANK", "Monobank", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("PRIVATBANK", "PrivatBank", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("PUMB", "PUMB", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("A_BANK", "A-Bank", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("RAIFFEISEN_BANK", "Raiffeisen Bank", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("SENSE_SUPERAPP", "Sense SuperApp", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("IZIBANK", "Izibank", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("OTP_BANK", "OTP Bank", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("KREDOBANK", "KredoBank", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("OSCHAD_BANK", "Oschad Bank", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("TASCOMBANK", "Tascombank", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("IBAN", "IBAN", PAYMENT_CATEGORY_FOP),
        PaymentMethodOption("FOP", "FOP account", PAYMENT_CATEGORY_FOP),
        PaymentMethodOption("BANK_TRANSFER", "Bank transfer", PAYMENT_CATEGORY_OTHER),
        PaymentMethodOption("WESTERN_UNION", "Western Union", PAYMENT_CATEGORY_OTHER),
    ],
    "PLN": [
        PaymentMethodOption("BLIK", "BLIK", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("BANK_TRANSFER", "Bank transfer", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("REVOLUT", "Revolut", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("WISE", "Wise", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("SEPA", "SEPA transfer", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("PKO_BP", "PKO Bank Polski", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("MBANK", "mBank", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("SANTANDER_PL", "Santander Bank Polska", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("PEKAO", "Bank Pekao", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("ING_PL", "ING Bank Slaski", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("ALIOR", "Alior Bank", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("MILLENNIUM", "Bank Millennium", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("BNP_PARIBAS", "BNP Paribas", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("CREDIT_AGRICOLE_PL", "Credit Agricole", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("CITI_HANDLOWY", "Citi Handlowy", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("NEST_BANK", "Nest Bank", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("VELO_BANK", "VeloBank", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("BANK_POCZTOWY", "Bank Pocztowy", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("BOS_BANK", "BOS Bank", PAYMENT_CATEGORY_PERSON),
        PaymentMethodOption("TOYOTA_BANK", "Toyota Bank", PAYMENT_CATEGORY_PERSON),
    ],
    "USD": COMMON_PAYMENT_METHOD_OPTIONS,
    "EUR": COMMON_PAYMENT_METHOD_OPTIONS,
    "GBP": COMMON_PAYMENT_METHOD_OPTIONS,
}


def get_payment_method_options(fiat_code: str) -> list[PaymentMethodOption]:
    return PAYMENT_METHOD_OPTIONS_BY_FIAT.get(
        str(fiat_code).upper(),
        COMMON_PAYMENT_METHOD_OPTIONS,
    )


def get_payment_method_option(
    fiat_code: str,
    code: str,
) -> PaymentMethodOption | None:
    normalized_code = str(code).upper()

    for option in get_payment_method_options(fiat_code):
        if option.code == normalized_code:
            return option

    return None
