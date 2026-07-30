import os

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from config import Config
from db.dto import (
    CANDIDATE_ORDER_COUNT_OPTIONS,
    DESCRIPTION_CHECK_GPT,
    DESCRIPTION_CHECK_MODE_OPTIONS,
    DESCRIPTION_CHECK_REGEX_GPT,
    DISPLAY_ORDER_COUNT_OPTIONS,
    MIN_PERCENT_OPTIONS,
    MIN_TRADES_OPTIONS,
    ORDER_MINUTES_OPTIONS,
    PAYMENT_CATEGORY_FOP,
    PAYMENT_CATEGORY_OTHER,
    PAYMENT_CATEGORY_PERSON,
    get_currency_options,
    get_payment_method_options,
)


BINANCE_ICON_CUSTOM_EMOJI_ID = os.getenv("BINANCE_ICON_CUSTOM_EMOJI_ID")
OKX_ICON_CUSTOM_EMOJI_ID = os.getenv("OKX_ICON_CUSTOM_EMOJI_ID")

BTN_BINANCE = "Binance" if BINANCE_ICON_CUSTOM_EMOJI_ID else "🟡 Binance"
BTN_OKX = "OKX" if OKX_ICON_CUSTOM_EMOJI_ID else "⚫ OKX"
BTN_P2P = "💱 P2P"
BTN_KNOWLEDGE_BASE = "🧠 P2P база знань"
BTN_STATISTICS = "📊 Статистика"
BTN_CABINET = "👤 Особистий кабінет"
BTN_P2P_RECOMMENDATIONS = "💡 AI-рекомендації"
BTN_ADMIN_PANEL = "🛠 Адмін панель"
BTN_ADMIN_CURRENCIES = "🪙 Валюти"
BTN_ADMIN_PAYMENT_METHODS = "🏦 Методи оплати"
BTN_ADMIN_STATISTICS = "📊 Налаштування статистики"
BTN_ADD_FIAT_CURRENCY = "➕ Додати фіат"
BTN_ADD_CRYPTO_CURRENCY = "➕ Додати крипту"
BTN_LIST_CURRENCIES = "📋 Список валют"
BTN_MY_INFO = "ℹ️ Інфо про себе"
BTN_SHARE_LOCATION = "📍 Поділитися геолокацією"
BTN_P2P_FILTERS = "⚙️ Фільтри P2P"
BTN_P2P_PAIRS = "💹 Мої P2P пари"
BTN_USER_PAYMENT_METHODS = "🏦 Мої банки"
BTN_UAH_TO_USDT = "₴ Фіат → ₮ Крипта"
BTN_USDT_TO_UAH = "₮ Крипта → ₴ Фіат"
BTN_MIXED_DIRECTION = "🔀 Змішаний"
BTN_BACK = "⬅️ Назад"
BTN_RESET_FILTERS = "♻️ Скинути фільтри"

BTN_FILTER_ORDER_TIME_PREFIX = "⏱ Час:"
BTN_FILTER_MIN_TRADES_PREFIX = "📊 Угоди:"
BTN_FILTER_DISPLAY_COUNT_PREFIX = "📋 Виводити:"
BTN_FILTER_CANDIDATE_COUNT_PREFIX = "🔍 Кандидати:"
BTN_FILTER_DESCRIPTION_CHECK_PREFIX = "🔎 Перевірка:"
BTN_FILTER_MIN_RATING_PREFIX = "⭐ Оцінка:"
BTN_FILTER_MIN_COMPLETION_PREFIX = "✅ Виконання:"
BTN_FILTER_FOP_PREFIX = "🏦 ФОП/ТОВ/IBAN:"
BTN_FILTER_PERSON_PREFIX = "👤 Фізособа/карта:"
BTN_FILTER_OTHER_PREFIX = "🌐 Інші методи:"
BTN_FILTER_THIRD_PARTY_PREFIX = "🧾 Треті особи:"
BTN_FILTER_SPLIT_PAYMENTS_PREFIX = "🧩 Кілька платежів:"
BTN_FILTER_MONOBANK_JAR_PREFIX = "🫙 Банка/збір/конверт:"

