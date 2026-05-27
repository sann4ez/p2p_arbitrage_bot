import re
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from db.dto import (
    DEFAULT_CANDIDATE_ORDER_COUNT,
    DEFAULT_DISPLAY_ORDER_COUNT,
    CANDIDATE_ORDER_COUNT_OPTIONS,
    DESCRIPTION_CHECK_MODE_OPTIONS,
    DESCRIPTION_CHECK_GPT,
    DESCRIPTION_CHECK_REGEX,
    DESCRIPTION_CHECK_REGEX_GPT,
    DISPLAY_ORDER_COUNT_OPTIONS,
    MIN_PERCENT_OPTIONS,
    MIN_TRADES_OPTIONS,
    ORDER_MINUTES_OPTIONS,
    PAYMENT_CATEGORIES,
    PAYMENT_CATEGORY_FOP,
    PAYMENT_CATEGORY_OTHER,
    PAYMENT_CATEGORY_PERSON,
    P2PFilterSettings,
)
from db.models import UserSettings
from repositories.user_repository import UserRepository
from services.okx_order_payload import get_okx_order_description_values

MAX_FETCH_ORDER_COUNT = 200

FOP_PAYMENT_KEYWORDS = (
    "iban",
    "fop",
    "фоп",
    "entrepreneur",
    "business",
    "рахунок",
)

BUSINESS_PAYMENT_TERM_RE = (
    r"(?:фоп|fop|iban|тов|тзов|ооо|llc|юридич\w*|юр\.?\s*особ\w*|"
    r"legal\s+entity|company\s+account|business\s+account)"
)

BUSINESS_PAYMENT_PATTERNS = (
    re.compile(rf"\b{BUSINESS_PAYMENT_TERM_RE}\b", re.IGNORECASE),
)

FOP_ONLY_PAYMENT_PATTERNS = (
    re.compile(rf"\b(?:тільки|лише|только)\b.{{0,60}}\b{BUSINESS_PAYMENT_TERM_RE}\b", re.IGNORECASE),
    re.compile(rf"\b{BUSINESS_PAYMENT_TERM_RE}\b.{{0,60}}\b(?:тільки|лише|только)\b", re.IGNORECASE),
    re.compile(rf"\b(?:оплат\w*|виплат\w*|выплат\w*|переказ\w*|перевод\w*)\b.{{0,60}}\b{BUSINESS_PAYMENT_TERM_RE}\b", re.IGNORECASE),
    re.compile(rf"\b(?:на|по)\s+{BUSINESS_PAYMENT_TERM_RE}\b", re.IGNORECASE),
    re.compile(r"\b(?:на|на\s+банківський)\s+рахунок\b", re.IGNORECASE),
)

PERSON_PAYMENT_DENY_PATTERNS = (
    re.compile(r"\b(?:на|на\s+банківські)?\s*(?:карти|карты|картки|карточки)\b.{0,60}\b(?:не|нет|немає|нема)\b", re.IGNORECASE),
    re.compile(r"\b(?:не|нет|немає|нема)\b.{0,60}\b(?:на|на\s+банківські)?\s*(?:карти|карты|картки|карточки)\b", re.IGNORECASE),
    re.compile(r"\b(?:карти|карты|картки|карточки)\b.{0,60}\b(?:не\s+виплачу|не\s+выплачи|не\s+відправ|не\s+отправ)\w*", re.IGNORECASE),
)

PERSON_PAYMENT_KEYWORDS = (
    "monobank",
    "privat",
    "privatbank",
    "pumb",
    "pumbbank",
    "a-bank",
    "abank",
    "raiff",
    "sense",
    "izibank",
    "otp",
    "kredo",
    "tascom",
    "oschad",
    "ukrsib",
    "accord",
    "unex",
    "idea",
    "credit dnepro",
    "bank credit dnepro",
    "bank vlasnyi rakhunok",
)

