from dataclasses import dataclass, field
from typing import Any


PAYMENT_CATEGORY_FOP = "fop"
PAYMENT_CATEGORY_PERSON = "person"
PAYMENT_CATEGORY_OTHER = "other"

PAYMENT_CATEGORIES = {
    PAYMENT_CATEGORY_FOP,
    PAYMENT_CATEGORY_PERSON,
    PAYMENT_CATEGORY_OTHER,
}

DEFAULT_DISPLAY_ORDER_COUNT = 5
DEFAULT_CANDIDATE_ORDER_COUNT = 20

DESCRIPTION_CHECK_REGEX = "regex"
DESCRIPTION_CHECK_GPT = "gpt"
DESCRIPTION_CHECK_MODE_OPTIONS = [
    DESCRIPTION_CHECK_REGEX,
    DESCRIPTION_CHECK_GPT,
]

ORDER_MINUTES_OPTIONS = [None, 15, 30, 60]
MIN_TRADES_OPTIONS = [None, 50, 100, 200, 500, 1000]
MIN_PERCENT_OPTIONS = [None, 90.0, 95.0, 98.0, 99.0]
DISPLAY_ORDER_COUNT_OPTIONS = [3, 5, 10, 15, 20]
CANDIDATE_ORDER_COUNT_OPTIONS = [20, 50, 100, 150, 200]


@dataclass
class P2PFilterSettings:
    max_order_minutes: int | None = None
    min_trades: int | None = None
    min_rating: float | None = None
    min_completion: float | None = None
    payment_categories: set[str] = field(default_factory=lambda: set(PAYMENT_CATEGORIES))
    allow_third_party_payments: bool = True
    allow_split_payments: bool = True
    display_order_count: int = DEFAULT_DISPLAY_ORDER_COUNT
    candidate_order_count: int = DEFAULT_CANDIDATE_ORDER_COUNT
    description_check_mode: str = DESCRIPTION_CHECK_REGEX


@dataclass
class P2PDescriptionClassification:
    split_payments: bool = False
    third_party_payments: bool = False
    confidence: float = 0.0
    reason: str = ""


@dataclass
class P2POrderMessage:
    merchant: str
    price: Any
    min_amount: Any
    max_amount: Any
    payment_methods: str = ""
    available: Any | None = None
    orders_count: Any | None = None
    rating: str | None = None
    completion_rate: str | None = None
    trade_minutes: Any | None = None
    description: str | None = None
    order_url: str | None = None