CB_FILTERS_MENU = "p2pf:menu"
CB_FILTERS_RESET = "p2pf:reset"
CB_FILTERS_SCREEN_PREFIX = "p2pf:screen:"
CB_FILTERS_SET_PREFIX = "p2pf:set:"
CB_FILTERS_PAY_PREFIX = "p2pf:pay:"
CB_ADMIN_CURRENCIES_MENU = "admcur:menu"
CB_ADMIN_CURRENCY_ADD_PREFIX = "admcur:add:"
CB_ADMIN_PAYMENT_ADD_PREFIX = "admpay:add:"
CB_ADMIN_PAYMENT_FIAT_PREFIX = "admpay:fiat:"
CB_ADMIN_PAYMENT_FIATS_MENU = "admpay:fiats"
CB_ADMIN_STATS_MENU = "admstats:menu"
CB_ADMIN_STATS_EXCHANGES_MENU = "admstats:exchanges"
CB_ADMIN_STATS_BANKS_MENU = "admstats:banks"
CB_ADMIN_STATS_RUN = "admstats:run"
CB_ADMIN_STATS_RESET = "admstats:reset"
CB_ADMIN_STATS_EXCHANGE_TOGGLE_PREFIX = "admstats:exchange:"
CB_ADMIN_STATS_TOGGLE_PREFIX = "admstats:toggle:"
CB_ADMIN_STATS_FILTER_PREFIX = "admstats:filter:"
CB_ADMIN_STATS_SET_PREFIX = "admstats:set:"
CB_ADMIN_STATS_AMOUNT_PREFIX = "admstats:amount:"
CB_ADMIN_STATS_PAY_PREFIX = "admstats:pay:"
CB_ADMIN_STATS_BANK_FIAT_PREFIX = "admstats:bank_fiat:"
CB_ADMIN_STATS_BANK_TOGGLE_PREFIX = "admstats:bank:"
CB_P2P_EXCHANGE_BACK = "p2pex:back"
CB_P2P_EXCHANGE_MENU = "p2pex:menu"
CB_P2P_EXCHANGE_PREFIX = "p2pex:"
CB_P2P_PAIR_BACK = "p2ppair:back"
CB_P2P_PAIR_CRYPTO_PREFIX = "p2ppair:crypto:"
CB_P2P_PAIR_NOOP = "p2ppair:noop"
CB_P2P_PAIR_SELECT_BACK_PREFIX = "p2ppair:select_back:"
CB_P2P_PAIR_SELECT_CRYPTO_PREFIX = "p2ppair:select_crypto:"
CB_P2P_PAIR_SELECT_PREFIX = "p2ppair:select:"
CB_P2P_DIRECTION_PREFIX = "p2pdir:"
CB_P2P_PAIR_TOGGLE_PREFIX = "p2ppair:toggle:"
CB_USER_PAYMENT_BACK = "userpay:back"
CB_USER_PAYMENT_FIAT_PREFIX = "userpay:fiat:"
CB_USER_PAYMENT_TOGGLE_PREFIX = "userpay:toggle:"
CB_STATS_SCOPE_PREFIX = "stats:scope:"
CB_STATS_PERIOD_PREFIX = "stats:period:"
CB_STATS_DATE_PREFIX = "stats:date:"
CB_STATS_DATE_PREV = "stats:date:prev"
CB_STATS_DATE_NEXT = "stats:date:next"
CB_STATS_DATE_TODAY = "stats:date:today"
CB_STATS_DATE_PICK = "stats:date:pick"
CB_STATS_PAIR_BACK = "stats:pair_back"
CB_STATS_PAIR_CRYPTO_PREFIX = "stats:crypto:"
CB_STATS_PAIR_SELECT_PREFIX = "stats:pair:"
CB_STATS_EXCHANGE_PREFIX = "stats:exchange:"
CB_STATS_DIRECTION_PREFIX = "stats:direction:"

FILTER_SCREEN_ORDER_TIME = "time"
FILTER_SCREEN_MIN_ORDER_AMOUNT = "min_amount"
FILTER_SCREEN_MAX_ORDER_AMOUNT = "max_amount"
FILTER_SCREEN_MIN_TRADES = "trades"
FILTER_SCREEN_MIN_RATING = "rating"
FILTER_SCREEN_MIN_COMPLETION = "completion"
FILTER_SCREEN_PAYMENT_METHODS = "pay_methods"
FILTER_SCREEN_THIRD_PARTY = "third_party"
FILTER_SCREEN_SPLIT_PAYMENTS = "split"
FILTER_SCREEN_MONOBANK_JAR = "mono_jar"
FILTER_SCREEN_DESCRIPTION_CHECK = "desc"
FILTER_SCREEN_DISPLAY_COUNT = "display"
FILTER_SCREEN_CANDIDATE_COUNT = "candidates"


def root_menu_kb(
    can_view_admin: bool = False,
    can_use_knowledge_base: bool = False,
):
    keyboard = [
        [
            KeyboardButton(text=BTN_P2P),
            KeyboardButton(text=BTN_CABINET),
        ],
        [
            KeyboardButton(text=BTN_STATISTICS),
        ],
    ]

    if can_use_knowledge_base:
        keyboard.append([KeyboardButton(text=BTN_KNOWLEDGE_BASE)])

    if can_view_admin:
        keyboard.append([KeyboardButton(text=BTN_ADMIN_PANEL)])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def p2p_exchange_inline_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN_BINANCE,
                    callback_data=f"{CB_P2P_EXCHANGE_PREFIX}binance",
                ),
                InlineKeyboardButton(
                    text=BTN_OKX,
                    callback_data=f"{CB_P2P_EXCHANGE_PREFIX}okx",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=BTN_BACK,
                    callback_data=CB_P2P_EXCHANGE_BACK,
                ),
            ],
        ]
    )


def cabinet_kb(telegram_id: int | None = None):
    rows = [
        [
            KeyboardButton(text=BTN_MY_INFO),
            KeyboardButton(text=BTN_P2P_FILTERS),
        ],
        [
            KeyboardButton(text=BTN_P2P_PAIRS),
            KeyboardButton(text=BTN_USER_PAYMENT_METHODS),
        ],
        [
            KeyboardButton(text=BTN_SHARE_LOCATION, request_location=True),
        ],
    ]

    if (
        Config.P2P_RECOMMENDATIONS_ENABLED
        and telegram_id in Config.P2P_RECOMMENDATIONS_TELEGRAM_IDS
    ):
        rows.append([KeyboardButton(text=BTN_P2P_RECOMMENDATIONS)])

    rows.append([KeyboardButton(text=BTN_BACK)])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
    )


def knowledge_base_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=BTN_BACK),
            ],
        ],
        resize_keyboard=True,
    )