THIRD_PARTY_PAYMENT_KEYWORDS = (
    "від третіх осіб",
    "від третіх лиць",
    "від 3-х осіб",
    "від 3х осіб",
    "від 3 осіб",
    "от третьих лиц",
    "от 3-х лиц",
    "от 3х лиц",
    "от 3 лиц",
    "від іншої особи",
    "від інших осіб",
    "от другого лица",
    "от других лиц",
    "від різних осіб",
    "от разных лиц",
    "від довірених осіб",
    "от доверенных лиц",
    "довірених осіб",
    "доверенных лиц",
    "third party",
    "third-party",
    "3rd party",
    "from another person",
    "from different person",
    "from different name",
    "different persons",
    "different names",
    "третье лицо",
    "третьи лица",
    "третє лице",
    "треті особи",
    "третім особам",
)

THIRD_PARTY_TERM_RE = (
    r"(?:трет\w*\s+(?:ос(?:о|і)б\w*|лиц\w*)|"
    r"3\s*[-\s]*(?:х|и|іх|им|м)?\s*(?:ос(?:о|і)б\w*|лиц\w*)|"
    r"3rd\s+part\w*|third[-\s]+part\w*)"
)

THIRD_PARTY_PAYMENT_PATTERNS = (
    re.compile(
        rf"(?:на|для|відправ\w*|отправ\w*|перевод\w*|переказ\w*|"
        rf"оплат\w*|прийма\w*|принима\w*)\W{{0,60}}{THIRD_PARTY_TERM_RE}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"{THIRD_PARTY_TERM_RE}\W{{0,60}}"
        rf"(?:можн\w*|прийма\w*|принима\w*|відправ\w*|отправ\w*|"
        rf"перевод\w*|переказ\w*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:карт[ауиі]|карта|картка)\s+"
        r"(?:чоловік\w*|чоловіка|муж\w*|мужа|жінк\w*|жены|дружин\w*|"
        r"брат\w*|сестр\w*|мам\w*|матер\w*|пап\w*|батьк\w*|отц\w*|"
        r"родич\w*|родственник\w*)",
        re.IGNORECASE,
    ),
)

THIRD_PARTY_DENY_KEYWORDS = (
    "не приймаю від трет",
    "не приймаю від 3",
    "не приймаю оплату від трет",
    "не приймаю оплату від 3",
    "не приймаються від трет",
    "не приймаються від 3",
    "не принимаю от трет",
    "не принимаю от 3",
    "не принимаю оплату от трет",
    "не принимаю оплату от 3",
    "не принимаются от трет",
    "не принимаются от 3",
    "не допускаю оплату від трет",
    "не допускается оплата от трет",
    "заборонена оплата від трет",
    "запрещена оплата от трет",
    "тільки від свого імені",
    "только от своего имени",
    "тільки зі своєї карти",
    "только со своей карты",
    "only from your own",
    "only own card",
    "no third party",
    "no 3rd party",
    "do not accept third",
    "don't accept third",
    "not accept third",
    "third parties are not accepted",
)

THIRD_PARTY_DENY_PATTERNS = (
    re.compile(
        rf"(?:не|ні|нет|немає|нема|заборон\w*|запрещ\w*|"
        rf"не\s+перевод\w*|не\s+переказ\w*|не\s+відправ\w*|не\s+отправ\w*)"
        rf"\W{{0,80}}{THIRD_PARTY_TERM_RE}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"{THIRD_PARTY_TERM_RE}\W{{0,80}}"
        rf"(?:не|ні|нет|немає|нема|заборон\w*|запрещ\w*|"
        rf"не\s+перевод\w*|не\s+переказ\w*|не\s+відправ\w*|не\s+отправ\w*)",
        re.IGNORECASE,
    ),
)

