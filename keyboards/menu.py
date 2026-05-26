import os

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

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
)


BINANCE_ICON_CUSTOM_EMOJI_ID = os.getenv("BINANCE_ICON_CUSTOM_EMOJI_ID")
OKX_ICON_CUSTOM_EMOJI_ID = os.getenv("OKX_ICON_CUSTOM_EMOJI_ID")

BTN_BINANCE = "Binance" if BINANCE_ICON_CUSTOM_EMOJI_ID else "🟡 Binance"
BTN_OKX = "OKX" if OKX_ICON_CUSTOM_EMOJI_ID else "⚫ OKX"
BTN_P2P = "💱 P2P"
BTN_CABINET = "👤 Особистий кабінет"
BTN_ADMIN_PANEL = "🛠 Адмін панель"
BTN_ADMIN_CURRENCIES = "🪙 Валюти"
BTN_ADD_FIAT_CURRENCY = "➕ Додати фіат"
BTN_ADD_CRYPTO_CURRENCY = "➕ Додати крипту"
BTN_LIST_CURRENCIES = "📋 Список валют"
BTN_MY_INFO = "ℹ️ Інфо про себе"
BTN_P2P_FILTERS = "⚙️ Фільтри P2P"
BTN_UAH_TO_USDT = "₴ UAH → ₮ USDT"
BTN_USDT_TO_UAH = "₮ USDT → ₴ UAH"
BTN_BACK = "⬅️ Назад"
BTN_RESET_FILTERS = "♻️ Скинути фільтри"

BTN_FILTER_ORDER_TIME_PREFIX = "⏱ Час:"
BTN_FILTER_MIN_TRADES_PREFIX = "📊 Угоди:"
BTN_FILTER_DISPLAY_COUNT_PREFIX = "📋 Виводити:"
BTN_FILTER_CANDIDATE_COUNT_PREFIX = "🔍 Кандидати:"
BTN_FILTER_DESCRIPTION_CHECK_PREFIX = "🔎 Перевірка:"
BTN_FILTER_MIN_RATING_PREFIX = "⭐ Оцінка:"
BTN_FILTER_MIN_COMPLETION_PREFIX = "✅ Виконання:"
BTN_FILTER_FOP_PREFIX = "🏦 ФОП/IBAN:"
BTN_FILTER_PERSON_PREFIX = "👤 Фізособа/карта:"
BTN_FILTER_OTHER_PREFIX = "🌐 Інші методи:"
BTN_FILTER_THIRD_PARTY_PREFIX = "🧾 Треті особи:"
BTN_FILTER_SPLIT_PAYMENTS_PREFIX = "🧩 Кілька платежів:"

CB_FILTERS_MENU = "p2pf:menu"
CB_FILTERS_RESET = "p2pf:reset"
CB_FILTERS_SCREEN_PREFIX = "p2pf:screen:"
CB_FILTERS_SET_PREFIX = "p2pf:set:"
CB_FILTERS_PAY_PREFIX = "p2pf:pay:"
CB_ADMIN_CURRENCIES_MENU = "admcur:menu"
CB_ADMIN_CURRENCY_ADD_PREFIX = "admcur:add:"

FILTER_SCREEN_ORDER_TIME = "time"
FILTER_SCREEN_MIN_TRADES = "trades"
FILTER_SCREEN_MIN_RATING = "rating"
FILTER_SCREEN_MIN_COMPLETION = "completion"
FILTER_SCREEN_PAYMENT_METHODS = "pay_methods"
FILTER_SCREEN_THIRD_PARTY = "third_party"
FILTER_SCREEN_SPLIT_PAYMENTS = "split"
FILTER_SCREEN_DESCRIPTION_CHECK = "desc"
FILTER_SCREEN_DISPLAY_COUNT = "display"
FILTER_SCREEN_CANDIDATE_COUNT = "candidates"


def keyboard_button(text: str, icon_custom_emoji_id: str | None = None):
    kwargs = {"text": text}

    if icon_custom_emoji_id:
        kwargs["icon_custom_emoji_id"] = icon_custom_emoji_id

    return KeyboardButton(**kwargs)