def admin_menu_kb(
    can_manage_currencies: bool = False,
    can_manage_payment_methods: bool = False,
    can_manage_statistics: bool = False,
):
    keyboard = []

    if can_manage_currencies:
        keyboard.append([KeyboardButton(text=BTN_ADMIN_CURRENCIES)])

    if can_manage_payment_methods:
        keyboard.append([KeyboardButton(text=BTN_ADMIN_PAYMENT_METHODS)])

    if can_manage_statistics:
        keyboard.append([KeyboardButton(text=BTN_ADMIN_STATISTICS)])

    keyboard.append([KeyboardButton(text=BTN_BACK)])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def admin_currencies_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=BTN_ADD_FIAT_CURRENCY),
                KeyboardButton(text=BTN_ADD_CRYPTO_CURRENCY),
            ],
            [
                KeyboardButton(text=BTN_LIST_CURRENCIES),
            ],
            [
                KeyboardButton(text=BTN_BACK),
            ],
        ],
        resize_keyboard=True,
    )


def admin_currency_options_inline_kb(
    currency_type: str,
    existing_codes: set[str] | None = None,
):
    existing_codes = existing_codes or set()
    rows = []

    for option in get_currency_options(currency_type):
        rows.append(
            [
                InlineKeyboardButton(
                    text=format_currency_option_label(option, existing_codes),
                    callback_data=(
                        f"{CB_ADMIN_CURRENCY_ADD_PREFIX}"
                        f"{currency_type}:{option.code}"
                    ),
                ),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ До валют",
                callback_data=CB_ADMIN_CURRENCIES_MENU,
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_payment_fiats_inline_kb(fiat_currencies, method_counts: dict[int, int]):
    rows = []

    for fiat in fiat_currencies:
        count = method_counts.get(fiat.id, 0)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{fiat.code} · {count} методів",
                    callback_data=f"{CB_ADMIN_PAYMENT_FIAT_PREFIX}{fiat.id}",
                ),
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_payment_options_inline_kb(fiat, existing_codes: set[str] | None = None):
    existing_codes = existing_codes or set()
    rows = []

    for option in get_payment_method_options(fiat.code):
        rows.append(
            [
                InlineKeyboardButton(
                    text=format_payment_method_option_label(option, existing_codes),
                    callback_data=(
                        f"{CB_ADMIN_PAYMENT_ADD_PREFIX}"
                        f"{fiat.id}:{option.code}"
                    ),
                ),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ До валют",
                callback_data=CB_ADMIN_PAYMENT_FIATS_MENU,
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_statistics_inline_kb(settings, filter_settings):
    rows = [
        [
            InlineKeyboardButton(
                text=toggle_label("Автостатистика", settings.is_enabled),
                callback_data=f"{CB_ADMIN_STATS_TOGGLE_PREFIX}is_enabled",
            ),
        ],
        [
            InlineKeyboardButton(
                text=toggle_label("Купівля крипти", settings.scan_buy),
                callback_data=f"{CB_ADMIN_STATS_TOGGLE_PREFIX}scan_buy",
            ),
            InlineKeyboardButton(
                text=toggle_label("Продаж крипти", settings.scan_sell),
                callback_data=f"{CB_ADMIN_STATS_TOGGLE_PREFIX}scan_sell",
            ),
        ],
    ]
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text=(
                        "💵 Сума від: "
                        f"{format_order_amount_bound(filter_settings.min_order_amount)}"
                    ),
                    callback_data=(
                        f"{CB_ADMIN_STATS_AMOUNT_PREFIX}"
                        f"{FILTER_SCREEN_MIN_ORDER_AMOUNT}"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=(
                        "💵 Сума до: "
                        f"{format_order_amount_bound(filter_settings.max_order_amount)}"
                    ),
                    callback_data=(
                        f"{CB_ADMIN_STATS_AMOUNT_PREFIX}"
                        f"{FILTER_SCREEN_MAX_ORDER_AMOUNT}"
                    ),
                ),
            ],
        ]
    )
    rows.extend(
        p2p_filters_inline_kb(
            filter_settings,
            screen_prefix=CB_ADMIN_STATS_FILTER_PREFIX,
            reset_callback=CB_ADMIN_STATS_RESET,
            reset_text="♻️ Скинути фільтри статистики",
        ).inline_keyboard
    )
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="🏛 Біржі",
                    callback_data=CB_ADMIN_STATS_EXCHANGES_MENU,
                ),
                InlineKeyboardButton(
                    text="🏦 Банки",
                    callback_data=CB_ADMIN_STATS_BANKS_MENU,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="▶️ Запустити зараз",
                    callback_data=CB_ADMIN_STATS_RUN,
                ),
            ],
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_statistics_amount_input_inline_kb(field: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="♻️ Без обмеження",
                    callback_data=f"{CB_ADMIN_STATS_SET_PREFIX}{field}:none",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ До статистики",
                    callback_data=CB_ADMIN_STATS_MENU,
                ),
            ],
        ]
    )


def admin_statistics_exchanges_inline_kb(settings):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=selected_label(settings.scan_binance, "Binance"),
                    callback_data=f"{CB_ADMIN_STATS_EXCHANGE_TOGGLE_PREFIX}scan_binance",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=selected_label(settings.scan_okx, "OKX"),
                    callback_data=f"{CB_ADMIN_STATS_EXCHANGE_TOGGLE_PREFIX}scan_okx",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ До статистики",
                    callback_data=CB_ADMIN_STATS_MENU,
                ),
            ],
        ]
    )