SPLIT_PAYMENT_KEYWORDS = (
    "кількома платеж",
    "декількома платеж",
    "кількох платеж",
    "декількох платеж",
    "кілька платеж",
    "декілька платеж",
    "несколькими платеж",
    "нескольких платеж",
    "несколько платеж",
    "кількома переказ",
    "декількома переказ",
    "кількох переказ",
    "декількох переказ",
    "несколькими перевод",
    "нескольких перевод",
    "несколько перевод",
    "кількома транзакц",
    "декількома транзакц",
    "кількох транзакц",
    "декількох транзакц",
    "несколькими транзакц",
    "нескольких транзакц",
    "несколько транзакц",
    "з декількох платеж",
    "з кількох платеж",
    "из нескольких платеж",
    "з декількох переказ",
    "з кількох переказ",
    "из нескольких перевод",
    "частинами",
    "частями",
    "по частинах",
    "по частям",
    "розбити платіж",
    "розбивати платіж",
    "разбить платеж",
    "разбивать платеж",
    "multiple payments",
    "several payments",
    "split payment",
    "split into",
    "installments",
)

SPLIT_PAYMENT_DENY_KEYWORDS = (
    "не кількома платеж",
    "не декількома платеж",
    "не кількох платеж",
    "не декількох платеж",
    "не несколькими платеж",
    "не нескольких платеж",
    "не приймаю кількома платеж",
    "не приймаю декількома платеж",
    "не принимаю несколькими платеж",
    "не приймаю частинами",
    "не принимаю частями",
    "не дробити",
    "не дробить",
    "не ділити",
    "не делить",
    "не розбивати",
    "не разбивать",
    "не розбити",
    "не разбить",
    "do not split",
    "don't split",
    "not split",
    "одним платеж",
    "одним переказ",
    "одним перевод",
    "одной транзакц",
    "single payment",
    "one payment",
)

SPLIT_PAYMENT_PATTERNS = (
    re.compile(
        r"(?:плат[еёі]ж\w*|поступлен\w*|зачислен\w*)\D{0,80}"
        r"(?:от|від)\s*\d+\+?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:от|від)\s*\d+\+?\D{0,40}"
        r"(?:плат[еёі]ж\w*|поступлен\w*|зачислен\w*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b\d+\+\s*(?:плат[еёі]ж\w*|поступлен\w*|зачислен\w*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:плат[еі]ж\w*|переказ\w*|перевод\w*|транзакц\w*|"
        r"част\w*|сум\w*)\s+по\s+\d+(?:[.,]\d+)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bпо\s+\d+(?:[.,]\d+)?\s*"
        r"(?:грн|грив\w*|uah|₴)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:декільк\w*|кільк\w*|нескольк\w*|several|multiple)\s+"
        r"(?:плат[еі]ж\w*|переказ\w*|перевод\w*|транзакц\w*|payments?|transfers?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:2|3|4|5|6|7|8|9|10)\s+"
        r"(?:плат[еі]ж\w*|переказ\w*|перевод\w*|транзакц\w*|payments?|transfers?)\b",
        re.IGNORECASE,
    ),
)

DESCRIPTION_PAYMENT_TIME_PATTERNS = (
    re.compile(
        r"(?:оплат\w*|поступлен\w*|зачислен\w*|закрыт\w*|закрит\w*|"
        r"ожидан\w*|очікуван\w*|может\s+занять|може\s+зайняти|срок\s+оплат\w*|"
        r"час\s+виконан\w*|термін\s+виконан\w*|время\s+исполнен\w*|срок\s+исполнен\w*)"
        r"\D{0,80}(?:от|від)?\s*(\d+)\s*(?:до|-)\s*(\d+)\s*"
        r"(час\w*|годин\w*|год\w*|минут\w*|мин\w*|хвилин\w*|хв\w*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:оплат\w*|поступлен\w*|зачислен\w*|закрыт\w*|закрит\w*|"
        r"ожидан\w*|очікуван\w*|срок\s+оплат\w*|"
        r"час\s+виконан\w*|термін\s+виконан\w*|время\s+исполнен\w*|срок\s+исполнен\w*)"
        r"\D{0,80}(?:до|up\s+to)\s*(\d+)\s*"
        r"(час\w*|годин\w*|год\w*|минут\w*|мин\w*|хвилин\w*|хв\w*)",
        re.IGNORECASE,
    ),
)


async def get_filters(session: AsyncSession, telegram_id: int) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    return settings_from_model(user_settings)