def root_menu_kb(can_view_admin: bool = False):
    keyboard = [
        [
            KeyboardButton(text=BTN_P2P),
            KeyboardButton(text=BTN_CABINET),
        ],
    ]

    if can_view_admin:
        keyboard.append([KeyboardButton(text=BTN_ADMIN_PANEL)])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def exchanges_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                keyboard_button(BTN_BINANCE, BINANCE_ICON_CUSTOM_EMOJI_ID),
                keyboard_button(BTN_OKX, OKX_ICON_CUSTOM_EMOJI_ID),
            ],
            [
                KeyboardButton(text=BTN_BACK),
            ],
        ],
        resize_keyboard=True,
    )


def cabinet_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=BTN_MY_INFO),
                KeyboardButton(text=BTN_P2P_FILTERS),
            ],
            [
                KeyboardButton(text=BTN_BACK),
            ],
        ],
        resize_keyboard=True,
    )


def admin_menu_kb(can_manage_currencies: bool = False):
    keyboard = []

    if can_manage_currencies:
        keyboard.append([KeyboardButton(text=BTN_ADMIN_CURRENCIES)])

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


def format_currency_option_label(option, existing_codes: set[str]) -> str:
    prefix = "✅" if option.code in existing_codes else "➕"

    return f"{prefix} {option.code} — {option.name}"


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
                KeyboardButton(text=BTN_RESET_FILTERS),
                KeyboardButton(text=BTN_BACK),
            ],
        ],
        resize_keyboard=True,
    )


def p2p_filters_inline_kb(settings):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"⏱ Час: {format_max_order_minutes(settings.max_order_minutes)}",
                    callback_data=f"{CB_FILTERS_SCREEN_PREFIX}{FILTER_SCREEN_ORDER_TIME}",
                ),
                InlineKeyboardButton(
                    text=f"📊 Угоди: {format_min_number(settings.min_trades)}",
                    callback_data=f"{CB_FILTERS_SCREEN_PREFIX}{FILTER_SCREEN_MIN_TRADES}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"⭐ Оцінка: {format_min_percent(settings.min_rating)}",
                    callback_data=f"{CB_FILTERS_SCREEN_PREFIX}{FILTER_SCREEN_MIN_RATING}",
                ),
                InlineKeyboardButton(
                    text=f"✅ Виконання: {format_min_percent(settings.min_completion)}",
                    callback_data=f"{CB_FILTERS_SCREEN_PREFIX}{FILTER_SCREEN_MIN_COMPLETION}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏦 Методи оплати",
                    callback_data=f"{CB_FILTERS_SCREEN_PREFIX}{FILTER_SCREEN_PAYMENT_METHODS}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"🧾 Треті особи: {format_allowed_toggle(settings.allow_third_party_payments)}",
                    callback_data=f"{CB_FILTERS_SCREEN_PREFIX}{FILTER_SCREEN_THIRD_PARTY}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"🧩 Кілька платежів: {format_allowed_toggle(settings.allow_split_payments)}",
                    callback_data=f"{CB_FILTERS_SCREEN_PREFIX}{FILTER_SCREEN_SPLIT_PAYMENTS}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"🔎 Перевірка опису: {format_description_check_mode(settings.description_check_mode)}",
                    callback_data=f"{CB_FILTERS_SCREEN_PREFIX}{FILTER_SCREEN_DESCRIPTION_CHECK}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"📋 Виводити: {settings.display_order_count}",
                    callback_data=f"{CB_FILTERS_SCREEN_PREFIX}{FILTER_SCREEN_DISPLAY_COUNT}",
                ),
                InlineKeyboardButton(
                    text=f"🔍 Кандидати: {format_candidate_order_count(settings)}",
                    callback_data=f"{CB_FILTERS_SCREEN_PREFIX}{FILTER_SCREEN_CANDIDATE_COUNT}",
                ),
            ],
            [
                InlineKeyboardButton(text=BTN_RESET_FILTERS, callback_data=CB_FILTERS_RESET),
            ],
        ],
    )