def admin_statistics_bank_fiats_inline_kb(fiat_currencies, selected_counts: dict[int, int]):
    rows = []

    for fiat in fiat_currencies:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{fiat.code} · {selected_counts.get(fiat.id, 0)} обрано",
                    callback_data=f"{CB_ADMIN_STATS_BANK_FIAT_PREFIX}{fiat.id}",
                ),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ До статистики",
                callback_data=CB_ADMIN_STATS_MENU,
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_statistics_bank_methods_inline_kb(methods, selected_ids: set[int]):
    rows = []

    for method in methods:
        rows.append(
            [
                InlineKeyboardButton(
                    text=selected_label(method.id in selected_ids, method.name),
                    callback_data=f"{CB_ADMIN_STATS_BANK_TOGGLE_PREFIX}{method.id}",
                ),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ До валют",
                callback_data=CB_ADMIN_STATS_BANKS_MENU,
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_payment_fiats_inline_kb(fiat_currencies, selected_counts: dict[int, int]):
    rows = []

    for fiat in fiat_currencies:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{fiat.code} · {selected_counts.get(fiat.id, 0)} обрано",
                    callback_data=f"{CB_USER_PAYMENT_FIAT_PREFIX}{fiat.id}",
                ),
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_payment_methods_inline_kb(methods):
    rows = []

    for method_row in chunked(methods, 2):
        rows.append(
            [
                InlineKeyboardButton(
                    text=format_user_payment_method_label(method),
                    callback_data=(
                        f"{CB_USER_PAYMENT_TOGGLE_PREFIX}"
                        f"{method.payment_method_id}"
                    ),
                )
                for method in method_row
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ До валют",
                callback_data=CB_USER_PAYMENT_BACK,
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def statistics_scope_inline_kb(pair=None, exchange: str | None = None, direction: str | None = None):
    suffix = format_statistics_selection_suffix(pair, exchange, direction)
    back_callback = (
        format_statistics_exchange_callback(pair, exchange)
        if pair and exchange
        else CB_STATS_PAIR_BACK
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌍 Загальна статистика",
                    callback_data=f"{CB_STATS_SCOPE_PREFIX}global{suffix}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎯 За моїми фільтрами",
                    callback_data=f"{CB_STATS_SCOPE_PREFIX}filter{suffix}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ До напрямку",
                    callback_data=back_callback,
                ),
            ],
        ]
    )


def statistics_period_inline_kb(
    current_period: str,
    scope: str = "global",
    pair=None,
    exchange: str | None = None,
    direction: str | None = None,
    selected_period_label: str | None = None,
):
    options = [
        ("hour", "Година"),
        ("day", "День"),
        ("week", "Тиждень"),
        ("month", "Місяць"),
        ("year", "Рік"),
    ]
    suffix = format_statistics_selection_suffix(pair, exchange, direction)
    range_controls = get_statistics_range_controls(current_period)

    rows = [
        [
            InlineKeyboardButton(
                text=selected_label(current_period == period, label),
                callback_data=f"{CB_STATS_PERIOD_PREFIX}{scope}:{period}{suffix}",
            )
            for period, label in options[:2]
        ],
        [
            InlineKeyboardButton(
                text=selected_label(current_period == period, label),
                callback_data=f"{CB_STATS_PERIOD_PREFIX}{scope}:{period}{suffix}",
            )
            for period, label in options[2:4]
        ],
        [
            InlineKeyboardButton(
                text=selected_label(current_period == options[4][0], options[4][1]),
                callback_data=f"{CB_STATS_PERIOD_PREFIX}{scope}:{options[4][0]}{suffix}",
            ),
        ],
    ]

    if range_controls:
        rows.extend(
            [
                [
                    InlineKeyboardButton(
                        text=f"⬅️ {range_controls['unit']}",
                        callback_data=CB_STATS_DATE_PREV,
                    ),
                    InlineKeyboardButton(
                        text=range_controls["current"],
                        callback_data=CB_STATS_DATE_TODAY,
                    ),
                    InlineKeyboardButton(
                        text=f"{range_controls['unit']} ➡️",
                        callback_data=CB_STATS_DATE_NEXT,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=f"✍️ {range_controls['input']}",
                        callback_data=CB_STATS_DATE_PICK,
                    ),
                ],
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ До вибору статистики",
                callback_data=f"{CB_STATS_SCOPE_PREFIX}menu{suffix}",
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_statistics_range_controls(period: str) -> dict[str, str] | None:
    controls = {
        "hour": {
            "label": "📅 Дата",
            "unit": "День",
            "current": "Сьогодні",
            "input": "Ввести дату",
        },
        "day": {
            "label": "📅 Місяць",
            "unit": "Місяць",
            "current": "Цей місяць",
            "input": "Ввести місяць",
        },
        "week": {
            "label": "📅 Рік",
            "unit": "Рік",
            "current": "Цей рік",
            "input": "Ввести рік",
        },
        "month": {
            "label": "📅 Рік",
            "unit": "Рік",
            "current": "Цей рік",
            "input": "Ввести рік",
        },
        "year": {
            "label": "📅 Діапазон",
            "unit": "10 років",
            "current": "Це десятиліття",
            "input": "Ввести рік",
        },
    }

    return controls.get(period)


def statistics_exchange_choice_inline_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN_BINANCE,
                    callback_data=f"{CB_STATS_EXCHANGE_PREFIX}binance",
                ),
                InlineKeyboardButton(
                    text=BTN_OKX,
                    callback_data=f"{CB_STATS_EXCHANGE_PREFIX}okx",
                ),
            ],
        ]
    )