async def reset_filters(session: AsyncSession, telegram_id: int) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    apply_settings_to_model(user_settings, P2PFilterSettings())
    await session.commit()

    return settings_from_model(user_settings)


async def cycle_order_minutes(session: AsyncSession, telegram_id: int) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    user_settings.max_order_minutes = cycle_value(
        ORDER_MINUTES_OPTIONS,
        user_settings.max_order_minutes,
    )
    await session.commit()

    return settings_from_model(user_settings)


async def cycle_min_trades(session: AsyncSession, telegram_id: int) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    user_settings.min_merchant_orders = cycle_value(
        MIN_TRADES_OPTIONS,
        user_settings.min_merchant_orders,
    )
    await session.commit()

    return settings_from_model(user_settings)


async def cycle_min_rating(session: AsyncSession, telegram_id: int) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    current = float(user_settings.min_merchant_rating) if user_settings.min_merchant_rating else None
    next_value = cycle_value(MIN_PERCENT_OPTIONS, current)
    user_settings.min_merchant_rating = decimal_or_none(next_value)
    await session.commit()

    return settings_from_model(user_settings)


async def cycle_min_completion(session: AsyncSession, telegram_id: int) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    current = (
        float(user_settings.min_merchant_completion_rate)
        if user_settings.min_merchant_completion_rate
        else None
    )
    next_value = cycle_value(MIN_PERCENT_OPTIONS, current)
    user_settings.min_merchant_completion_rate = decimal_or_none(next_value)
    await session.commit()

    return settings_from_model(user_settings)


async def cycle_display_order_count(
    session: AsyncSession,
    telegram_id: int,
) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    current = normalize_display_order_count(user_settings.display_order_count)
    user_settings.display_order_count = cycle_value(DISPLAY_ORDER_COUNT_OPTIONS, current)
    await session.commit()

    return settings_from_model(user_settings)


async def cycle_candidate_order_count(
    session: AsyncSession,
    telegram_id: int,
) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    current = normalize_candidate_order_count(user_settings.candidate_order_count)
    user_settings.candidate_order_count = cycle_value(
        CANDIDATE_ORDER_COUNT_OPTIONS,
        current,
    )
    await session.commit()

    return settings_from_model(user_settings)


async def cycle_description_check_mode(
    session: AsyncSession,
    telegram_id: int,
) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    current = normalize_description_check_mode(user_settings.description_check_mode)
    user_settings.description_check_mode = cycle_value(
        DESCRIPTION_CHECK_MODE_OPTIONS,
        current,
    )
    await session.commit()

    return settings_from_model(user_settings)


async def set_order_minutes(
    session: AsyncSession,
    telegram_id: int,
    value: int | None,
) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    user_settings.max_order_minutes = value if value in ORDER_MINUTES_OPTIONS else None
    await session.commit()

    return settings_from_model(user_settings)


async def set_min_trades(
    session: AsyncSession,
    telegram_id: int,
    value: int | None,
) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    user_settings.min_merchant_orders = value if value in MIN_TRADES_OPTIONS else None
    await session.commit()

    return settings_from_model(user_settings)


async def set_min_rating(
    session: AsyncSession,
    telegram_id: int,
    value: float | None,
) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    value = value if value in MIN_PERCENT_OPTIONS else None
    user_settings.min_merchant_rating = decimal_or_none(value)
    await session.commit()

    return settings_from_model(user_settings)


async def set_min_completion(
    session: AsyncSession,
    telegram_id: int,
    value: float | None,
) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    value = value if value in MIN_PERCENT_OPTIONS else None
    user_settings.min_merchant_completion_rate = decimal_or_none(value)
    await session.commit()

    return settings_from_model(user_settings)


async def set_display_order_count(
    session: AsyncSession,
    telegram_id: int,
    value: int,
) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    user_settings.display_order_count = normalize_display_order_count(value)
    await session.commit()

    return settings_from_model(user_settings)


async def set_candidate_order_count(
    session: AsyncSession,
    telegram_id: int,
    value: int,
) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    user_settings.candidate_order_count = normalize_candidate_order_count(value)
    await session.commit()

    return settings_from_model(user_settings)