def p2p_filter_values_inline_kb(settings, screen: str):
    if screen == FILTER_SCREEN_ORDER_TIME:
        return options_inline_kb(
            screen,
            ORDER_MINUTES_OPTIONS,
            settings.max_order_minutes,
            format_max_order_minutes,
        )

    if screen == FILTER_SCREEN_MIN_TRADES:
        return options_inline_kb(
            screen,
            MIN_TRADES_OPTIONS,
            settings.min_trades,
            format_min_number,
        )

    if screen == FILTER_SCREEN_MIN_RATING:
        return options_inline_kb(
            screen,
            MIN_PERCENT_OPTIONS,
            settings.min_rating,
            format_min_percent,
        )

    if screen == FILTER_SCREEN_MIN_COMPLETION:
        return options_inline_kb(
            screen,
            MIN_PERCENT_OPTIONS,
            settings.min_completion,
            format_min_percent,
        )

    if screen == FILTER_SCREEN_DISPLAY_COUNT:
        return options_inline_kb(
            screen,
            DISPLAY_ORDER_COUNT_OPTIONS,
            settings.display_order_count,
            lambda value: f"{value} ордерів",
        )

    if screen == FILTER_SCREEN_CANDIDATE_COUNT:
        return options_inline_kb(
            screen,
            CANDIDATE_ORDER_COUNT_OPTIONS,
            settings.candidate_order_count,
            lambda value: f"{value} кандидатів",
        )

    if screen == FILTER_SCREEN_DESCRIPTION_CHECK:
        return options_inline_kb(
            screen,
            DESCRIPTION_CHECK_MODE_OPTIONS,
            settings.description_check_mode,
            format_description_check_mode,
        )

    if screen == FILTER_SCREEN_THIRD_PARTY:
        return bool_inline_kb(screen, settings.allow_third_party_payments)

    if screen == FILTER_SCREEN_SPLIT_PAYMENTS:
        return bool_inline_kb(screen, settings.allow_split_payments)

    if screen == FILTER_SCREEN_PAYMENT_METHODS:
        return payment_methods_inline_kb(settings)

    return p2p_filters_inline_kb(settings)


def options_inline_kb(screen: str, options: list, current, formatter):
    rows = []

    for option in options:
        label = formatter(option)
        rows.append(
            [
                InlineKeyboardButton(
                    text=selected_label(option == current, label),
                    callback_data=f"{CB_FILTERS_SET_PREFIX}{screen}:{serialize_callback_value(option)}",
                ),
            ]
        )

    rows.append(back_to_filters_row())

    return InlineKeyboardMarkup(inline_keyboard=rows)


def bool_inline_kb(screen: str, current: bool):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=selected_label(current, "Дозволено"),
                    callback_data=f"{CB_FILTERS_SET_PREFIX}{screen}:1",
                ),
                InlineKeyboardButton(
                    text=selected_label(not current, "Заборонено"),
                    callback_data=f"{CB_FILTERS_SET_PREFIX}{screen}:0",
                ),
            ],
            back_to_filters_row(),
        ],
    )


def payment_methods_inline_kb(settings):
    categories = settings.payment_categories

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=selected_label(PAYMENT_CATEGORY_FOP in categories, "ФОП/IBAN"),
                    callback_data=f"{CB_FILTERS_PAY_PREFIX}{PAYMENT_CATEGORY_FOP}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=selected_label(PAYMENT_CATEGORY_PERSON in categories, "Фізособа/карта"),
                    callback_data=f"{CB_FILTERS_PAY_PREFIX}{PAYMENT_CATEGORY_PERSON}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=selected_label(PAYMENT_CATEGORY_OTHER in categories, "Інші методи"),
                    callback_data=f"{CB_FILTERS_PAY_PREFIX}{PAYMENT_CATEGORY_OTHER}",
                ),
            ],
            back_to_filters_row(),
        ],
    )


def back_to_filters_row():
    return [
        InlineKeyboardButton(text="⬅️ До фільтрів", callback_data=CB_FILTERS_MENU),
    ]


def selected_label(is_selected: bool, label: str) -> str:
    return f"✅ {label}" if is_selected else label


def serialize_callback_value(value) -> str:
    return "none" if value is None else str(value)


def p2p_directions_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=BTN_UAH_TO_USDT),
                KeyboardButton(text=BTN_USDT_TO_UAH),
            ],
            [
                KeyboardButton(text=BTN_BACK),
            ],
        ],
        resize_keyboard=True,
    )


def main_menu_kb():
    return root_menu_kb()


def format_max_order_minutes(value: int | None) -> str:
    return "будь-який" if value is None else f"≤ {value} хв"


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