def statistics_exchange_inline_kb(pair):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN_BINANCE,
                    callback_data=format_statistics_exchange_callback(pair, "binance"),
                ),
                InlineKeyboardButton(
                    text=BTN_OKX,
                    callback_data=format_statistics_exchange_callback(pair, "okx"),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ До вибору пари",
                    callback_data=CB_STATS_PAIR_BACK,
                ),
            ],
        ]
    )


def statistics_direction_inline_kb(pair, exchange: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN_UAH_TO_USDT,
                    callback_data=format_statistics_direction_callback(
                        pair,
                        exchange,
                        "fiat_crypto",
                    ),
                ),
                InlineKeyboardButton(
                    text=BTN_USDT_TO_UAH,
                    callback_data=format_statistics_direction_callback(
                        pair,
                        exchange,
                        "crypto_fiat",
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=BTN_MIXED_DIRECTION,
                    callback_data=format_statistics_direction_callback(
                        pair,
                        exchange,
                        "mixed",
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ До бірж",
                    callback_data=f"{CB_STATS_EXCHANGE_PREFIX}back",
                ),
            ],
        ]
    )


def statistics_pair_cryptos_inline_kb(pairs, back_callback: str | None = None):
    rows = []

    for crypto_code, crypto_pairs in group_pairs_by_crypto(pairs):
        rows.append(
            [
                InlineKeyboardButton(
                    text=format_exchange_crypto_button_text(crypto_code, crypto_pairs),
                    callback_data=(
                        f"{CB_STATS_PAIR_CRYPTO_PREFIX}"
                        f"{crypto_pairs[0].crypto_currency_id}"
                    ),
                ),
            ]
        )

    if back_callback:
        rows.append(
            [
                InlineKeyboardButton(
                    text="⬅️ До бірж",
                    callback_data=back_callback,
                ),
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def statistics_pair_fiats_inline_kb(
    pairs,
    crypto_currency_id: int,
    back_callback: str = CB_STATS_PAIR_BACK,
):
    rows = []
    crypto_pairs = [
        pair
        for pair in pairs
        if pair.crypto_currency_id == crypto_currency_id
    ]

    for pair_row in chunked(crypto_pairs, 3):
        rows.append(
            [
                InlineKeyboardButton(
                    text=pair.fiat_code,
                    callback_data=(
                        f"{CB_STATS_PAIR_SELECT_PREFIX}"
                        f"{pair.crypto_currency_id}:{pair.fiat_currency_id}"
                    ),
                )
                for pair in pair_row
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ До стейблів",
                callback_data=back_callback,
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_statistics_pair_suffix(pair) -> str:
    if not pair:
        return ""

    return f":{pair.crypto_currency_id}:{pair.fiat_currency_id}"


def format_statistics_selection_suffix(
    pair,
    exchange: str | None = None,
    direction: str | None = None,
) -> str:
    if not pair or not exchange or not direction:
        return format_statistics_pair_suffix(pair)

    return (
        f":{exchange}:{direction}:"
        f"{pair.crypto_currency_id}:{pair.fiat_currency_id}"
    )


def format_statistics_exchange_callback(pair, exchange: str | None) -> str:
    if not pair or not exchange:
        return CB_STATS_PAIR_BACK

    return (
        f"{CB_STATS_EXCHANGE_PREFIX}{exchange}:"
        f"{pair.crypto_currency_id}:{pair.fiat_currency_id}"
    )


def format_statistics_direction_callback(pair, exchange: str, direction: str) -> str:
    return (
        f"{CB_STATS_DIRECTION_PREFIX}{exchange}:{direction}:"
        f"{pair.crypto_currency_id}:{pair.fiat_currency_id}"
    )


def p2p_pairs_inline_kb(pairs):
    return p2p_pair_cryptos_inline_kb(pairs)


def p2p_pair_cryptos_inline_kb(pairs):
    rows = []

    for crypto_code, crypto_pairs in group_pairs_by_crypto(pairs):
        rows.append(
            [
                InlineKeyboardButton(
                    text=format_crypto_pair_button_text(crypto_code, crypto_pairs),
                    callback_data=(
                        f"{CB_P2P_PAIR_CRYPTO_PREFIX}"
                        f"{crypto_pairs[0].crypto_currency_id}"
                    ),
                ),
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def p2p_pair_fiats_inline_kb(pairs, crypto_currency_id: int):
    rows = []
    crypto_pairs = [
        pair
        for pair in pairs
        if pair.crypto_currency_id == crypto_currency_id
    ]

    for pair_row in chunked(crypto_pairs, 3):
        rows.append(
            [
                InlineKeyboardButton(
                    text=format_pair_button_text(pair, selected_mode=False),
                    callback_data=(
                        f"{CB_P2P_PAIR_TOGGLE_PREFIX}"
                        f"{pair.crypto_currency_id}:{pair.fiat_currency_id}"
                    ),
                )
                for pair in pair_row
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ До стейблів",
                callback_data=CB_P2P_PAIR_BACK,
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def p2p_pair_select_cryptos_inline_kb(pairs, exchange: str):
    rows = []

    for crypto_code, crypto_pairs in group_pairs_by_crypto(pairs):
        rows.append(
            [
                InlineKeyboardButton(
                    text=format_exchange_crypto_button_text(crypto_code, crypto_pairs),
                    callback_data=(
                        f"{CB_P2P_PAIR_SELECT_CRYPTO_PREFIX}"
                        f"{exchange}:{crypto_pairs[0].crypto_currency_id}"
                    ),
                ),
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def p2p_pair_select_fiats_inline_kb(
    pairs,
    exchange: str,
    crypto_currency_id: int,
    *,
    back_callback: str | None = None,
    back_text: str = "⬅️ До стейблів",
):
    rows = []
    crypto_pairs = [
        pair
        for pair in pairs
        if pair.crypto_currency_id == crypto_currency_id
    ]

    for pair_row in chunked(crypto_pairs, 3):
        rows.append(
            [
                InlineKeyboardButton(
                    text=pair.fiat_code,
                    callback_data=(
                        f"{CB_P2P_PAIR_SELECT_PREFIX}"
                        f"{exchange}:{pair.crypto_currency_id}:{pair.fiat_currency_id}"
                    ),
                )
                for pair in pair_row
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text=back_text,
                callback_data=(
                    back_callback
                    or f"{CB_P2P_PAIR_SELECT_BACK_PREFIX}{exchange}"
                ),
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def p2p_directions_inline_kb(
    exchange: str,
    pair,
    *,
    back_callback: str | None = None,
    back_text: str = "⬅️ До фіату",
):
    suffix = f"{exchange}:{pair.crypto_currency_id}:{pair.fiat_currency_id}"
    back_callback = back_callback or (
        f"{CB_P2P_PAIR_SELECT_CRYPTO_PREFIX}"
        f"{exchange}:{pair.crypto_currency_id}"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN_UAH_TO_USDT,
                    callback_data=f"{CB_P2P_DIRECTION_PREFIX}fiat_crypto:{suffix}",
                ),
                InlineKeyboardButton(
                    text=BTN_USDT_TO_UAH,
                    callback_data=f"{CB_P2P_DIRECTION_PREFIX}crypto_fiat:{suffix}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=back_text,
                    callback_data=back_callback,
                ),
            ],
        ]
    )


def group_pairs_by_crypto(pairs):
    grouped = {}

    for pair in pairs:
        grouped.setdefault(pair.crypto_code, []).append(pair)

    return grouped.items()


def chunked(items, size: int):
    return [items[index:index + size] for index in range(0, len(items), size)]


def format_pair_button_text(pair, selected_mode: bool) -> str:
    if selected_mode:
        return pair.fiat_code

    prefix = "✅" if pair.is_selected else "➕"

    return f"{prefix} {pair.fiat_code}"


def format_crypto_pair_button_text(crypto_code: str, pairs) -> str:
    selected_count = sum(1 for pair in pairs if pair.is_selected)

    if selected_count:
        return f"✅ {crypto_code} · {selected_count}/{len(pairs)}"

    return f"➕ {crypto_code}"


def format_exchange_crypto_button_text(crypto_code: str, pairs) -> str:
    if len(pairs) == 1:
        return crypto_code

    return f"{crypto_code} · {len(pairs)}"


def format_currency_option_label(option, existing_codes: set[str]) -> str:
    prefix = "✅" if option.code in existing_codes else "➕"

    return f"{prefix} {option.code} — {option.name}"


def format_payment_method_option_label(option, existing_codes: set[str]) -> str:
    prefix = "✅" if option.code in existing_codes else "➕"

    return (
        f"{prefix} {option.name} "
        f"({format_payment_method_category(option.category)})"
    )


def format_payment_method_category(category: str | None) -> str:
    labels = {
        PAYMENT_CATEGORY_FOP: "ФОП/ТОВ",
        PAYMENT_CATEGORY_PERSON: "фізособа",
        PAYMENT_CATEGORY_OTHER: "інші",
    }

    return labels.get(category, "інші")


def format_user_payment_method_label(method) -> str:
    prefix = "✅" if method.is_selected else "➕"

    return f"{prefix} {method.name}"


def p2p_filters_kb(settings):
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=f"{BTN_FILTER_ORDER_TIME_PREFIX} "
                    f"{format_max_order_minutes(settings.max_order_minutes)}"
                ),
            ],
            [
                KeyboardButton(
                    text=f"{BTN_FILTER_MIN_TRADES_PREFIX} "
                    f"{format_min_number(settings.min_trades)}"
                ),
            ],
            [
                KeyboardButton(
                    text=f"{BTN_FILTER_DISPLAY_COUNT_PREFIX} "
                    f"{settings.display_order_count} ордерів"
                ),
            ],
            [
                KeyboardButton(
                    text=f"{BTN_FILTER_CANDIDATE_COUNT_PREFIX} "
                    f"{format_candidate_order_count(settings)}"
                ),
            ],
            [
                KeyboardButton(
                    text=f"{BTN_FILTER_DESCRIPTION_CHECK_PREFIX} "
                    f"{format_description_check_mode(settings.description_check_mode)}"
                ),
            ],
            [
                KeyboardButton(
                    text=f"{BTN_FILTER_MIN_RATING_PREFIX} "
                    f"{format_min_percent(settings.min_rating)}"
                ),
                KeyboardButton(
                    text=f"{BTN_FILTER_MIN_COMPLETION_PREFIX} "
                    f"{format_min_percent(settings.min_completion)}"
                ),
            ],
            [
                KeyboardButton(
                    text=f"{BTN_FILTER_FOP_PREFIX} "
                    f"{format_toggle('fop' in settings.payment_categories)}"
                ),
                KeyboardButton(
                    text=f"{BTN_FILTER_PERSON_PREFIX} "
                    f"{format_toggle('person' in settings.payment_categories)}"
                ),
            ],
            [
                KeyboardButton(
                    text=f"{BTN_FILTER_OTHER_PREFIX} "
                    f"{format_toggle('other' in settings.payment_categories)}"
                ),
            ],
            [
                KeyboardButton(
                    text=f"{BTN_FILTER_THIRD_PARTY_PREFIX} "
                    f"{format_allowed_toggle(settings.allow_third_party_payments)}"
                ),
            ],
            [
                KeyboardButton(
                    text=f"{BTN_FILTER_SPLIT_PAYMENTS_PREFIX} "
                    f"{format_allowed_toggle(settings.allow_split_payments)}"
                ),
            ],
            [
                KeyboardButton(
                    text=f"{BTN_FILTER_MONOBANK_JAR_PREFIX} "
                    f"{format_allowed_toggle(settings.allow_monobank_jar_payments)}"
                ),
            ],
            [
                KeyboardButton(text=BTN_RESET_FILTERS),
                KeyboardButton(text=BTN_BACK),
            ],
        ],
        resize_keyboard=True,
    )


def p2p_filters_inline_kb(
    settings,
    *,
    screen_prefix: str = CB_FILTERS_SCREEN_PREFIX,
    reset_callback: str = CB_FILTERS_RESET,
    reset_text: str = BTN_RESET_FILTERS,
):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"⏱ Час: {format_max_order_minutes(settings.max_order_minutes)}",
                    callback_data=f"{screen_prefix}{FILTER_SCREEN_ORDER_TIME}",
                ),
                InlineKeyboardButton(
                    text=f"📊 Угоди: {format_min_number(settings.min_trades)}",
                    callback_data=f"{screen_prefix}{FILTER_SCREEN_MIN_TRADES}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"⭐ Оцінка: {format_min_percent(settings.min_rating)}",
                    callback_data=f"{screen_prefix}{FILTER_SCREEN_MIN_RATING}",
                ),
                InlineKeyboardButton(
                    text=f"✅ Виконання: {format_min_percent(settings.min_completion)}",
                    callback_data=f"{screen_prefix}{FILTER_SCREEN_MIN_COMPLETION}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏦 Методи оплати",
                    callback_data=f"{screen_prefix}{FILTER_SCREEN_PAYMENT_METHODS}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"🧾 Треті особи: {format_allowed_toggle(settings.allow_third_party_payments)}",
                    callback_data=f"{screen_prefix}{FILTER_SCREEN_THIRD_PARTY}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"🧩 Кілька платежів: {format_allowed_toggle(settings.allow_split_payments)}",
                    callback_data=f"{screen_prefix}{FILTER_SCREEN_SPLIT_PAYMENTS}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"🫙 Банка/збір/конверт: {format_allowed_toggle(settings.allow_monobank_jar_payments)}",
                    callback_data=f"{screen_prefix}{FILTER_SCREEN_MONOBANK_JAR}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"🔎 Перевірка опису: {format_description_check_mode(settings.description_check_mode)}",
                    callback_data=f"{screen_prefix}{FILTER_SCREEN_DESCRIPTION_CHECK}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"📋 Виводити: {settings.display_order_count}",
                    callback_data=f"{screen_prefix}{FILTER_SCREEN_DISPLAY_COUNT}",
                ),
                InlineKeyboardButton(
                    text=f"🔍 Кандидати: {format_candidate_order_count(settings)}",
                    callback_data=f"{screen_prefix}{FILTER_SCREEN_CANDIDATE_COUNT}",
                ),
            ],
            [
                InlineKeyboardButton(text=reset_text, callback_data=reset_callback),
            ],
        ],
    )


def p2p_filter_values_inline_kb(
    settings,
    screen: str,
    *,
    set_prefix: str = CB_FILTERS_SET_PREFIX,
    pay_prefix: str = CB_FILTERS_PAY_PREFIX,
    back_callback: str = CB_FILTERS_MENU,
):
    if screen == FILTER_SCREEN_ORDER_TIME:
        return options_inline_kb(
            screen,
            ORDER_MINUTES_OPTIONS,
            settings.max_order_minutes,
            format_max_order_minutes,
            set_prefix=set_prefix,
            back_callback=back_callback,
        )

    if screen == FILTER_SCREEN_MIN_TRADES:
        return options_inline_kb(
            screen,
            MIN_TRADES_OPTIONS,
            settings.min_trades,
            format_min_number,
            set_prefix=set_prefix,
            back_callback=back_callback,
        )

    if screen == FILTER_SCREEN_MIN_RATING:
        return options_inline_kb(
            screen,
            MIN_PERCENT_OPTIONS,
            settings.min_rating,
            format_min_percent,
            set_prefix=set_prefix,
            back_callback=back_callback,
        )

    if screen == FILTER_SCREEN_MIN_COMPLETION:
        return options_inline_kb(
            screen,
            MIN_PERCENT_OPTIONS,
            settings.min_completion,
            format_min_percent,
            set_prefix=set_prefix,
            back_callback=back_callback,
        )

    if screen == FILTER_SCREEN_DISPLAY_COUNT:
        return options_inline_kb(
            screen,
            DISPLAY_ORDER_COUNT_OPTIONS,
            settings.display_order_count,
            lambda value: f"{value} ордерів",
            set_prefix=set_prefix,
            back_callback=back_callback,
        )

    if screen == FILTER_SCREEN_CANDIDATE_COUNT:
        return options_inline_kb(
            screen,
            CANDIDATE_ORDER_COUNT_OPTIONS,
            settings.candidate_order_count,
            lambda value: f"{value} кандидатів",
            set_prefix=set_prefix,
            back_callback=back_callback,
        )

    if screen == FILTER_SCREEN_DESCRIPTION_CHECK:
        return options_inline_kb(
            screen,
            DESCRIPTION_CHECK_MODE_OPTIONS,
            settings.description_check_mode,
            format_description_check_mode,
            set_prefix=set_prefix,
            back_callback=back_callback,
        )

    if screen == FILTER_SCREEN_THIRD_PARTY:
        return bool_inline_kb(
            screen,
            settings.allow_third_party_payments,
            set_prefix=set_prefix,
            back_callback=back_callback,
        )

    if screen == FILTER_SCREEN_SPLIT_PAYMENTS:
        return bool_inline_kb(
            screen,
            settings.allow_split_payments,
            set_prefix=set_prefix,
            back_callback=back_callback,
        )

    if screen == FILTER_SCREEN_MONOBANK_JAR:
        return bool_inline_kb(
            screen,
            settings.allow_monobank_jar_payments,
            set_prefix=set_prefix,
            back_callback=back_callback,
        )

    if screen == FILTER_SCREEN_PAYMENT_METHODS:
        return payment_methods_inline_kb(
            settings,
            pay_prefix=pay_prefix,
            back_callback=back_callback,
        )

    return p2p_filters_inline_kb(settings)


def options_inline_kb(
    screen: str,
    options: list,
    current,
    formatter,
    *,
    set_prefix: str = CB_FILTERS_SET_PREFIX,
    back_callback: str = CB_FILTERS_MENU,
):
    rows = []

    for option in options:
        label = formatter(option)
        rows.append(
            [
                InlineKeyboardButton(
                    text=selected_label(option == current, label),
                    callback_data=f"{set_prefix}{screen}:{serialize_callback_value(option)}",
                ),
            ]
        )

    rows.append(back_to_filters_row(back_callback))

    return InlineKeyboardMarkup(inline_keyboard=rows)


def bool_inline_kb(
    screen: str,
    current: bool,
    *,
    set_prefix: str = CB_FILTERS_SET_PREFIX,
    back_callback: str = CB_FILTERS_MENU,
):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=selected_label(current, "Дозволено"),
                    callback_data=f"{set_prefix}{screen}:1",
                ),
                InlineKeyboardButton(
                    text=selected_label(not current, "Заборонено"),
                    callback_data=f"{set_prefix}{screen}:0",
                ),
            ],
            back_to_filters_row(back_callback),
        ],
    )