async def set_description_check_mode(
    session: AsyncSession,
    telegram_id: int,
    value: str,
) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    user_settings.description_check_mode = normalize_description_check_mode(value)
    await session.commit()

    return settings_from_model(user_settings)


async def set_third_party_payments(
    session: AsyncSession,
    telegram_id: int,
    is_allowed: bool,
) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    user_settings.allow_third_party_payments = is_allowed
    await session.commit()

    return settings_from_model(user_settings)


async def set_split_payments(
    session: AsyncSession,
    telegram_id: int,
    is_allowed: bool,
) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    user_settings.allow_split_payments = is_allowed
    await session.commit()

    return settings_from_model(user_settings)


async def toggle_payment_category(
    session: AsyncSession,
    telegram_id: int,
    category: str,
) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    settings = settings_from_model(user_settings)

    if category not in PAYMENT_CATEGORIES:
        return settings

    if category in settings.payment_categories and len(settings.payment_categories) > 1:
        settings.payment_categories.remove(category)
    else:
        settings.payment_categories.add(category)

    apply_payment_categories_to_model(user_settings, settings.payment_categories)
    await session.commit()

    return settings_from_model(user_settings)


async def toggle_third_party_payments(
    session: AsyncSession,
    telegram_id: int,
) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    user_settings.allow_third_party_payments = not user_settings.allow_third_party_payments
    await session.commit()

    return settings_from_model(user_settings)


async def toggle_split_payments(
    session: AsyncSession,
    telegram_id: int,
) -> P2PFilterSettings:
    user_settings = await get_user_settings(session, telegram_id)

    if not user_settings:
        return P2PFilterSettings()

    user_settings.allow_split_payments = not user_settings.allow_split_payments
    await session.commit()

    return settings_from_model(user_settings)


async def get_user_settings(session: AsyncSession, telegram_id: int) -> UserSettings | None:
    repo = UserRepository(session)
    user = await repo.get_by_telegram_id(telegram_id)

    if not user:
        return None

    return await repo.ensure_settings(user.id)


def settings_from_model(user_settings: UserSettings) -> P2PFilterSettings:
    return P2PFilterSettings(
        max_order_minutes=user_settings.max_order_minutes,
        min_trades=user_settings.min_merchant_orders,
        min_rating=to_float(user_settings.min_merchant_rating),
        min_completion=to_float(user_settings.min_merchant_completion_rate),
        payment_categories=payment_categories_from_model(user_settings),
        allow_third_party_payments=user_settings.allow_third_party_payments,
        allow_split_payments=user_settings.allow_split_payments,
        display_order_count=normalize_display_order_count(user_settings.display_order_count),
        candidate_order_count=normalize_candidate_order_count(
            user_settings.candidate_order_count
        ),
        description_check_mode=normalize_description_check_mode(
            user_settings.description_check_mode
        ),
    )


def apply_settings_to_model(
    user_settings: UserSettings,
    settings: P2PFilterSettings,
):
    user_settings.max_order_minutes = settings.max_order_minutes
    user_settings.min_merchant_orders = settings.min_trades
    user_settings.min_merchant_rating = decimal_or_none(settings.min_rating)
    user_settings.min_merchant_completion_rate = decimal_or_none(settings.min_completion)
    user_settings.allow_third_party_payments = settings.allow_third_party_payments
    user_settings.allow_split_payments = settings.allow_split_payments
    user_settings.display_order_count = normalize_display_order_count(
        settings.display_order_count
    )
    user_settings.candidate_order_count = normalize_candidate_order_count(
        settings.candidate_order_count
    )
    user_settings.description_check_mode = normalize_description_check_mode(
        settings.description_check_mode
    )
    apply_payment_categories_to_model(user_settings, settings.payment_categories)