def payment_methods_inline_kb(
    settings,
    *,
    pay_prefix: str = CB_FILTERS_PAY_PREFIX,
    back_callback: str = CB_FILTERS_MENU,
):
    categories = settings.payment_categories

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=selected_label(PAYMENT_CATEGORY_FOP in categories, "ФОП/ТОВ/IBAN"),
                    callback_data=f"{pay_prefix}{PAYMENT_CATEGORY_FOP}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=selected_label(PAYMENT_CATEGORY_PERSON in categories, "Фізособа/карта"),
                    callback_data=f"{pay_prefix}{PAYMENT_CATEGORY_PERSON}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=selected_label(PAYMENT_CATEGORY_OTHER in categories, "Інші методи"),
                    callback_data=f"{pay_prefix}{PAYMENT_CATEGORY_OTHER}",
                ),
            ],
            back_to_filters_row(back_callback),
        ],
    )


def back_to_filters_row(callback_data: str = CB_FILTERS_MENU):
    return [
        InlineKeyboardButton(text="⬅️ До фільтрів", callback_data=callback_data),
    ]


def selected_label(is_selected: bool, label: str) -> str:
    return f"✅ {label}" if is_selected else label


def toggle_label(label: str, is_enabled: bool) -> str:
    return f"✅ {label}" if is_enabled else f"🚫 {label}"


def serialize_callback_value(value) -> str:
    return "none" if value is None else str(value)


def main_menu_kb():
    return root_menu_kb()


def format_max_order_minutes(value: int | None) -> str:
    return "будь-який" if value is None else f"≤ {value} хв"


def format_order_amount_bound(value: float | None) -> str:
    if value is None:
        return "без обмеження"

    return f"{value:,.2f}".replace(",", " ").rstrip("0").rstrip(".")


def format_min_number(value: int | None) -> str:
    return "будь-яка к-сть" if value is None else f"≥ {value}"


def format_min_percent(value: float | None) -> str:
    return "будь-який" if value is None else f"≥ {value:g}%"


def format_toggle(value: bool) -> str:
    return "✅" if value else "❌"


def format_allowed_toggle(value: bool) -> str:
    return "дозволено" if value else "заборонено"


def format_description_check_mode(value: str) -> str:
    if value == DESCRIPTION_CHECK_GPT:
        return "GPT"

    if value == DESCRIPTION_CHECK_REGEX_GPT:
        return "Regex + GPT"

    return "Regex"


def format_candidate_order_count(settings) -> str:
    return f"{settings.candidate_order_count}"