def payment_categories_from_model(user_settings: UserSettings) -> set[str]:
    categories = set()

    if user_settings.allow_fop:
        categories.add(PAYMENT_CATEGORY_FOP)

    if user_settings.allow_person:
        categories.add(PAYMENT_CATEGORY_PERSON)

    if user_settings.allow_other_payment_methods:
        categories.add(PAYMENT_CATEGORY_OTHER)

    return categories or set(PAYMENT_CATEGORIES)


def apply_payment_categories_to_model(
    user_settings: UserSettings,
    categories: set[str],
):
    user_settings.allow_fop = PAYMENT_CATEGORY_FOP in categories
    user_settings.allow_person = PAYMENT_CATEGORY_PERSON in categories
    user_settings.allow_other_payment_methods = PAYMENT_CATEGORY_OTHER in categories


def to_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def decimal_or_none(value: float | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def cycle_value(options: list, current):
    current_index = options.index(current) if current in options else 0
    next_index = (current_index + 1) % len(options)

    return options[next_index]


def normalize_display_order_count(value) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return DEFAULT_DISPLAY_ORDER_COUNT

    if count in DISPLAY_ORDER_COUNT_OPTIONS:
        return count

    return min(
        DISPLAY_ORDER_COUNT_OPTIONS,
        key=lambda option: abs(option - count),
    )


def get_fetch_order_count(settings: P2PFilterSettings) -> int:
    return min(
        MAX_FETCH_ORDER_COUNT,
        max(
            settings.display_order_count,
            normalize_candidate_order_count(settings.candidate_order_count),
        ),
    )


def normalize_candidate_order_count(value) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return DEFAULT_CANDIDATE_ORDER_COUNT

    if count in CANDIDATE_ORDER_COUNT_OPTIONS:
        return count

    return min(CANDIDATE_ORDER_COUNT_OPTIONS, key=lambda option: abs(option - count))


def normalize_description_check_mode(value: str | None) -> str:
    return value if value in DESCRIPTION_CHECK_MODE_OPTIONS else DESCRIPTION_CHECK_REGEX


def filter_orders(
    orders: list[dict] | None,
    exchange: str,
    settings: P2PFilterSettings,
    *,
    apply_description_filters: bool = True,
    apply_payment_filters: bool = True,
) -> list[dict]:
    if not orders:
        return []

    return [
        order
        for order in orders
        if order_matches(
            get_order_metrics(order, exchange),
            settings,
            apply_description_filters=apply_description_filters,
            apply_payment_filters=apply_payment_filters,
        )
    ]


def get_order_metrics(order: dict, exchange: str) -> dict:
    if exchange == "binance":
        return get_binance_order_metrics(order)

    return get_okx_order_metrics(order)


def get_binance_order_metrics(order: dict) -> dict:
    adv = order.get("adv", {})
    advertiser = order.get("advertiser", {})
    payment_names = get_binance_payment_names(adv.get("tradeMethods", []))
    detail = order.get("_detail") if isinstance(order.get("_detail"), dict) else {}
    description = normalize_order_description(
        order.get("_order_description"),
        detail.get("remarks"),
        detail.get("autoReplyMsg"),
        adv.get("remarks"),
        adv.get("autoReplyMsg"),
    )

    return {
        "minutes": max_known_minutes(
            parse_int(adv.get("payTimeLimit")),
            parse_description_payment_minutes(description),
        ),
        "trades": parse_int(
            advertiser.get("monthOrderCount") or advertiser.get("orderCount")
        ),
        "rating": parse_percent(advertiser.get("positiveRate")),
        "completion": parse_percent(advertiser.get("monthFinishRate")),
        "payment_categories": categorize_payment_methods(payment_names, description),
        "third_party_payments": has_third_party_payment_terms(description),
        "split_payments": has_split_payment_terms(description),
    }


def get_okx_order_metrics(order: dict) -> dict:
    payment_names = [str(method) for method in order.get("paymentMethods", [])]
    description = normalize_order_description(*get_okx_order_description_values(order))

    return {
        "minutes": max_known_minutes(
            parse_int(order.get("paymentTimeoutMinutes")),
            parse_description_payment_minutes(description),
        ),
        "trades": parse_int(order.get("completedOrderQuantity")),
        "rating": parse_percent(order.get("posReviewPercentage"))
        or parse_percent(order.get("completedRate")),
        "completion": parse_percent(order.get("completedRate")),
        "payment_categories": categorize_payment_methods(payment_names, description),
        "third_party_payments": has_third_party_payment_terms(description),
        "split_payments": has_split_payment_terms(description),
    }


def get_binance_payment_names(methods: list[dict]) -> list[str]:
    names = []

    for method in methods:
        name = (
            method.get("tradeMethodShortName")
            or method.get("tradeMethodName")
            or method.get("identifier")
            or method.get("payType")
        )

        if name:
            names.append(str(name))

    return names


def order_matches(
    metrics: dict,
    settings: P2PFilterSettings,
    *,
    apply_description_filters: bool = True,
    apply_payment_filters: bool = True,
) -> bool:
    if settings.max_order_minutes is not None and not value_lte(
        metrics["minutes"],
        settings.max_order_minutes,
    ):
        return False

    if settings.min_trades is not None and not value_gte(
        metrics["trades"],
        settings.min_trades,
    ):
        return False

    if settings.min_rating is not None and not value_gte(
        metrics["rating"],
        settings.min_rating,
    ):
        return False

    if settings.min_completion is not None and not value_gte(
        metrics["completion"],
        settings.min_completion,
    ):
        return False

    if apply_description_filters:
        if not settings.allow_third_party_payments and metrics["third_party_payments"]:
            return False

        if not settings.allow_split_payments and metrics["split_payments"]:
            return False

    if apply_payment_filters:
        return bool(settings.payment_categories & metrics["payment_categories"])

    return True


def value_lte(value, threshold) -> bool:
    return value is not None and value <= threshold


def value_gte(value, threshold) -> bool:
    return value is not None and value >= threshold


def categorize_payment_methods(
    payment_names: list[str],
    description: str | None = None,
) -> set[str]:
    if has_fop_only_payment_terms(description):
        return {PAYMENT_CATEGORY_FOP}

    categories = set()

    for name in payment_names:
        normalized = name.lower()

        if contains_any(normalized, FOP_PAYMENT_KEYWORDS):
            categories.add(PAYMENT_CATEGORY_FOP)
        elif contains_any(normalized, PERSON_PAYMENT_KEYWORDS):
            categories.add(PAYMENT_CATEGORY_PERSON)
        else:
            categories.add(PAYMENT_CATEGORY_OTHER)

    if has_fop_payment_terms(description):
        categories.add(PAYMENT_CATEGORY_FOP)

    return categories or {PAYMENT_CATEGORY_OTHER}


def contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def normalize_order_description(*values) -> str | None:
    for value in values:
        if not value:
            continue

        lines = [
            line.strip()
            for line in str(value).replace("\r", "\n").split("\n")
            if line.strip()
        ]
        text = "\n".join(lines)

        if text:
            return text

    return None


def normalize_search_text(value: str | None) -> str:
    if not value:
        return ""

    return " ".join(str(value).lower().replace("ё", "е").split())


def has_fop_payment_terms(description: str | None) -> bool:
    text = normalize_search_text(description)

    if not text:
        return False

    return contains_any(text, FOP_PAYMENT_KEYWORDS) or any(
        pattern.search(text) for pattern in BUSINESS_PAYMENT_PATTERNS
    )


def has_fop_only_payment_terms(description: str | None) -> bool:
    text = normalize_search_text(description)

    if not text:
        return False

    if not has_fop_payment_terms(text):
        return False

    return any(pattern.search(text) for pattern in FOP_ONLY_PAYMENT_PATTERNS) or any(
        pattern.search(text) for pattern in PERSON_PAYMENT_DENY_PATTERNS
    )


def has_third_party_payment_terms(description: str | None) -> bool:
    text = normalize_search_text(description)

    if not text:
        return False

    if contains_any(text, THIRD_PARTY_DENY_KEYWORDS) or any(
        pattern.search(text) for pattern in THIRD_PARTY_DENY_PATTERNS
    ):
        return False

    return contains_any(text, THIRD_PARTY_PAYMENT_KEYWORDS) or any(
        pattern.search(text) for pattern in THIRD_PARTY_PAYMENT_PATTERNS
    )


def has_split_payment_terms(description: str | None) -> bool:
    text = normalize_search_text(description)

    if not text:
        return False

    if any(pattern.search(text) for pattern in SPLIT_PAYMENT_PATTERNS):
        return True

    if contains_any(text, SPLIT_PAYMENT_DENY_KEYWORDS):
        return False

    if contains_any(text, SPLIT_PAYMENT_KEYWORDS):
        return True

    return False


def parse_description_payment_minutes(description: str | None) -> int | None:
    text = normalize_search_text(description)

    if not text:
        return None

    values = []

    for pattern in DESCRIPTION_PAYMENT_TIME_PATTERNS:
        for match in pattern.finditer(text):
            groups = match.groups()

            if len(groups) == 3:
                raw_value, unit = groups[1], groups[2]
            else:
                raw_value, unit = groups[0], groups[1]

            minutes = parse_duration_to_minutes(raw_value, unit)

            if minutes is not None:
                values.append(minutes)

    return max(values) if values else None


def parse_duration_to_minutes(value, unit: str) -> int | None:
    amount = parse_int(value)

    if amount is None:
        return None

    normalized_unit = normalize_search_text(unit)

    if any(token in normalized_unit for token in ("час", "год", "hour")):
        return amount * 60

    return amount


def max_known_minutes(*values: int | None) -> int | None:
    known_values = [value for value in values if value is not None]

    return max(known_values) if known_values else None


def parse_int(value) -> int | None:
    if value in (None, ""):
        return None

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_percent(value) -> float | None:
    if value in (None, "", -1, "-1"):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if number <= 1:
        number *= 100

    return number


def filters_summary(settings: P2PFilterSettings) -> str:
    parts = [
        f"Час угоди: {format_max_order_minutes(settings.max_order_minutes)}",
        f"Угоди: {format_min_number(settings.min_trades)}",
        f"Оцінка: {format_min_percent(settings.min_rating)}",
        f"Виконання: {format_min_percent(settings.min_completion)}",
        f"Методи: {format_payment_categories(settings.payment_categories)}",
        f"Оплата від 3-х осіб: {format_allowed(settings.allow_third_party_payments)}",
        f"Кілька платежів: {format_allowed(settings.allow_split_payments)}",
        f"Перевірка опису: {format_description_check_mode(settings.description_check_mode)}",
        f"Виводити ордерів: {settings.display_order_count}",
        f"Перевіряти кандидатів: {format_candidate_order_count(settings)}",
    ]

    return "\n".join(f"• {part}" for part in parts)


def format_max_order_minutes(value: int | None) -> str:
    return "будь-який" if value is None else f"до {value} хв"


def format_min_number(value: int | None) -> str:
    return "будь-яка к-сть" if value is None else f"від {value}"


def format_min_percent(value: float | None) -> str:
    return "будь-який" if value is None else f"від {value:g}%"


def format_payment_categories(categories: set[str]) -> str:
    labels = {
        PAYMENT_CATEGORY_FOP: "ФОП/ТОВ/IBAN",
        PAYMENT_CATEGORY_PERSON: "фізособа/карта",
        PAYMENT_CATEGORY_OTHER: "інші",
    }

    return ", ".join(labels[category] for category in labels if category in categories)


def format_allowed(value: bool) -> str:
    return "дозволено" if value else "заборонено"


def format_description_check_mode(value: str) -> str:
    labels = {
        DESCRIPTION_CHECK_REGEX: "Regex",
        DESCRIPTION_CHECK_REGEX_GPT: "Regex + GPT",
        DESCRIPTION_CHECK_GPT: "GPT",
    }

    return labels.get(normalize_description_check_mode(value), "Regex")


def format_candidate_order_count(settings: P2PFilterSettings) -> str:
    fetch_count = get_fetch_order_count(settings)

    return f"до {fetch_count}"
