import json
import re
from datetime import date, datetime, timedelta
from html import escape

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile

from db.base import AsyncSessionLocal
from db.dto import P2PUserPair
from fsm.states import AppMenu, P2PExchange
from keyboards.menu import (
    BTN_BACK,
    BTN_CABINET,
    CB_FILTERS_MENU,
    CB_FILTERS_PAY_PREFIX,
    CB_FILTERS_RESET,
    CB_FILTERS_SCREEN_PREFIX,
    CB_FILTERS_SET_PREFIX,
    BTN_FILTER_CANDIDATE_COUNT_PREFIX,
    BTN_FILTER_FOP_PREFIX,
    BTN_FILTER_DISPLAY_COUNT_PREFIX,
    BTN_FILTER_DESCRIPTION_CHECK_PREFIX,
    BTN_FILTER_MIN_COMPLETION_PREFIX,
    BTN_FILTER_MIN_RATING_PREFIX,
    BTN_FILTER_MIN_TRADES_PREFIX,
    BTN_FILTER_MONOBANK_JAR_PREFIX,
    BTN_FILTER_ORDER_TIME_PREFIX,
    BTN_FILTER_OTHER_PREFIX,
    BTN_FILTER_PERSON_PREFIX,
    BTN_FILTER_SPLIT_PAYMENTS_PREFIX,
    BTN_FILTER_THIRD_PARTY_PREFIX,
    BTN_KNOWLEDGE_BASE,
    BTN_MY_INFO,
    BTN_P2P,
    BTN_P2P_FILTERS,
    BTN_P2P_PAIRS,
    BTN_RESET_FILTERS,
    BTN_SHARE_LOCATION,
    BTN_STATISTICS,
    CB_P2P_PAIR_BACK,
    CB_P2P_PAIR_CRYPTO_PREFIX,
    CB_P2P_PAIR_NOOP,
    CB_P2P_PAIR_TOGGLE_PREFIX,
    CB_STATS_PAIR_BACK,
    CB_STATS_PAIR_CRYPTO_PREFIX,
    CB_STATS_PAIR_SELECT_PREFIX,
    CB_STATS_DIRECTION_PREFIX,
    CB_STATS_DATE_NEXT,
    CB_STATS_DATE_PICK,
    CB_STATS_DATE_PREFIX,
    CB_STATS_DATE_PREV,
    CB_STATS_DATE_TODAY,
    CB_STATS_EXCHANGE_PREFIX,
    CB_STATS_PERIOD_PREFIX,
    CB_STATS_SCOPE_PREFIX,
    BTN_USER_PAYMENT_METHODS,
    CB_USER_PAYMENT_BACK,
    CB_USER_PAYMENT_FIAT_PREFIX,
    CB_USER_PAYMENT_TOGGLE_PREFIX,
    FILTER_SCREEN_CANDIDATE_COUNT,
    FILTER_SCREEN_DESCRIPTION_CHECK,
    FILTER_SCREEN_DISPLAY_COUNT,
    FILTER_SCREEN_MIN_COMPLETION,
    FILTER_SCREEN_MIN_RATING,
    FILTER_SCREEN_MIN_TRADES,
    FILTER_SCREEN_MONOBANK_JAR,
    FILTER_SCREEN_ORDER_TIME,
    FILTER_SCREEN_PAYMENT_METHODS,
    FILTER_SCREEN_SPLIT_PAYMENTS,
    FILTER_SCREEN_THIRD_PARTY,
    cabinet_kb,
    knowledge_base_kb,
    p2p_exchange_inline_kb,
    p2p_filter_values_inline_kb,
    p2p_filters_inline_kb,
    p2p_pair_fiats_inline_kb,
    p2p_pairs_inline_kb,
    statistics_direction_inline_kb,
    statistics_exchange_choice_inline_kb,
    statistics_exchange_inline_kb,
    statistics_pair_cryptos_inline_kb,
    statistics_pair_fiats_inline_kb,
    statistics_period_inline_kb,
    statistics_scope_inline_kb,
    user_payment_fiats_inline_kb,
    user_payment_methods_inline_kb,
)
from services.menu_service import can_use_knowledge_base, root_menu_for_user
from services.payment_method_service import PaymentMethodService
from services.p2p_pair_service import P2PPairService, format_pairs_summary
from services.p2p_filters import (
    PAYMENT_CATEGORY_FOP,
    PAYMENT_CATEGORY_OTHER,
    PAYMENT_CATEGORY_PERSON,
    cycle_candidate_order_count,
    cycle_description_check_mode,
    cycle_display_order_count,
    cycle_min_completion,
    cycle_min_rating,
    cycle_min_trades,
    cycle_order_minutes,
    filters_summary,
    get_filters,
    reset_filters,
    set_candidate_order_count,
    set_description_check_mode,
    set_display_order_count,
    set_min_completion,
    set_monobank_jar_payments,
    set_min_rating,
    set_min_trades,
    set_order_minutes,
    set_split_payments,
    set_third_party_payments,
    toggle_split_payments,
    toggle_monobank_jar_payments,
    toggle_payment_category,
    toggle_third_party_payments,
)
from services.p2p_exchange_drivers import (
    P2P_DIRECTION_CRYPTO_TO_FIAT,
    P2P_DIRECTION_FIAT_TO_CRYPTO,
    get_p2p_exchange_driver,
)
from services.p2p_statistics_service import (
    STAT_PERIOD_DAY,
    STAT_PERIOD_HOUR,
    STAT_PERIOD_LABELS,
    STAT_PERIOD_MONTH,
    STAT_PERIOD_TYPES,
    STAT_PERIOD_WEEK,
    STAT_PERIOD_YEAR,
    STAT_SCOPE_FILTER,
    STAT_SCOPE_GLOBAL,
    build_statistics_filter_hash,
    P2PStatisticsService,
)
from services.p2p_statistics_chart import (
    build_p2p_statistics_caption,
    get_statistics_metric_label,
    get_statistics_metric_value,
    render_p2p_statistics_chart,
)
from services.p2p_knowledge_base import answer_p2p_knowledge_question
from services.statistics_settings_service import StatisticsSettingsService
from services.telegram_payloads import dump_telegram_model
from services.timezone_resolver import resolve_timezone_from_coordinates
from services.time_utils import (
    display_dates_to_utc_naive_range,
    display_datetime,
    display_today,
)
from services.user_service import UserService

router = Router()
STATISTICS_HISTORY_PERIODS = 12
STATISTICS_HOURLY_DATE_PERIODS = 24
STATISTICS_DAILY_MONTH_PERIODS = 31
STATISTICS_WEEKLY_YEAR_PERIODS = 54
STATISTICS_MONTHLY_YEAR_PERIODS = 12
STATISTICS_YEARLY_DECADE_PERIODS = 10
TELEGRAM_MESSAGE_LIMIT = 3900
ALLOWED_KNOWLEDGE_HTML_TAGS = {"b", "i", "u", "s", "code"}
STATISTICS_EXCHANGES = {"binance", "okx"}
STATISTICS_DIRECTION_MIXED = "mixed"
STATISTICS_DIRECTIONS = {
    P2P_DIRECTION_FIAT_TO_CRYPTO,
    P2P_DIRECTION_CRYPTO_TO_FIAT,
    STATISTICS_DIRECTION_MIXED,
}
STATISTICS_EXCHANGE_LABELS = {
    "binance": "Binance",
    "okx": "OKX",
}
STATISTICS_DIRECTION_LABELS = {
    P2P_DIRECTION_FIAT_TO_CRYPTO: "Фіат → Крипта",
    P2P_DIRECTION_CRYPTO_TO_FIAT: "Крипта → Фіат",
    STATISTICS_DIRECTION_MIXED: "Змішаний",
}

FILTER_SCREEN_TEXTS = {
    FILTER_SCREEN_ORDER_TIME: (
        "Час угоди",
        "Оберіть максимальний час, протягом якого мерчант очікує оплату.",
    ),
    FILTER_SCREEN_MIN_TRADES: (
        "Кількість угод",
        "Оберіть мінімальну кількість завершених угод у мерчанта.",
    ),
    FILTER_SCREEN_MIN_RATING: (
        "Оцінка мерчанта",
        "Оберіть мінімальний відсоток позитивної оцінки мерчанта.",
    ),
    FILTER_SCREEN_MIN_COMPLETION: (
        "Виконання угод",
        "Оберіть мінімальний відсоток виконаних угод.",
    ),
    FILTER_SCREEN_PAYMENT_METHODS: (
        "Методи оплати",
        "Залиште увімкненими типи методів, які підходять для пошуку.",
    ),
    FILTER_SCREEN_THIRD_PARTY: (
        "Оплата від третіх осіб",
        "Якщо заборонити, бот прибере ордери, де в описі дозволена оплата не від власника акаунта.",
    ),
    FILTER_SCREEN_SPLIT_PAYMENTS: (
        "Кілька платежів",
        "Якщо заборонити, бот прибере ордери, де в описі дозволено або просять платити частинами.",
    ),
    FILTER_SCREEN_MONOBANK_JAR: (
        "Банка / збір / конверт",
        "Якщо заборонити, бот прибере ордери, де в описі просять оплату через Monobank «банку», A-Bank «збір» або PrivatBank «конверт».",
    ),
    FILTER_SCREEN_DESCRIPTION_CHECK: (
        "Перевірка опису",
        "Regex швидший, GPT краще розуміє нечіткі формулювання, а Regex + GPT спочатку прибирає очевидне regex-ом і потім перевіряє решту через GPT.",
    ),
    FILTER_SCREEN_DISPLAY_COUNT: (
        "Кількість у видачі",
        "Оберіть, скільки ордерів показувати в Telegram після фільтрації.",
    ),
    FILTER_SCREEN_CANDIDATE_COUNT: (
        "Кандидати для перевірки",
        "Оберіть, скільки перших ордерів перевіряти описами перед фінальною видачею.",
    ),
}

TELEGRAM_USER_MAIN_FIELDS = (
    ("id", "Telegram ID"),
    ("first_name", "Ім'я"),
    ("last_name", "Прізвище"),
    ("username", "Username"),
    ("language_code", "Мова"),
    ("is_premium", "Telegram Premium"),
)

TELEGRAM_USER_CAPABILITY_FIELDS = (
    ("is_bot", "Бот"),
    ("can_join_groups", "Може вступати в групи"),
    ("can_read_all_group_messages", "Читає всі повідомлення груп"),
    ("supports_inline_queries", "Підтримує inline-запити"),
    ("added_to_attachment_menu", "Доданий в attachment menu"),
)

TELEGRAM_USER_KNOWN_FIELDS = {
    key
    for key, _ in TELEGRAM_USER_MAIN_FIELDS + TELEGRAM_USER_CAPABILITY_FIELDS
}


@router.message(F.text == BTN_P2P)
async def p2p_menu(message: types.Message, state: FSMContext):
    await state.set_state(AppMenu.p2p_exchanges)

    async with AsyncSessionLocal() as session:
        pair_service = P2PPairService(session)
        selected_pairs = await pair_service.list_selected_pairs(message.from_user.id)

    await message.answer(
        "Оберіть біржу:\n\n"
        f"Обрані P2P пари: <b>{escape(format_pairs_summary(selected_pairs))}</b>",
        reply_markup=p2p_exchange_inline_kb(),
    )


@router.message(F.text == BTN_CABINET)
async def cabinet_menu(message: types.Message, state: FSMContext):
    await state.set_state(AppMenu.cabinet)

    await message.answer(
        "Особистий кабінет:",
        reply_markup=cabinet_kb(message.from_user.id),
    )


@router.message(
    StateFilter(
        None,
        AppMenu.p2p_exchanges,
        AppMenu.cabinet,
        AppMenu.p2p_filters,
        AppMenu.p2p_pairs,
        AppMenu.payment_methods,
        AppMenu.statistics,
        P2PExchange.binance,
        P2PExchange.okx,
    ),
    F.text == BTN_STATISTICS,
)
async def statistics_menu(message: types.Message, state: FSMContext):
    await state.set_state(AppMenu.statistics)
    await clear_statistics_pair(state)
    await send_statistics_exchange_choice_menu(message)


@router.message(F.text == BTN_KNOWLEDGE_BASE)
async def knowledge_base_menu(message: types.Message, state: FSMContext):
    if not can_use_knowledge_base(message.from_user.id if message.from_user else None):
        await message.answer("Цей розділ зараз недоступний для вашого акаунта.")
        return

    await state.set_state(AppMenu.knowledge_base)

    await message.answer(
        "<b>🧠 P2P база знань</b>\n\n"
        "Напишіть питання по матеріалах з бази знань. "
        "Я знайду відповідь у файлах <code>knowledge_base/*.md</code>.",
        reply_markup=knowledge_base_kb(),
    )


@router.message(
    StateFilter(
        AppMenu.p2p_filters,
        AppMenu.p2p_pairs,
        AppMenu.payment_methods,
        AppMenu.statistics,
        AppMenu.statistics_period_input,
    ),
    F.text == BTN_BACK,
)
async def back_to_cabinet(message: types.Message, state: FSMContext):
    current_state = await state.get_state()

    if current_state == AppMenu.statistics.state:
        await state.clear()
        await message.answer(
            "Головне меню:",
            reply_markup=await root_menu_for_user(message.from_user.id),
        )
        return

    await state.set_state(AppMenu.cabinet)

    await message.answer(
        "Особистий кабінет:",
        reply_markup=cabinet_kb(message.from_user.id),
    )


@router.message(
    StateFilter(AppMenu.p2p_exchanges, AppMenu.cabinet, AppMenu.knowledge_base, None),
    F.text == BTN_BACK,
)
async def back_to_main_menu(message: types.Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Головне меню:",
        reply_markup=await root_menu_for_user(message.from_user.id),
    )


@router.message(StateFilter(AppMenu.knowledge_base), F.text)
async def answer_knowledge_base_question(message: types.Message):
    if not can_use_knowledge_base(message.from_user.id if message.from_user else None):
        await message.answer("Цей розділ зараз недоступний для вашого акаунта.")
        return

    question = (message.text or "").strip()

    if len(question) < 3:
        await message.answer(
            "Напишіть питання трохи детальніше.",
            reply_markup=knowledge_base_kb(),
        )
        return

    await message.answer("Шукаю відповідь у P2P базі знань...")
    knowledge_answer = await answer_p2p_knowledge_question(question)
    response_text = build_knowledge_base_answer_text(knowledge_answer)

    for part in split_long_message(response_text):
        try:
            await message.answer(part, reply_markup=knowledge_base_kb())
        except TelegramBadRequest:
            await message.answer(
                strip_telegram_html(part),
                reply_markup=knowledge_base_kb(),
            )


@router.message(F.text == BTN_MY_INFO)
async def my_info(message: types.Message):
    telegram_data = dump_telegram_model(message.from_user)

    async with AsyncSessionLocal() as session:
        service = UserService(session)
        user = await service.register_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            telegram_data=telegram_data,
        )
        roles = await service.get_user_role_codes(message.from_user.id)

    if not user:
        await message.answer("Профіль ще не створено. Натисніть /start.")
        return

    await send_profile_info(message, user, roles)


@router.message(F.location)
async def save_user_location(message: types.Message, state: FSMContext):
    if not message.from_user or not message.location:
        return

    await state.set_state(AppMenu.cabinet)

    telegram_data = dump_telegram_model(message.from_user)
    location_data = dump_telegram_model(message.location) or {}
    location_message_data = dump_telegram_model(message)
    timezone_name = resolve_timezone_from_coordinates(
        location_data.get("latitude"),
        location_data.get("longitude"),
    )

    async with AsyncSessionLocal() as session:
        service = UserService(session)
        user = await service.save_user_location(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            telegram_data=telegram_data,
            location_data=location_data,
            location_message_data=location_message_data,
            timezone_name=timezone_name,
        )

    await message.answer(
        build_location_saved_text(user),
        reply_markup=cabinet_kb(message.from_user.id),
    )


@router.message(F.text == BTN_SHARE_LOCATION)
async def share_location_help(message: types.Message):
    await message.answer(
        "Натисніть кнопку нижче і підтвердьте відправку геолокації. "
        "Після цього бот збереже координати, timezone і сирі Telegram-дані.",
        reply_markup=cabinet_kb(message.from_user.id),
    )


@router.message(F.text == BTN_P2P_FILTERS)
async def p2p_filters(message: types.Message, state: FSMContext):
    await state.set_state(AppMenu.p2p_filters)
    await send_filters_menu(message)


@router.message(F.text == BTN_P2P_PAIRS)
async def p2p_pairs(message: types.Message, state: FSMContext):
    await state.set_state(AppMenu.p2p_pairs)
    await send_p2p_pairs_menu(message)


@router.callback_query(StateFilter(AppMenu.statistics), F.data == CB_STATS_PAIR_BACK)
async def statistics_pair_back(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    exchange = normalize_statistics_exchange(data.get("statistics_exchange"))

    if exchange:
        await edit_statistics_pair_crypto_for_exchange(callback, state, exchange)
        return

    await edit_statistics_pair_crypto_menu(callback, state)


@router.callback_query(
    StateFilter(AppMenu.statistics),
    F.data.startswith(CB_STATS_PAIR_CRYPTO_PREFIX),
)
async def statistics_pair_crypto_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    crypto_currency_id = parse_statistics_pair_crypto_callback(callback.data or "")

    if not crypto_currency_id:
        await callback.answer("Не вдалося прочитати стейбл", show_alert=True)
        return

    selected_pairs = await load_selected_p2p_pairs(callback.from_user.id)
    crypto_pairs = filter_pairs_by_crypto(selected_pairs, crypto_currency_id)
    data = await state.get_data()
    exchange = normalize_statistics_exchange(data.get("statistics_exchange"))

    if not crypto_pairs:
        await callback.answer("Для цього стейбла немає обраних фіатів", show_alert=True)
        return

    await state.set_state(AppMenu.statistics)
    await callback.answer(crypto_pairs[0].crypto_code)

    if exchange and len(crypto_pairs) == 1:
        pair = crypto_pairs[0]
        await set_statistics_pair(state, pair)
        await set_statistics_exchange(state, exchange)

        if callback.message:
            await replace_statistics_direction_message(callback.message, pair, exchange)

        return

    if callback.message:
        await safe_edit_callback_message(
            callback,
            build_statistics_pair_fiats_text(selected_pairs, crypto_currency_id),
            statistics_pair_fiats_inline_kb(
                selected_pairs,
                crypto_currency_id,
                back_callback=get_statistics_fiat_back_callback(selected_pairs),
            ),
        )


@router.callback_query(
    StateFilter(AppMenu.statistics),
    F.data.startswith(CB_STATS_PAIR_SELECT_PREFIX),
)
async def statistics_pair_select_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    crypto_currency_id, fiat_currency_id = parse_statistics_pair_select_callback(
        callback.data or ""
    )

    if not crypto_currency_id or not fiat_currency_id:
        await callback.answer("Не вдалося прочитати пару", show_alert=True)
        return

    pair = await load_selected_statistics_pair(
        callback.from_user.id,
        crypto_currency_id,
        fiat_currency_id,
    )

    if not pair:
        await callback.answer("Ця пара не обрана або вже недоступна", show_alert=True)
        return

    data = await state.get_data()
    exchange = normalize_statistics_exchange(data.get("statistics_exchange"))
    await set_statistics_pair(state, pair)

    if exchange:
        await set_statistics_exchange(state, exchange)
        await callback.answer(pair.label)

        if callback.message:
            await replace_statistics_direction_message(callback.message, pair, exchange)

        return

    await callback.answer(pair.label)

    if callback.message:
        await replace_statistics_exchange_message(callback.message, pair)


@router.callback_query(
    StateFilter(AppMenu.statistics),
    F.data.startswith(CB_STATS_EXCHANGE_PREFIX),
)
async def statistics_exchange_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    if (callback.data or "") == f"{CB_STATS_EXCHANGE_PREFIX}back":
        await edit_statistics_exchange_choice_menu(callback, state)
        return

    exchange, crypto_currency_id, fiat_currency_id = parse_statistics_exchange_callback(
        callback.data or ""
    )

    if not exchange:
        await callback.answer("Не вдалося прочитати біржу", show_alert=True)
        return

    if not crypto_currency_id or not fiat_currency_id:
        await set_statistics_exchange(state, exchange)
        await callback.answer(format_statistics_exchange_label(exchange))

        if callback.message:
            await edit_statistics_pair_crypto_for_exchange(callback, state, exchange)

        return

    pair = await load_selected_statistics_pair(
        callback.from_user.id,
        crypto_currency_id,
        fiat_currency_id,
    )

    if not pair:
        await callback.answer("Ця пара не обрана або вже недоступна", show_alert=True)
        return

    await set_statistics_exchange(state, exchange)
    await callback.answer(format_statistics_exchange_label(exchange))

    if callback.message:
        await replace_statistics_direction_message(callback.message, pair, exchange)


@router.callback_query(
    StateFilter(AppMenu.statistics),
    F.data.startswith(CB_STATS_DIRECTION_PREFIX),
)
async def statistics_direction_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    exchange, direction, crypto_currency_id, fiat_currency_id = (
        parse_statistics_direction_callback(callback.data or "")
    )

    if not exchange or not direction or not crypto_currency_id or not fiat_currency_id:
        await callback.answer("Не вдалося прочитати напрямок", show_alert=True)
        return

    pair = await load_selected_statistics_pair(
        callback.from_user.id,
        crypto_currency_id,
        fiat_currency_id,
    )

    if not pair:
        await callback.answer("Ця пара не обрана або вже недоступна", show_alert=True)
        return

    await set_statistics_direction(state, exchange, direction)
    await callback.answer(format_statistics_direction_label(direction))

    if callback.message:
        await replace_statistics_scope_message(
            callback.message,
            state,
            pair=pair,
            exchange=exchange,
            direction=direction,
        )


@router.callback_query(F.data.startswith(CB_STATS_PERIOD_PREFIX))
async def statistics_period_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    scope, period_type, exchange, direction, crypto_currency_id, fiat_currency_id = (
        parse_statistics_period_callback(callback.data or "")
    )

    if period_type not in STAT_PERIOD_TYPES or not is_supported_statistics_scope(scope):
        await callback.answer("Не вдалося прочитати період", show_alert=True)
        return

    pair = await resolve_statistics_pair(
        callback.from_user.id,
        state,
        crypto_currency_id,
        fiat_currency_id,
    )
    exchange, direction = await resolve_statistics_market(
        state,
        exchange=exchange,
        direction=direction,
    )

    if not pair:
        await callback.answer("Спочатку оберіть пару для статистики", show_alert=True)
        return

    if not exchange or not direction:
        await callback.answer("Спочатку оберіть біржу і напрямок", show_alert=True)
        return

    timezone_name = await get_user_timezone_name(callback.from_user.id)
    selected_anchor = normalize_statistics_period_anchor(
        period_type,
        await get_statistics_period_anchor(state, period_type=period_type),
    )
    selected_anchor = selected_anchor or current_statistics_period_anchor(
        period_type,
        timezone_name,
    )
    await set_statistics_view_context(state, scope, period_type, selected_anchor)

    stats = await load_statistics_for_user(
        callback.from_user.id,
        scope,
        period_type,
        pair,
        exchange,
        direction,
        selected_anchor=selected_anchor,
        timezone_name=timezone_name,
    )

    await callback.answer(STAT_PERIOD_LABELS.get(period_type, period_type))

    if callback.message:
        await replace_statistics_message(
            callback.message,
            pair,
            exchange,
            direction,
            stats,
            period_type,
            scope,
            selected_anchor=selected_anchor,
            timezone_name=timezone_name,
        )


@router.callback_query(
    StateFilter(AppMenu.statistics, AppMenu.statistics_period_input),
    F.data.startswith(CB_STATS_DATE_PREFIX),
)
async def statistics_date_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    action = (callback.data or "")[len(CB_STATS_DATE_PREFIX):]
    data = await state.get_data()
    period_type = data.get("statistics_period_type") or STAT_PERIOD_HOUR

    if action == "pick":
        await state.set_state(AppMenu.statistics_period_input)
        await state.update_data(statistics_waiting_period_type=period_type)
        await callback.answer()

        if callback.message:
            await callback.message.answer(
                build_statistics_period_input_prompt(period_type)
            )

        return

    pair = await resolve_statistics_pair(callback.from_user.id, state)
    exchange, direction = await resolve_statistics_market(state)

    if not pair or not exchange or not direction:
        await callback.answer("Спочатку оберіть пару, біржу і напрямок", show_alert=True)
        return

    timezone_name = await get_user_timezone_name(callback.from_user.id)
    current_anchor = await get_statistics_period_anchor(state)
    selected_anchor = resolve_statistics_period_action(
        period_type,
        action,
        current_anchor,
        timezone_name=timezone_name,
    )

    if action == "next" and is_future_statistics_anchor(
        period_type,
        selected_anchor,
        timezone_name=timezone_name,
    ):
        await callback.answer("Це майбутній період", show_alert=True)
        return

    scope = data.get("statistics_scope") or STAT_SCOPE_GLOBAL
    await set_statistics_view_context(state, scope, period_type, selected_anchor)

    stats = await load_statistics_for_user(
        callback.from_user.id,
        scope,
        period_type,
        pair,
        exchange,
        direction,
        selected_anchor=selected_anchor,
        timezone_name=timezone_name,
    )

    await callback.answer(format_statistics_period_answer(period_type, selected_anchor))

    if callback.message:
        await replace_statistics_message(
            callback.message,
            pair,
            exchange,
            direction,
            stats,
            period_type,
            scope,
            selected_anchor=selected_anchor,
            timezone_name=timezone_name,
        )


@router.callback_query(F.data.startswith(CB_STATS_SCOPE_PREFIX))
async def statistics_scope_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    scope, exchange, direction, crypto_currency_id, fiat_currency_id = (
        parse_statistics_scope_callback(callback.data or "")
    )
    pair = await resolve_statistics_pair(
        callback.from_user.id,
        state,
        crypto_currency_id,
        fiat_currency_id,
    )
    exchange, direction = await resolve_statistics_market(
        state,
        exchange=exchange,
        direction=direction,
    )

    if scope == "menu":
        if pair and exchange and direction and callback.message:
            await callback.answer()
            await replace_statistics_scope_message(
                callback.message,
                state,
                pair=pair,
                exchange=exchange,
                direction=direction,
            )
        else:
            await edit_statistics_pair_crypto_menu(callback, state)

        return

    if not is_supported_statistics_scope(scope):
        await callback.answer("Не вдалося прочитати тип статистики", show_alert=True)
        return

    if not pair:
        await callback.answer("Спочатку оберіть пару для статистики", show_alert=True)
        return

    if not exchange or not direction:
        await callback.answer("Спочатку оберіть біржу і напрямок", show_alert=True)
        return

    timezone_name = await get_user_timezone_name(callback.from_user.id)
    selected_anchor = current_statistics_period_anchor(
        STAT_PERIOD_DAY,
        timezone_name,
    )
    await set_statistics_view_context(state, scope, STAT_PERIOD_DAY, selected_anchor)

    stats = await load_statistics_for_user(
        callback.from_user.id,
        scope,
        STAT_PERIOD_DAY,
        pair,
        exchange,
        direction,
        selected_anchor=selected_anchor,
        timezone_name=timezone_name,
    )

    await callback.answer(format_statistics_scope_title(scope))

    if callback.message:
        await replace_statistics_message(
            callback.message,
            pair,
            exchange,
            direction,
            stats,
            STAT_PERIOD_DAY,
            scope,
            selected_anchor=selected_anchor,
            timezone_name=timezone_name,
        )


@router.message(StateFilter(AppMenu.statistics_period_input), F.text)
async def statistics_date_input(message: types.Message, state: FSMContext):
    data = await state.get_data()
    period_type = data.get("statistics_waiting_period_type") or data.get(
        "statistics_period_type"
    ) or STAT_PERIOD_HOUR

    selected_anchor = parse_statistics_period_input(message.text or "", period_type)

    if selected_anchor is None:
        await message.answer(build_statistics_period_input_error(period_type))
        return

    timezone_name = await get_user_timezone_name(message.from_user.id)

    if is_future_statistics_anchor(
        period_type,
        selected_anchor,
        timezone_name=timezone_name,
    ):
        await message.answer("Це майбутній період. Введіть поточний або минулий період.")
        return

    pair = await resolve_statistics_pair(message.from_user.id, state)
    exchange, direction = await resolve_statistics_market(state)

    if not pair or not exchange or not direction:
        await state.set_state(AppMenu.statistics)
        await state.update_data(statistics_waiting_period_type=None)
        await message.answer("Спочатку оберіть пару, біржу і напрямок для статистики.")
        return

    scope = data.get("statistics_scope") or STAT_SCOPE_GLOBAL
    await set_statistics_view_context(state, scope, period_type, selected_anchor)

    stats = await load_statistics_for_user(
        message.from_user.id,
        scope,
        period_type,
        pair,
        exchange,
        direction,
        selected_anchor=selected_anchor,
        timezone_name=timezone_name,
    )

    await send_statistics_message(
        message,
        pair,
        exchange,
        direction,
        stats,
        period_type,
        scope,
        selected_anchor=selected_anchor,
        timezone_name=timezone_name,
    )


@router.message(F.text == BTN_USER_PAYMENT_METHODS)
async def user_payment_methods(message: types.Message, state: FSMContext):
    await state.set_state(AppMenu.payment_methods)
    await send_user_payment_fiats_menu(message)


@router.callback_query(F.data == CB_USER_PAYMENT_BACK)
async def back_to_user_payment_fiats(callback: types.CallbackQuery):
    await callback.answer()
    await edit_user_payment_fiats_menu(callback)


@router.callback_query(F.data.startswith(CB_USER_PAYMENT_FIAT_PREFIX))
async def choose_user_payment_fiat(callback: types.CallbackQuery):
    fiat_currency_id = parse_user_payment_fiat_callback(callback.data or "")

    if not fiat_currency_id:
        await callback.answer("Не вдалося прочитати валюту", show_alert=True)
        return

    await callback.answer()
    await edit_user_payment_methods_for_fiat(callback, fiat_currency_id)


@router.callback_query(F.data.startswith(CB_USER_PAYMENT_TOGGLE_PREFIX))
async def toggle_user_payment_method(callback: types.CallbackQuery):
    payment_method_id = parse_user_payment_toggle_callback(callback.data or "")

    if not payment_method_id:
        await callback.answer("Не вдалося прочитати банк", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        service = PaymentMethodService(session)
        result = await service.toggle_user_method(
            callback.from_user.id,
            payment_method_id,
        )

    await callback.answer(result.message, show_alert=not result.changed)

    if not result.methods:
        await edit_user_payment_fiats_menu(callback)
        return

    await safe_edit_callback_message(
        callback,
        build_user_payment_methods_text(result.methods, prefix=result.message),
        user_payment_methods_inline_kb(result.methods),
    )


@router.callback_query(F.data == CB_P2P_PAIR_NOOP)
async def p2p_pair_noop(callback: types.CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == CB_P2P_PAIR_BACK)
async def back_to_p2p_pair_cryptos(callback: types.CallbackQuery):
    async with AsyncSessionLocal() as session:
        service = P2PPairService(session)
        pairs = await service.list_available_pairs(callback.from_user.id)

    await callback.answer()

    if callback.message:
        await safe_edit_callback_message(
            callback,
            build_p2p_pairs_text(pairs),
            p2p_pairs_inline_kb(pairs) if pairs else None,
        )


@router.callback_query(F.data.startswith(CB_P2P_PAIR_CRYPTO_PREFIX))
async def choose_p2p_pair_crypto(callback: types.CallbackQuery):
    crypto_currency_id = parse_pair_crypto_callback(callback.data or "")

    if not crypto_currency_id:
        await callback.answer("Не вдалося прочитати стейбл", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        service = P2PPairService(session)
        pairs = await service.list_available_pairs(callback.from_user.id)

    crypto_pairs = filter_pairs_by_crypto(pairs, crypto_currency_id)

    if not crypto_pairs:
        await callback.answer("Для цього стейбла немає доступних фіатів", show_alert=True)
        return

    await callback.answer(crypto_pairs[0].crypto_code)

    if callback.message:
        await safe_edit_callback_message(
            callback,
            build_p2p_pair_fiats_text(pairs, crypto_currency_id),
            p2p_pair_fiats_inline_kb(pairs, crypto_currency_id),
        )


@router.callback_query(F.data.startswith(CB_P2P_PAIR_TOGGLE_PREFIX))
async def toggle_p2p_pair_callback(callback: types.CallbackQuery):
    crypto_currency_id, fiat_currency_id = parse_pair_callback(callback.data or "")

    if not crypto_currency_id or not fiat_currency_id:
        await callback.answer("Не вдалося прочитати пару", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        service = P2PPairService(session)
        result = await service.toggle_pair(
            callback.from_user.id,
            crypto_currency_id,
            fiat_currency_id,
        )

    await callback.answer(result.message, show_alert=not result.changed)

    if callback.message:
        await safe_edit_callback_message(
            callback,
            build_p2p_pair_fiats_text(result.pairs, crypto_currency_id),
            (
                p2p_pair_fiats_inline_kb(result.pairs, crypto_currency_id)
                if result.pairs
                else None
            ),
        )


@router.message(StateFilter(AppMenu.p2p_filters), F.text.startswith(BTN_FILTER_ORDER_TIME_PREFIX))
async def change_order_time_filter(message: types.Message):
    async with AsyncSessionLocal() as session:
        await cycle_order_minutes(session, message.from_user.id)

    await send_filters_menu(message)


@router.message(StateFilter(AppMenu.p2p_filters), F.text.startswith(BTN_FILTER_MIN_TRADES_PREFIX))
async def change_min_trades_filter(message: types.Message):
    async with AsyncSessionLocal() as session:
        await cycle_min_trades(session, message.from_user.id)

    await send_filters_menu(message)


@router.message(StateFilter(AppMenu.p2p_filters), F.text.startswith(BTN_FILTER_DISPLAY_COUNT_PREFIX))
async def change_display_order_count_filter(message: types.Message):
    async with AsyncSessionLocal() as session:
        await cycle_display_order_count(session, message.from_user.id)

    await send_filters_menu(message)


@router.message(StateFilter(AppMenu.p2p_filters), F.text.startswith(BTN_FILTER_CANDIDATE_COUNT_PREFIX))
async def change_candidate_order_count_filter(message: types.Message):
    async with AsyncSessionLocal() as session:
        await cycle_candidate_order_count(session, message.from_user.id)

    await send_filters_menu(message)


@router.message(StateFilter(AppMenu.p2p_filters), F.text.startswith(BTN_FILTER_DESCRIPTION_CHECK_PREFIX))
async def change_description_check_mode(message: types.Message):
    async with AsyncSessionLocal() as session:
        await cycle_description_check_mode(session, message.from_user.id)

    await send_filters_menu(message)


@router.message(StateFilter(AppMenu.p2p_filters), F.text.startswith(BTN_FILTER_MIN_RATING_PREFIX))
async def change_min_rating_filter(message: types.Message):
    async with AsyncSessionLocal() as session:
        await cycle_min_rating(session, message.from_user.id)

    await send_filters_menu(message)


@router.message(StateFilter(AppMenu.p2p_filters), F.text.startswith(BTN_FILTER_MIN_COMPLETION_PREFIX))
async def change_min_completion_filter(message: types.Message):
    async with AsyncSessionLocal() as session:
        await cycle_min_completion(session, message.from_user.id)

    await send_filters_menu(message)


@router.message(StateFilter(AppMenu.p2p_filters), F.text.startswith(BTN_FILTER_FOP_PREFIX))
async def toggle_fop_filter(message: types.Message):
    async with AsyncSessionLocal() as session:
        await toggle_payment_category(session, message.from_user.id, PAYMENT_CATEGORY_FOP)

    await send_filters_menu(message)


@router.message(StateFilter(AppMenu.p2p_filters), F.text.startswith(BTN_FILTER_PERSON_PREFIX))
async def toggle_person_filter(message: types.Message):
    async with AsyncSessionLocal() as session:
        await toggle_payment_category(session, message.from_user.id, PAYMENT_CATEGORY_PERSON)

    await send_filters_menu(message)


@router.message(StateFilter(AppMenu.p2p_filters), F.text.startswith(BTN_FILTER_OTHER_PREFIX))
async def toggle_other_filter(message: types.Message):
    async with AsyncSessionLocal() as session:
        await toggle_payment_category(session, message.from_user.id, PAYMENT_CATEGORY_OTHER)

    await send_filters_menu(message)


@router.message(StateFilter(AppMenu.p2p_filters), F.text.startswith(BTN_FILTER_THIRD_PARTY_PREFIX))
async def toggle_third_party_filter(message: types.Message):
    async with AsyncSessionLocal() as session:
        await toggle_third_party_payments(session, message.from_user.id)

    await send_filters_menu(message)


@router.message(StateFilter(AppMenu.p2p_filters), F.text.startswith(BTN_FILTER_SPLIT_PAYMENTS_PREFIX))
async def toggle_split_payments_filter(message: types.Message):
    async with AsyncSessionLocal() as session:
        await toggle_split_payments(session, message.from_user.id)

    await send_filters_menu(message)


@router.message(StateFilter(AppMenu.p2p_filters), F.text.startswith(BTN_FILTER_MONOBANK_JAR_PREFIX))
async def toggle_monobank_jar_filter(message: types.Message):
    async with AsyncSessionLocal() as session:
        await toggle_monobank_jar_payments(session, message.from_user.id)

    await send_filters_menu(message)


@router.message(StateFilter(AppMenu.p2p_filters), F.text == BTN_RESET_FILTERS)
async def reset_p2p_filters(message: types.Message):
    async with AsyncSessionLocal() as session:
        await reset_filters(session, message.from_user.id)

    await send_filters_menu(message, prefix="Фільтри скинуто.")


@router.callback_query(F.data == CB_FILTERS_MENU)
async def show_filters_menu_callback(callback: types.CallbackQuery):
    await callback.answer()
    await edit_filters_menu(callback)


@router.callback_query(F.data == CB_FILTERS_RESET)
async def reset_filters_callback(callback: types.CallbackQuery):
    async with AsyncSessionLocal() as session:
        settings = await reset_filters(session, callback.from_user.id)

    await callback.answer("Фільтри скинуто")
    await edit_filters_menu(callback, settings=settings, prefix="Фільтри скинуто.")


@router.callback_query(F.data.startswith(CB_FILTERS_SCREEN_PREFIX))
async def show_filter_screen_callback(callback: types.CallbackQuery):
    screen = callback.data[len(CB_FILTERS_SCREEN_PREFIX):]

    await callback.answer()
    await edit_filter_screen(callback, screen)


@router.callback_query(F.data.startswith(CB_FILTERS_PAY_PREFIX))
async def toggle_payment_method_callback(callback: types.CallbackQuery):
    category = callback.data[len(CB_FILTERS_PAY_PREFIX):]

    async with AsyncSessionLocal() as session:
        settings = await toggle_payment_category(session, callback.from_user.id, category)

    await callback.answer("Оновлено")
    await edit_filter_screen(
        callback,
        FILTER_SCREEN_PAYMENT_METHODS,
        settings=settings,
    )


@router.callback_query(F.data.startswith(CB_FILTERS_SET_PREFIX))
async def set_filter_value_callback(callback: types.CallbackQuery):
    field, raw_value = parse_set_callback(callback.data)

    if not field:
        await callback.answer("Не вдалося прочитати значення", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        settings = await apply_filter_value(
            session,
            callback.from_user.id,
            field,
            raw_value,
        )

    await callback.answer("Збережено")
    await edit_filter_screen(callback, field, settings=settings)


async def send_filters_menu(message: types.Message, prefix: str | None = None):
    async with AsyncSessionLocal() as session:
        settings = await get_filters(session, message.from_user.id)

    await message.answer(
        build_filters_menu_text(settings, prefix=prefix),
        reply_markup=p2p_filters_inline_kb(settings),
    )


async def send_p2p_pairs_menu(message: types.Message):
    async with AsyncSessionLocal() as session:
        service = P2PPairService(session)
        pairs = await service.list_available_pairs(message.from_user.id)

    await message.answer(
        build_p2p_pairs_text(pairs),
        reply_markup=p2p_pairs_inline_kb(pairs) if pairs else None,
    )


async def load_selected_p2p_pairs(telegram_id: int):
    async with AsyncSessionLocal() as session:
        service = P2PPairService(session)
        return await service.list_selected_pairs(telegram_id)


async def load_selected_statistics_pair(
    telegram_id: int,
    crypto_currency_id: int,
    fiat_currency_id: int,
):
    selected_pairs = await load_selected_p2p_pairs(telegram_id)

    return find_pair(selected_pairs, crypto_currency_id, fiat_currency_id)


async def resolve_statistics_pair(
    telegram_id: int,
    state: FSMContext,
    crypto_currency_id: int | None = None,
    fiat_currency_id: int | None = None,
):
    if crypto_currency_id and fiat_currency_id:
        pair = await load_selected_statistics_pair(
            telegram_id,
            crypto_currency_id,
            fiat_currency_id,
        )

        if pair:
            await set_statistics_pair(state, pair)

        return pair

    data = await state.get_data()
    stored_crypto_id = data.get("statistics_pair_crypto_currency_id")
    stored_fiat_id = data.get("statistics_pair_fiat_currency_id")

    if stored_crypto_id and stored_fiat_id:
        return await load_selected_statistics_pair(
            telegram_id,
            int(stored_crypto_id),
            int(stored_fiat_id),
        )

    selected_pairs = await load_selected_p2p_pairs(telegram_id)

    if len(selected_pairs) == 1:
        await set_statistics_pair(state, selected_pairs[0])
        return selected_pairs[0]

    return None


async def resolve_statistics_market(
    state: FSMContext,
    *,
    exchange: str | None = None,
    direction: str | None = None,
) -> tuple[str | None, str | None]:
    data = await state.get_data()
    selected_exchange = normalize_statistics_exchange(
        exchange or data.get("statistics_exchange")
    )
    selected_direction = normalize_statistics_direction(
        direction or data.get("statistics_direction")
    )

    if selected_exchange and selected_direction:
        await set_statistics_direction(state, selected_exchange, selected_direction)

    return selected_exchange, selected_direction


async def set_statistics_pair(state: FSMContext, pair):
    await state.set_state(AppMenu.statistics)
    await state.update_data(
        statistics_pair_crypto_currency_id=pair.crypto_currency_id,
        statistics_pair_fiat_currency_id=pair.fiat_currency_id,
        statistics_pair_crypto_code=pair.crypto_code,
        statistics_pair_fiat_code=pair.fiat_code,
        statistics_exchange=None,
        statistics_direction=None,
    )


async def set_statistics_exchange(state: FSMContext, exchange: str):
    await state.set_state(AppMenu.statistics)
    await state.update_data(
        statistics_exchange=exchange,
        statistics_direction=None,
    )


async def set_statistics_direction(
    state: FSMContext,
    exchange: str,
    direction: str,
):
    await state.set_state(AppMenu.statistics)
    await state.update_data(
        statistics_exchange=exchange,
        statistics_direction=direction,
    )


async def set_statistics_view_context(
    state: FSMContext,
    scope: str,
    period_type: str,
    selected_anchor: date | None,
):
    selected_anchor = normalize_statistics_period_anchor(period_type, selected_anchor)

    await state.set_state(AppMenu.statistics)
    await state.update_data(
        statistics_scope=scope,
        statistics_period_type=period_type,
        statistics_period_anchor=(
            selected_anchor.isoformat()
            if selected_anchor is not None
            else None
        ),
        statistics_waiting_period_type=None,
    )


async def get_statistics_period_anchor(
    state: FSMContext,
    *,
    period_type: str | None = None,
) -> date | None:
    data = await state.get_data()

    if period_type is not None and data.get("statistics_period_type") != period_type:
        return None

    raw_value = data.get("statistics_period_anchor") or data.get(
        "statistics_selected_date"
    )

    if not raw_value:
        return None

    try:
        return date.fromisoformat(str(raw_value))
    except ValueError:
        return None


async def clear_statistics_pair(state: FSMContext):
    await state.update_data(
        statistics_pair_crypto_currency_id=None,
        statistics_pair_fiat_currency_id=None,
        statistics_pair_crypto_code=None,
        statistics_pair_fiat_code=None,
        statistics_exchange=None,
        statistics_direction=None,
        statistics_scope=None,
        statistics_period_type=None,
        statistics_period_anchor=None,
        statistics_selected_date=None,
        statistics_waiting_period_type=None,
    )


async def send_statistics_exchange_choice_menu(message: types.Message):
    await message.answer(
        "<b>Статистика P2P</b>\n\n"
        "Оберіть біржу для графіка статистики.",
        reply_markup=statistics_exchange_choice_inline_kb(),
    )


async def edit_statistics_exchange_choice_menu(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    await clear_statistics_pair(state)
    await callback.answer()

    if callback.message:
        await safe_edit_callback_message(
            callback,
            "<b>Статистика P2P</b>\n\n"
            "Оберіть біржу для графіка статистики.",
            statistics_exchange_choice_inline_kb(),
        )


async def edit_statistics_pair_crypto_for_exchange(
    callback: types.CallbackQuery,
    state: FSMContext,
    exchange: str,
):
    selected_pairs = await load_selected_p2p_pairs(callback.from_user.id)

    if not selected_pairs:
        await callback.answer("Немає обраних P2P-пар", show_alert=True)
        return

    crypto_groups_count = count_unique_cryptos(selected_pairs)

    if crypto_groups_count == 1:
        await continue_statistics_after_crypto_selected(
            callback,
            state,
            exchange,
            selected_pairs[0].crypto_currency_id,
            selected_pairs=selected_pairs,
            crypto_was_auto_selected=True,
        )
        return

    await safe_edit_callback_message(
        callback,
        build_statistics_pair_cryptos_text(selected_pairs),
        statistics_pair_cryptos_inline_kb(
            selected_pairs,
            back_callback=f"{CB_STATS_EXCHANGE_PREFIX}back",
        ),
    )


async def continue_statistics_after_crypto_selected(
    callback: types.CallbackQuery,
    state: FSMContext,
    exchange: str,
    crypto_currency_id: int,
    *,
    selected_pairs=None,
    crypto_was_auto_selected: bool = False,
):
    selected_pairs = selected_pairs or await load_selected_p2p_pairs(callback.from_user.id)
    crypto_pairs = filter_pairs_by_crypto(selected_pairs, crypto_currency_id)

    if not crypto_pairs:
        await callback.answer("Для цього стейбла немає обраних фіатів", show_alert=True)
        return

    if len(crypto_pairs) == 1:
        pair = crypto_pairs[0]
        await set_statistics_pair(state, pair)
        await set_statistics_exchange(state, exchange)
        await callback.answer(pair.label)

        if callback.message:
            await replace_statistics_direction_message(callback.message, pair, exchange)

        return

    await callback.answer(crypto_pairs[0].crypto_code)

    if callback.message:
        await safe_edit_callback_message(
            callback,
            build_statistics_pair_fiats_text(selected_pairs, crypto_currency_id),
            statistics_pair_fiats_inline_kb(
                selected_pairs,
                crypto_currency_id,
                back_callback=(
                    f"{CB_STATS_EXCHANGE_PREFIX}back"
                    if crypto_was_auto_selected
                    else CB_STATS_PAIR_BACK
                ),
            ),
        )


async def send_statistics_pair_crypto_menu(
    message: types.Message,
    state: FSMContext,
):
    selected_pairs = await load_selected_p2p_pairs(message.from_user.id)

    if not selected_pairs:
        await message.answer(
            "<b>Статистика P2P</b>\n\n"
            "Поки немає обраних P2P-пар. Відкрийте Особистий кабінет -> Мої P2P пари "
            "і оберіть хоча б одну пару."
        )
        return

    if len(selected_pairs) == 1:
        pair = selected_pairs[0]
        await set_statistics_pair(state, pair)
        await send_statistics_exchange_menu(message, pair)
        return

    await message.answer(
        build_statistics_pair_cryptos_text(selected_pairs),
        reply_markup=statistics_pair_cryptos_inline_kb(selected_pairs),
    )


async def edit_statistics_pair_crypto_menu(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    selected_pairs = await load_selected_p2p_pairs(callback.from_user.id)

    if not selected_pairs:
        await clear_statistics_pair(state)
        await callback.answer("Немає обраних P2P-пар", show_alert=True)
        return

    await callback.answer()
    await clear_statistics_pair(state)

    if len(selected_pairs) == 1:
        pair = selected_pairs[0]
        await set_statistics_pair(state, pair)

        if callback.message:
            await replace_statistics_exchange_message(callback.message, pair)

        return

    if callback.message:
        await safe_edit_callback_message(
            callback,
            build_statistics_pair_cryptos_text(selected_pairs),
            statistics_pair_cryptos_inline_kb(selected_pairs),
        )


async def send_statistics_exchange_menu(message: types.Message, pair):
    await message.answer(
        "<b>Статистика P2P</b>\n\n"
        f"Пара: <b>{escape(pair.label)}</b>\n\n"
        "Оберіть біржу для графіка статистики.",
        reply_markup=statistics_exchange_inline_kb(pair),
    )


async def replace_statistics_exchange_message(message: types.Message, pair):
    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    await send_statistics_exchange_menu(message, pair)


async def send_statistics_direction_menu(message: types.Message, pair, exchange: str):
    await message.answer(
        "<b>Статистика P2P</b>\n\n"
        f"Пара: <b>{escape(pair.label)}</b>\n"
        f"Біржа: <b>{escape(format_statistics_exchange_label(exchange))}</b>\n\n"
        "Оберіть напрямок.",
        reply_markup=statistics_direction_inline_kb(pair, exchange),
    )


async def replace_statistics_direction_message(
    message: types.Message,
    pair,
    exchange: str,
):
    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    await send_statistics_direction_menu(message, pair, exchange)


async def send_statistics_scope_menu(
    message: types.Message,
    pair,
    exchange: str,
    direction: str,
):
    await message.answer(
        "<b>Статистика P2P</b>\n\n"
        f"Пара: <b>{escape(pair.label)}</b>\n"
        f"Біржа: <b>{escape(format_statistics_exchange_label(exchange))}</b>\n"
        f"Напрямок: <b>{escape(format_statistics_direction_label(direction))}</b>\n\n"
        "Оберіть тип статистики:\n"
        "• <b>Загальна</b> — формується автоматично за налаштуваннями адмінки.\n"
        "• <b>За моїми фільтрами</b> — збирається зі сканів усіх користувачів з таким самим набором фільтрів.",
        reply_markup=statistics_scope_inline_kb(pair, exchange, direction),
    )


async def replace_statistics_scope_message(
    message: types.Message,
    state: FSMContext,
    *,
    pair=None,
    exchange: str | None = None,
    direction: str | None = None,
    telegram_id: int | None = None,
):
    if pair is None:
        pair = (
            await resolve_statistics_pair(telegram_id, state)
            if telegram_id is not None
            else None
        )

    if pair is None:
        return

    exchange, direction = await resolve_statistics_market(
        state,
        exchange=exchange,
        direction=direction,
    )

    if not exchange or not direction:
        return

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    await send_statistics_scope_menu(message, pair, exchange, direction)


async def send_statistics_menu(
    message: types.Message,
    period_type: str,
    scope: str = STAT_SCOPE_GLOBAL,
    pair=None,
    exchange: str | None = None,
    direction: str | None = None,
    selected_anchor: date | None = None,
):
    if pair is None or not exchange or not direction:
        return

    timezone_name = await get_user_timezone_name(message.from_user.id)
    selected_anchor = selected_anchor or current_statistics_period_anchor(
        period_type,
        timezone_name,
    )

    stats = await load_statistics_for_user(
        message.from_user.id,
        scope,
        period_type,
        pair,
        exchange,
        direction,
        selected_anchor=selected_anchor,
        timezone_name=timezone_name,
    )

    await send_statistics_message(
        message,
        pair,
        exchange,
        direction,
        stats,
        period_type,
        scope,
        selected_anchor=selected_anchor,
        timezone_name=timezone_name,
    )


async def load_statistics_for_user(
    telegram_id: int,
    scope: str,
    period_type: str,
    pair,
    exchange: str,
    direction: str,
    *,
    selected_anchor: date | None = None,
    timezone_name: str | None = None,
):
    async with AsyncSessionLocal() as session:
        timezone_name = timezone_name or await get_user_timezone_name(
            telegram_id,
            session=session,
        )
        filter_hashes = None
        query_pairs = [pair]
        exchange_code = format_statistics_exchange_code(exchange)
        sides = get_statistics_sides(exchange, direction)
        period_started_from = None
        period_started_to = None
        max_periods = STATISTICS_HISTORY_PERIODS

        selected_range = get_statistics_period_range(period_type, selected_anchor)

        if selected_range is not None:
            period_started_from, period_started_to = display_dates_to_utc_naive_range(
                selected_range[0],
                selected_range[1],
                timezone_name=timezone_name,
            )
            max_periods = get_statistics_range_max_periods(period_type)

        closed_period_started_to = get_closed_statistics_period_started_to(
            period_type,
            timezone_name=timezone_name,
        )
        if closed_period_started_to is not None:
            period_started_to = min_date_or_none(
                period_started_to,
                closed_period_started_to,
            )

        if scope == STAT_SCOPE_FILTER:
            settings = await get_filters(session, telegram_id)
            filter_hashes = await build_user_statistics_filter_hashes(
                session,
                telegram_id,
                query_pairs,
                settings,
                exchange=exchange,
                direction=direction,
            )
        else:
            filter_hashes = await build_global_statistics_filter_hashes(
                session,
                query_pairs,
                exchange=exchange,
                direction=direction,
            )

        stats = await P2PStatisticsService(session).list_history_for_pairs(
            query_pairs,
            period_type=period_type,
            max_periods=max_periods,
            scope=scope,
            filter_hashes=filter_hashes,
            exchange_codes=[exchange_code],
            sides=sides,
            period_started_from=period_started_from,
            period_started_to=period_started_to,
        )

    return stats


def get_closed_statistics_period_started_to(
    period_type: str,
    *,
    timezone_name: str | None = None,
) -> datetime | None:
    if period_type == STAT_PERIOD_HOUR:
        return None

    today = display_today(timezone_name)

    if period_type == STAT_PERIOD_DAY:
        started_on = today
    elif period_type == STAT_PERIOD_WEEK:
        started_on = today - timedelta(days=today.weekday())
    elif period_type == STAT_PERIOD_MONTH:
        started_on = date(today.year, today.month, 1)
    elif period_type == STAT_PERIOD_YEAR:
        started_on = date(today.year, 1, 1)
    else:
        return None

    return display_dates_to_utc_naive_range(
        started_on,
        started_on + timedelta(days=1),
        timezone_name=timezone_name,
    )[0]


def min_date_or_none(
    first_value: datetime | None,
    second_value: datetime | None,
) -> datetime | None:
    if first_value is None:
        return second_value

    if second_value is None:
        return first_value

    return min(first_value, second_value)


async def get_user_timezone_name(
    telegram_id: int,
    *,
    session=None,
) -> str | None:
    if session is not None:
        user = await UserService(session).get_user_by_telegram_id(telegram_id)
        return user.location_timezone if user else None

    async with AsyncSessionLocal() as session:
        user = await UserService(session).get_user_by_telegram_id(telegram_id)
        return user.location_timezone if user else None


async def build_global_statistics_filter_hashes(
    session,
    pairs=None,
    *,
    exchange: str | None = None,
    direction: str | None = None,
) -> list[str]:
    service = StatisticsSettingsService(session)
    settings_model = await service.get_or_create_settings()

    if not settings_model.is_enabled:
        return []

    settings = await service.get_filter_settings()
    hashes = set()

    if pairs is None:
        crypto_currencies = await service.list_crypto_currencies()
        fiat_currencies = await service.list_fiat_currencies()
        pairs = [
            P2PUserPair(
                crypto_currency_id=crypto.id,
                fiat_currency_id=fiat.id,
                crypto_code=crypto.code,
                fiat_code=fiat.code,
                is_selected=True,
            )
            for crypto in crypto_currencies
            for fiat in fiat_currencies
        ]

    selected_exchange = normalize_statistics_exchange(exchange)
    selected_direction = normalize_statistics_direction(direction)
    exchange_codes = get_global_statistics_exchange_codes(settings_model)

    if selected_exchange:
        exchange_code = format_statistics_exchange_code(selected_exchange)
        exchange_codes = [
            code
            for code in exchange_codes
            if code == exchange_code
        ]

    for pair in pairs:
        payment_methods = await service.list_selected_methods_for_fiat_code(
            pair.fiat_code,
        )

        for exchange_code in exchange_codes:
            sides = get_statistics_sides(exchange_code, selected_direction) if (
                selected_direction
            ) else get_global_statistics_sides(exchange_code, settings_model)

            for side in sides:
                hashes.add(
                    build_statistics_filter_hash(
                        exchange_code=exchange_code,
                        pair=pair,
                        side=side,
                        settings=settings,
                        payment_methods=payment_methods,
                    )
                )

    return sorted(hashes)


async def build_user_statistics_filter_hashes(
    session,
    telegram_id: int,
    selected_pairs,
    settings,
    *,
    exchange: str | None = None,
    direction: str | None = None,
) -> list[str]:
    service = PaymentMethodService(session)
    methods_by_fiat = {}
    hashes = set()
    selected_exchange = normalize_statistics_exchange(exchange)
    selected_direction = normalize_statistics_direction(direction)
    exchange_codes = (
        [format_statistics_exchange_code(selected_exchange)]
        if selected_exchange
        else ["BINANCE", "OKX"]
    )

    for pair in selected_pairs:
        if pair.fiat_code not in methods_by_fiat:
            methods_by_fiat[pair.fiat_code] = await service.list_user_selected_methods_for_fiat_code(
                telegram_id,
                pair.fiat_code,
            )

        payment_methods = methods_by_fiat[pair.fiat_code]

        for exchange_code in exchange_codes:
            sides = (
                get_statistics_sides(exchange_code, selected_direction)
                if selected_direction
                else ["BUY", "SELL"]
            )

            for side in sides:
                hashes.add(
                    build_statistics_filter_hash(
                        exchange_code=exchange_code,
                        pair=pair,
                        side=side,
                        settings=settings,
                        payment_methods=payment_methods,
                    )
                )

    return sorted(hashes)


def get_global_statistics_exchange_codes(settings_model) -> list[str]:
    codes = []

    if settings_model.scan_binance:
        codes.append("BINANCE")

    if settings_model.scan_okx:
        codes.append("OKX")

    return codes


def get_global_statistics_sides(exchange_code: str, settings_model) -> list[str]:
    if exchange_code == "OKX":
        sides = []

        if settings_model.scan_buy:
            sides.append("sell")

        if settings_model.scan_sell:
            sides.append("buy")

        return sides

    sides = []

    if settings_model.scan_buy:
        sides.append("BUY")

    if settings_model.scan_sell:
        sides.append("SELL")

    return sides


async def send_statistics_message(
    message: types.Message,
    pair,
    exchange: str,
    direction: str,
    stats,
    period_type: str,
    scope: str,
    selected_anchor: date | None = None,
    timezone_name: str | None = None,
):
    reply_markup = statistics_period_inline_kb(
        period_type,
        scope,
        pair,
        exchange,
        direction,
        selected_period_label=format_statistics_period_anchor(period_type, selected_anchor),
    )

    if not pair or not stats:
        await message.answer(
            build_statistics_text(
                pair,
                exchange,
                direction,
                stats,
                period_type,
                scope,
                selected_anchor=selected_anchor,
                timezone_name=timezone_name,
            ),
            reply_markup=reply_markup,
        )
        return

    try:
        chart = render_p2p_statistics_chart(
            stats,
            period_type,
            periods=build_statistics_chart_periods(
                period_type,
                selected_anchor,
                timezone_name=timezone_name,
            ),
            timezone_name=timezone_name,
        )
    except RuntimeError as error:
        await message.answer(
            f"{build_statistics_text(pair, exchange, direction, stats, period_type, scope, selected_anchor=selected_anchor, timezone_name=timezone_name)}\n\n{escape(str(error))}",
            reply_markup=reply_markup,
        )
        return

    caption = (
        f"{format_statistics_scope_title(scope)} · {escape(format_statistics_market_label(pair, exchange, direction))} · "
        f"{escape(format_statistics_period_label(period_type, selected_anchor))}\n"
        f"{build_p2p_statistics_caption(stats, period_type)}"
    )

    await message.answer_photo(
        BufferedInputFile(chart, filename=f"p2p_statistics_{period_type}.png"),
        caption=caption,
        reply_markup=reply_markup,
    )

    await send_statistics_values_message(
        message,
        stats,
        period_type,
        timezone_name=timezone_name,
    )


async def replace_statistics_message(
    message: types.Message,
    pair,
    exchange: str,
    direction: str,
    stats,
    period_type: str,
    scope: str,
    selected_anchor: date | None = None,
    timezone_name: str | None = None,
):
    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    await send_statistics_message(
        message,
        pair,
        exchange,
        direction,
        stats,
        period_type,
        scope,
        selected_anchor=selected_anchor,
        timezone_name=timezone_name,
    )


async def send_statistics_values_message(
    message: types.Message,
    stats,
    period_type: str,
    *,
    timezone_name: str | None = None,
):
    for part in build_statistics_values_messages(
        stats,
        period_type,
        timezone_name=timezone_name,
    ):
        await message.answer(part)


def build_statistics_values_messages(
    stats,
    period_type: str,
    *,
    timezone_name: str | None = None,
) -> list[str]:
    if not stats:
        return []

    fiat_code = escape(str(getattr(stats[0], "fiat_code", "") or ""))
    header = f"\n\n<b>Значення:</b> {get_statistics_metric_label(period_type)}"
    if fiat_code:
        header = f"{header}, {fiat_code}"

    header = header.strip()
    rows = build_statistics_known_value_rows(
        stats,
        period_type,
        timezone_name=timezone_name,
    )
    messages = []
    current = header

    for row in rows:
        candidate = f"{current}\n{row}"

        if len(candidate) <= TELEGRAM_MESSAGE_LIMIT:
            current = candidate
            continue

        if current != header:
            messages.append(current)
            current = f"{header}\n{row}"
            continue

        messages.extend(split_long_message(row, TELEGRAM_MESSAGE_LIMIT))
        current = header

    if current != header or not messages:
        messages.append(current)

    if len(messages) <= 1:
        return messages

    return [
        f"{message_text}\n\n<i>Частина {index}/{len(messages)}</i>"
        for index, message_text in enumerate(messages, start=1)
    ]


def build_statistics_known_value_rows(
    stats,
    period_type: str,
    *,
    timezone_name: str | None = None,
) -> list[str]:
    items = sorted(
        stats,
        key=lambda stat: (
            stat.period_started_at,
            stat.exchange_code,
            stat.pair_label,
            get_stat_side_order(stat.side, stat.exchange_code),
        ),
    )
    show_series = len(
        {
            (
                getattr(item, "exchange_code", None),
                getattr(item, "pair_label", None),
                getattr(item, "side", None),
            )
            for item in stats
        }
    ) > 1
    show_series_context = len(
        {
            (
                getattr(item, "exchange_code", None),
                getattr(item, "pair_label", None),
            )
            for item in stats
        }
    ) > 1

    if not show_series:
        return [
            (
                f"{format_statistics_value_period(item.period_started_at, period_type, timezone_name=timezone_name)}: "
                f"<b>{format_stat_price(get_statistics_metric_value(item, period_type))}</b>"
            )
            for item in items
        ]

    grouped_by_period = {}

    for item in items:
        grouped_by_period.setdefault(item.period_started_at, []).append(item)

    rows = []

    for period_started_at, period_items in grouped_by_period.items():
        prefix = format_statistics_value_period(
            period_started_at,
            period_type,
            timezone_name=timezone_name,
        )
        values = [
            format_statistics_known_value_item(
                item,
                period_type,
                show_context=show_series_context,
            )
            for item in period_items
        ]

        rows.append(
            f"{prefix}: "
            f"{' · '.join(values)}"
        )

    return rows


def format_statistics_known_value_item(
    item,
    period_type: str,
    *,
    show_context: bool = False,
) -> str:
    label = escape(format_stat_side(item.side, item.exchange_code))

    if show_context:
        label = (
            f"{escape(str(item.exchange_code))} · "
            f"{escape(str(item.pair_label))} · "
            f"{label}"
        )

    return (
        f"{label} "
        f"<b>{format_stat_price(get_statistics_metric_value(item, period_type))}</b>"
    )


async def send_user_payment_fiats_menu(message: types.Message):
    async with AsyncSessionLocal() as session:
        service = PaymentMethodService(session)
        fiat_currencies = await service.list_fiat_currencies()
        selected_counts = await get_user_payment_selected_counts(
            service,
            message.from_user.id,
            fiat_currencies,
        )

    await message.answer(
        build_user_payment_fiats_text(fiat_currencies),
        reply_markup=(
            user_payment_fiats_inline_kb(fiat_currencies, selected_counts)
            if fiat_currencies
            else None
        ),
    )


async def edit_user_payment_fiats_menu(callback: types.CallbackQuery):
    async with AsyncSessionLocal() as session:
        service = PaymentMethodService(session)
        fiat_currencies = await service.list_fiat_currencies()
        selected_counts = await get_user_payment_selected_counts(
            service,
            callback.from_user.id,
            fiat_currencies,
        )

    await safe_edit_callback_message(
        callback,
        build_user_payment_fiats_text(fiat_currencies),
        (
            user_payment_fiats_inline_kb(fiat_currencies, selected_counts)
            if fiat_currencies
            else None
        ),
    )


async def edit_user_payment_methods_for_fiat(
    callback: types.CallbackQuery,
    fiat_currency_id: int,
):
    async with AsyncSessionLocal() as session:
        service = PaymentMethodService(session)
        methods = await service.list_user_methods_for_fiat(
            callback.from_user.id,
            fiat_currency_id,
        )

    await safe_edit_callback_message(
        callback,
        build_user_payment_methods_text(methods),
        user_payment_methods_inline_kb(methods),
    )


async def get_user_payment_selected_counts(
    service: PaymentMethodService,
    telegram_id: int,
    fiat_currencies,
) -> dict[int, int]:
    counts = {}

    for fiat in fiat_currencies:
        methods = await service.list_user_methods_for_fiat(telegram_id, fiat.id)
        counts[fiat.id] = sum(1 for method in methods if method.is_selected)

    return counts


async def edit_filters_menu(
    callback: types.CallbackQuery,
    *,
    settings=None,
    prefix: str | None = None,
):
    if settings is None:
        async with AsyncSessionLocal() as session:
            settings = await get_filters(session, callback.from_user.id)

    await safe_edit_callback_message(
        callback,
        build_filters_menu_text(settings, prefix=prefix),
        p2p_filters_inline_kb(settings),
    )


async def edit_filter_screen(
    callback: types.CallbackQuery,
    screen: str,
    *,
    settings=None,
):
    if settings is None:
        async with AsyncSessionLocal() as session:
            settings = await get_filters(session, callback.from_user.id)

    await safe_edit_callback_message(
        callback,
        build_filter_screen_text(screen),
        p2p_filter_values_inline_kb(settings, screen),
    )


async def safe_edit_callback_message(
    callback: types.CallbackQuery,
    text: str,
    reply_markup,
):
    if not callback.message:
        return

    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error).lower():
            raise


def build_filters_menu_text(settings, prefix: str | None = None) -> str:
    title = "Фільтри P2P"

    if prefix:
        title = f"{prefix}\n\n{title}"

    return (
        f"<b>{title}</b>\n\n"
        f"{filters_summary(settings)}\n\n"
        "Оберіть параметр нижче."
    )


def build_filter_screen_text(screen: str) -> str:
    title, hint = FILTER_SCREEN_TEXTS.get(
        screen,
        (
            "Фільтр P2P",
            "Оберіть потрібне значення.",
        ),
    )

    return f"<b>{title}</b>\n\n{hint}"


def parse_set_callback(callback_data: str) -> tuple[str | None, str | None]:
    parts = callback_data.split(":")

    if len(parts) != 4:
        return None, None

    return parts[2], parts[3]


def parse_pair_callback(callback_data: str) -> tuple[int | None, int | None]:
    payload = callback_data[len(CB_P2P_PAIR_TOGGLE_PREFIX):]
    parts = payload.split(":")

    if len(parts) != 2:
        return None, None

    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None, None


def parse_pair_crypto_callback(callback_data: str) -> int | None:
    payload = callback_data[len(CB_P2P_PAIR_CRYPTO_PREFIX):]

    try:
        return int(payload)
    except ValueError:
        return None


def parse_user_payment_fiat_callback(callback_data: str) -> int | None:
    payload = callback_data[len(CB_USER_PAYMENT_FIAT_PREFIX):]

    try:
        return int(payload)
    except ValueError:
        return None


def parse_user_payment_toggle_callback(callback_data: str) -> int | None:
    payload = callback_data[len(CB_USER_PAYMENT_TOGGLE_PREFIX):]

    try:
        return int(payload)
    except ValueError:
        return None


def parse_statistics_period_callback(
    callback_data: str,
) -> tuple[str, str | None, str | None, str | None, int | None, int | None]:
    payload = callback_data[len(CB_STATS_PERIOD_PREFIX):]
    parts = payload.split(":")

    if len(parts) == 1:
        return STAT_SCOPE_GLOBAL, parts[0], None, None, None, None

    if len(parts) == 2:
        return parts[0], parts[1], None, None, None, None

    if len(parts) == 4:
        try:
            return parts[0], parts[1], None, None, int(parts[2]), int(parts[3])
        except ValueError:
            return parts[0], parts[1], None, None, None, None

    if len(parts) == 6:
        exchange = normalize_statistics_exchange(parts[2])
        direction = normalize_statistics_direction(parts[3])

        try:
            return parts[0], parts[1], exchange, direction, int(parts[4]), int(parts[5])
        except ValueError:
            return parts[0], parts[1], exchange, direction, None, None

    return "", None, None, None, None, None


def parse_statistics_period_input(value: str, period_type: str) -> date | None:
    text = str(value or "").strip()

    if period_type == STAT_PERIOD_HOUR:
        return normalize_statistics_period_anchor(
            period_type,
            parse_statistics_date_text(text),
        )

    if period_type == STAT_PERIOD_DAY:
        return normalize_statistics_period_anchor(
            period_type,
            parse_statistics_month_text(text) or parse_statistics_date_text(text),
        )

    if period_type in (STAT_PERIOD_WEEK, STAT_PERIOD_MONTH, STAT_PERIOD_YEAR):
        return normalize_statistics_period_anchor(
            period_type,
            parse_statistics_year_text(text)
            or parse_statistics_month_text(text)
            or parse_statistics_date_text(text),
        )

    return None


def parse_statistics_date_text(value: str) -> date | None:
    formats = ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d")

    for date_format in formats:
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue

    return None


def parse_statistics_month_text(value: str) -> date | None:
    formats = ("%m.%Y", "%m.%y", "%Y-%m")

    for date_format in formats:
        try:
            parsed = datetime.strptime(value, date_format).date()
            return date(parsed.year, parsed.month, 1)
        except ValueError:
            continue

    return None


def parse_statistics_year_text(value: str) -> date | None:
    try:
        parsed_year = int(str(value).strip())
    except ValueError:
        return None

    if parsed_year < 2000 or parsed_year > 2100:
        return None

    return date(parsed_year, 1, 1)


def resolve_statistics_period_action(
    period_type: str,
    action: str,
    selected_anchor: date | None,
    *,
    timezone_name: str | None = None,
) -> date | None:
    base_anchor = normalize_statistics_period_anchor(
        period_type,
        selected_anchor,
    ) or current_statistics_period_anchor(period_type, timezone_name)

    if action == "prev":
        return shift_statistics_period_anchor(period_type, base_anchor, -1)

    if action == "next":
        return shift_statistics_period_anchor(period_type, base_anchor, 1)

    if action == "today":
        return current_statistics_period_anchor(period_type, timezone_name)

    if action == "clear":
        return current_statistics_period_anchor(period_type, timezone_name)

    return base_anchor


def current_statistics_period_anchor(
    period_type: str,
    timezone_name: str | None = None,
) -> date:
    today = display_today(timezone_name)

    return normalize_statistics_period_anchor(period_type, today) or today


def shift_statistics_period_anchor(
    period_type: str,
    value: date,
    amount: int,
) -> date:
    if period_type == STAT_PERIOD_HOUR:
        return value + timedelta(days=amount)

    if period_type == STAT_PERIOD_DAY:
        return add_months(value, amount)

    if period_type in (STAT_PERIOD_WEEK, STAT_PERIOD_MONTH):
        return date(value.year + amount, 1, 1)

    if period_type == STAT_PERIOD_YEAR:
        return date(value.year + amount * 10, 1, 1)

    return value


def normalize_statistics_period_anchor(
    period_type: str,
    value: date | None,
) -> date | None:
    if value is None:
        return None

    if period_type == STAT_PERIOD_HOUR:
        return value

    if period_type == STAT_PERIOD_DAY:
        return date(value.year, value.month, 1)

    if period_type in (STAT_PERIOD_WEEK, STAT_PERIOD_MONTH):
        return date(value.year, 1, 1)

    if period_type == STAT_PERIOD_YEAR:
        return date((value.year // 10) * 10, 1, 1)

    return value


def add_months(value: date, amount: int) -> date:
    month_index = value.month - 1 + amount
    year = value.year + month_index // 12
    month = month_index % 12 + 1

    return date(year, month, 1)


def is_future_statistics_anchor(
    period_type: str,
    value: date | None,
    *,
    timezone_name: str | None = None,
) -> bool:
    if value is None:
        return False

    current_anchor = current_statistics_period_anchor(period_type, timezone_name)
    normalized_value = normalize_statistics_period_anchor(period_type, value)

    return normalized_value is not None and normalized_value > current_anchor


def get_statistics_period_range(
    period_type: str,
    selected_anchor: date | None,
) -> tuple[date, date] | None:
    anchor = normalize_statistics_period_anchor(period_type, selected_anchor)

    if anchor is None:
        return None

    if period_type == STAT_PERIOD_HOUR:
        return anchor, anchor + timedelta(days=1)

    if period_type == STAT_PERIOD_DAY:
        return anchor, add_months(anchor, 1)

    if period_type == STAT_PERIOD_WEEK:
        started_on = anchor - timedelta(days=anchor.weekday())
        return started_on, date(anchor.year + 1, 1, 1)

    if period_type == STAT_PERIOD_MONTH:
        return anchor, date(anchor.year + 1, 1, 1)

    if period_type == STAT_PERIOD_YEAR:
        return anchor, date(anchor.year + 10, 1, 1)

    return None


def get_statistics_range_max_periods(period_type: str) -> int:
    values = {
        STAT_PERIOD_HOUR: STATISTICS_HOURLY_DATE_PERIODS,
        STAT_PERIOD_DAY: STATISTICS_DAILY_MONTH_PERIODS,
        STAT_PERIOD_WEEK: STATISTICS_WEEKLY_YEAR_PERIODS,
        STAT_PERIOD_MONTH: STATISTICS_MONTHLY_YEAR_PERIODS,
        STAT_PERIOD_YEAR: STATISTICS_YEARLY_DECADE_PERIODS,
    }

    return values.get(period_type, STATISTICS_HISTORY_PERIODS)


def build_statistics_chart_periods(
    period_type: str,
    selected_anchor: date | None,
    *,
    timezone_name: str | None = None,
) -> list[datetime] | None:
    selected_range = get_statistics_period_range(period_type, selected_anchor)

    if selected_range is None:
        return None

    started_on, ended_before = selected_range

    if period_type == STAT_PERIOD_HOUR:
        started_at, ended_at = display_dates_to_utc_naive_range(
            started_on,
            ended_before,
            timezone_name=timezone_name,
        )
        return list_datetime_range(started_at, ended_at, timedelta(hours=1))

    if period_type == STAT_PERIOD_DAY:
        return [
            datetime(day.year, day.month, day.day)
            for day in iter_date_range(started_on, ended_before, timedelta(days=1))
        ]

    if period_type == STAT_PERIOD_WEEK:
        return [
            datetime(day.year, day.month, day.day)
            for day in iter_date_range(started_on, ended_before, timedelta(days=7))
        ]

    if period_type == STAT_PERIOD_MONTH:
        periods = []
        current = date(started_on.year, started_on.month, 1)

        while current < ended_before:
            periods.append(datetime(current.year, current.month, 1))
            current = add_months(current, 1)

        return periods

    if period_type == STAT_PERIOD_YEAR:
        return [
            datetime(year, 1, 1)
            for year in range(started_on.year, ended_before.year)
        ]

    return None


def iter_date_range(started_on: date, ended_before: date, step: timedelta):
    current = started_on

    while current < ended_before:
        yield current
        current += step


def list_datetime_range(
    started_at: datetime,
    ended_before: datetime,
    step: timedelta,
) -> list[datetime]:
    periods = []
    current = started_at

    while current < ended_before:
        periods.append(current)
        current += step

    return periods


def format_statistics_period_anchor(
    period_type: str,
    value: date | None,
) -> str | None:
    value = normalize_statistics_period_anchor(period_type, value)

    if value is None:
        return None

    if period_type == STAT_PERIOD_HOUR:
        return value.strftime("%d.%m.%Y")

    if period_type == STAT_PERIOD_DAY:
        return value.strftime("%m.%Y")

    if period_type in (STAT_PERIOD_WEEK, STAT_PERIOD_MONTH):
        return value.strftime("%Y")

    if period_type == STAT_PERIOD_YEAR:
        return f"{value.year}-{value.year + 9}"

    return value.isoformat()


def format_statistics_period_answer(period_type: str, value: date | None) -> str:
    return format_statistics_period_anchor(period_type, value) or "Останні періоди"


def build_statistics_period_input_prompt(period_type: str) -> str:
    examples = {
        STAT_PERIOD_HOUR: (
            "Введіть дату для погодинної статистики у форматі <b>ДД.ММ.РРРР</b>.\n"
            "Наприклад: <code>04.06.2026</code>"
        ),
        STAT_PERIOD_DAY: (
            "Введіть місяць для денної статистики у форматі <b>ММ.РРРР</b>.\n"
            "Наприклад: <code>06.2026</code>"
        ),
        STAT_PERIOD_WEEK: (
            "Введіть рік для тижневої статистики у форматі <b>РРРР</b>.\n"
            "Наприклад: <code>2026</code>"
        ),
        STAT_PERIOD_MONTH: (
            "Введіть рік для місячної статистики у форматі <b>РРРР</b>.\n"
            "Наприклад: <code>2026</code>"
        ),
        STAT_PERIOD_YEAR: (
            "Введіть будь-який рік потрібного десятиліття у форматі <b>РРРР</b>.\n"
            "Наприклад: <code>2026</code> покаже 2020-2029."
        ),
    }

    return examples.get(period_type, examples[STAT_PERIOD_HOUR])


def build_statistics_period_input_error(period_type: str) -> str:
    examples = {
        STAT_PERIOD_HOUR: "Не вдалося прочитати дату. Приклад: <code>04.06.2026</code>.",
        STAT_PERIOD_DAY: "Не вдалося прочитати місяць. Приклад: <code>06.2026</code>.",
        STAT_PERIOD_WEEK: "Не вдалося прочитати рік. Приклад: <code>2026</code>.",
        STAT_PERIOD_MONTH: "Не вдалося прочитати рік. Приклад: <code>2026</code>.",
        STAT_PERIOD_YEAR: "Не вдалося прочитати рік. Приклад: <code>2026</code>.",
    }

    return examples.get(period_type, examples[STAT_PERIOD_HOUR])


def parse_statistics_scope_callback(
    callback_data: str,
) -> tuple[str, str | None, str | None, int | None, int | None]:
    payload = callback_data[len(CB_STATS_SCOPE_PREFIX):]
    parts = payload.split(":")

    if len(parts) == 1:
        return parts[0], None, None, None, None

    if len(parts) == 3:
        try:
            return parts[0], None, None, int(parts[1]), int(parts[2])
        except ValueError:
            return parts[0], None, None, None, None

    if len(parts) == 5:
        exchange = normalize_statistics_exchange(parts[1])
        direction = normalize_statistics_direction(parts[2])

        try:
            return parts[0], exchange, direction, int(parts[3]), int(parts[4])
        except ValueError:
            return parts[0], exchange, direction, None, None

    return "", None, None, None, None


def parse_statistics_exchange_callback(
    callback_data: str,
) -> tuple[str | None, int | None, int | None]:
    payload = callback_data[len(CB_STATS_EXCHANGE_PREFIX):]
    parts = payload.split(":")

    exchange = normalize_statistics_exchange(parts[0])

    if len(parts) == 1:
        return exchange, None, None

    if len(parts) != 3:
        return exchange, None, None

    try:
        return exchange, int(parts[1]), int(parts[2])
    except ValueError:
        return exchange, None, None


def parse_statistics_direction_callback(
    callback_data: str,
) -> tuple[str | None, str | None, int | None, int | None]:
    payload = callback_data[len(CB_STATS_DIRECTION_PREFIX):]
    parts = payload.split(":")

    if len(parts) != 4:
        return None, None, None, None

    exchange = normalize_statistics_exchange(parts[0])
    direction = normalize_statistics_direction(parts[1])

    try:
        return exchange, direction, int(parts[2]), int(parts[3])
    except ValueError:
        return exchange, direction, None, None


def parse_statistics_pair_crypto_callback(callback_data: str) -> int | None:
    payload = callback_data[len(CB_STATS_PAIR_CRYPTO_PREFIX):]

    try:
        return int(payload)
    except ValueError:
        return None


def parse_statistics_pair_select_callback(
    callback_data: str,
) -> tuple[int | None, int | None]:
    payload = callback_data[len(CB_STATS_PAIR_SELECT_PREFIX):]
    parts = payload.split(":")

    if len(parts) != 2:
        return None, None

    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None, None


def is_supported_statistics_scope(scope: str) -> bool:
    return scope in {STAT_SCOPE_GLOBAL, STAT_SCOPE_FILTER}


def format_statistics_scope_title(scope: str) -> str:
    if scope == STAT_SCOPE_FILTER:
        return "🎯 Статистика за моїми фільтрами"

    return "🌍 Загальна статистика"


def normalize_statistics_exchange(exchange: str | None) -> str | None:
    if not exchange:
        return None

    normalized = str(exchange).lower()

    return normalized if normalized in STATISTICS_EXCHANGES else None


def normalize_statistics_direction(direction: str | None) -> str | None:
    if not direction:
        return None

    normalized = str(direction).lower()

    return normalized if normalized in STATISTICS_DIRECTIONS else None


def format_statistics_exchange_code(exchange: str | None) -> str:
    normalized = normalize_statistics_exchange(exchange)

    return str(normalized or exchange or "").upper()


def format_statistics_exchange_label(exchange: str | None) -> str:
    normalized = normalize_statistics_exchange(exchange)

    return STATISTICS_EXCHANGE_LABELS.get(normalized, str(exchange or "невідомо"))


def format_statistics_direction_label(direction: str | None) -> str:
    normalized = normalize_statistics_direction(direction)

    return STATISTICS_DIRECTION_LABELS.get(normalized, str(direction or "невідомо"))


def format_statistics_period_label(
    period_type: str,
    selected_anchor: date | None = None,
) -> str:
    period_label = STAT_PERIOD_LABELS.get(period_type, period_type)
    selected_label = format_statistics_period_anchor(period_type, selected_anchor)

    if selected_label:
        return f"{period_label} · {selected_label}"

    return period_label


def format_statistics_market_label(pair, exchange: str, direction: str) -> str:
    return (
        f"{format_statistics_exchange_label(exchange)} · "
        f"{format_statistics_direction_label(direction)} · "
        f"{pair.label}"
    )


def get_statistics_side(exchange: str | None, direction: str | None) -> str:
    normalized_exchange = normalize_statistics_exchange(exchange)
    normalized_direction = normalize_statistics_direction(direction)

    if normalized_exchange and normalized_direction:
        return get_p2p_exchange_driver(normalized_exchange).side_for_direction(
            normalized_direction,
        ).upper()

    return "BUY"


def get_statistics_sides(exchange: str | None, direction: str | None) -> list[str]:
    normalized_exchange = normalize_statistics_exchange(exchange)
    normalized_direction = normalize_statistics_direction(direction)

    if normalized_exchange and normalized_direction == STATISTICS_DIRECTION_MIXED:
        driver = get_p2p_exchange_driver(normalized_exchange)
        return [
            driver.side_for_direction(P2P_DIRECTION_FIAT_TO_CRYPTO).upper(),
            driver.side_for_direction(P2P_DIRECTION_CRYPTO_TO_FIAT).upper(),
        ]

    return [get_statistics_side(exchange, direction)]


def build_statistics_pair_cryptos_text(pairs) -> str:
    return (
        "<b>Статистика P2P</b>\n\n"
        "Оберіть стейбл для графіка статистики.\n\n"
        f"Доступні пари: <b>{escape(format_pairs_summary(pairs))}</b>"
    )


def build_statistics_pair_fiats_text(pairs, crypto_currency_id: int) -> str:
    crypto_pairs = filter_pairs_by_crypto(pairs, crypto_currency_id)

    if not crypto_pairs:
        return build_statistics_pair_cryptos_text(pairs)

    return (
        f"<b>Статистика P2P · {escape(crypto_pairs[0].crypto_code)}</b>\n\n"
        "Оберіть фіат для графіка статистики."
    )


def build_p2p_pairs_text(pairs) -> str:
    selected_pairs = [pair for pair in pairs if pair.is_selected]

    if not pairs:
        return (
            "<b>Мої P2P пари</b>\n\n"
            "Поки немає доступних пар. Адмін має додати хоча б одну криптовалюту "
            "і одну фіатну валюту."
        )

    return (
        "<b>Мої P2P пари</b>\n\n"
        "Спочатку оберіть стейбл, а на наступному кроці фіатні валюти "
        "для P2P-пошуку.\n\n"
        f"Обрані: <b>{escape(format_pairs_summary(selected_pairs))}</b>"
    )


def build_p2p_pair_fiats_text(pairs, crypto_currency_id: int) -> str:
    crypto_pairs = filter_pairs_by_crypto(pairs, crypto_currency_id)
    selected_pairs = [pair for pair in pairs if pair.is_selected]

    if not crypto_pairs:
        return build_p2p_pairs_text(pairs)

    return (
        f"<b>Мої P2P пари · {escape(crypto_pairs[0].crypto_code)}</b>\n\n"
        "Оберіть фіатні валюти для цього стейбла.\n\n"
        f"Обрані: <b>{escape(format_pairs_summary(selected_pairs))}</b>"
    )


def build_statistics_text(
    pair,
    exchange: str | None,
    direction: str | None,
    stats,
    period_type: str,
    scope: str,
    *,
    selected_anchor: date | None = None,
    timezone_name: str | None = None,
) -> str:
    period_label = format_statistics_period_label(period_type, selected_anchor)
    title = format_statistics_scope_title(scope)

    if not pair or not exchange or not direction:
        return (
            f"<b>{escape(title)} · {escape(period_label)}</b>\n\n"
            "Спочатку оберіть стейбл, фіат, біржу і напрямок для статистики."
        )

    market_label = escape(format_statistics_market_label(pair, exchange, direction))

    if not stats:
        if scope == STAT_SCOPE_GLOBAL:
            return (
                f"<b>{escape(title)} · {market_label} · {escape(period_label)}</b>\n\n"
                "Поки немає збережених автоматичних сканів для цього набору.\n"
                "Перевірте, що глобальна статистика увімкнена в адмінці, і дочекайтесь наступного погодинного запуску."
            )

        return (
            f"<b>{escape(title)} · {market_label} · {escape(period_label)}</b>\n\n"
            "Поки немає збережених сканів цього набору з таким самим набором фільтрів.\n"
            "Натисніть пошук ордерів на Binance або OKX, і бот почне накопичувати цю статистику."
        )

    rows = [
        f"<b>{escape(title)} · {market_label} · {escape(period_label)}</b>",
        "",
    ]

    for item in stats:
        rows.extend(
            [
                f"<b>{escape(item.exchange_code)} · {escape(item.pair_label)} · {format_stat_side(item.side, item.exchange_code)}</b>",
                f"Період: {format_stat_period(item, timezone_name=timezone_name)}",
                f"Мін/сер/медіана/макс: {format_stat_price(item.min_price)} / {format_stat_price(item.avg_price)} / {format_stat_price(item.median_price)} / {format_stat_price(item.max_price)} {escape(item.fiat_code)}",
                f"Ордерів: {item.offers_count} · Сканів: {item.scans_count}",
                "",
            ]
        )

    return "\n".join(rows).strip()


def format_stat_side(side: str, exchange_code: str | None = None) -> str:
    if str(exchange_code or "").upper() == "OKX":
        labels = {
            "BUY": "SELL",
            "SELL": "BUY",
        }
    else:
        labels = {
            "BUY": "BUY",
            "SELL": "SELL",
        }

    return labels.get(str(side).upper(), str(side))


def get_stat_side_order(side: str, exchange_code: str | None = None) -> int:
    return {
        "BUY": 0,
        "SELL": 1,
    }.get(format_stat_side(side, exchange_code), 99)


def format_stat_period(item, *, timezone_name: str | None = None) -> str:
    started_at = display_datetime(item.period_started_at, timezone_name=timezone_name)
    ended_at = display_datetime(item.period_ended_at, timezone_name=timezone_name)

    return (
        f"{started_at:%Y-%m-%d %H:%M} - "
        f"{ended_at:%Y-%m-%d %H:%M}"
    )


def format_statistics_value_period(
    value: datetime,
    period_type: str,
    *,
    timezone_name: str | None = None,
) -> str:
    display_value = display_datetime(value, timezone_name=timezone_name)

    if period_type == STAT_PERIOD_HOUR:
        return display_value.strftime("%H:%M")

    if period_type == STAT_PERIOD_DAY:
        return display_value.strftime("%d.%m")

    if period_type == STAT_PERIOD_WEEK:
        return f"з {display_value:%d.%m}"

    if period_type == STAT_PERIOD_MONTH:
        return display_value.strftime("%m.%Y")

    if period_type == STAT_PERIOD_YEAR:
        return display_value.strftime("%Y")

    return display_value.strftime("%d.%m.%Y %H:%M")


def format_stat_price(value) -> str:
    return f"{float(value):.2f}"


def build_user_payment_fiats_text(fiat_currencies) -> str:
    if not fiat_currencies:
        return (
            "<b>Мої банки</b>\n\n"
            "Поки немає доступних фіатних валют. Адмін має додати хоча б одну валюту."
        )

    return (
        "<b>Мої банки</b>\n\n"
        "Оберіть валюту, а потім банки/методи оплати, які підходять для ваших "
        "P2P-оголошень.\n\n"
        "Якщо для валюти нічого не обрано, бот не обмежує оголошення банками."
    )


def build_user_payment_methods_text(methods, prefix: str | None = None) -> str:
    if not methods:
        return (
            "<b>Мої банки</b>\n\n"
            "Для цієї валюти ще немає доданих банків або методів оплати."
        )

    selected_count = sum(1 for method in methods if method.is_selected)
    title = f"Мої банки · {escape(methods[0].fiat_code)}"

    if prefix:
        title = f"{escape(prefix)}\n\n{title}"

    return (
        f"<b>{title}</b>\n\n"
        "Увімкніть банки, які хочете бачити у видачі.\n\n"
        f"Обрано: <b>{selected_count}</b>\n"
        "Якщо нічого не обрано — показуються всі банки для цієї валюти."
    )


def filter_pairs_by_crypto(pairs, crypto_currency_id: int):
    return [
        pair
        for pair in pairs
        if pair.crypto_currency_id == crypto_currency_id
    ]


def count_unique_cryptos(pairs) -> int:
    return len({pair.crypto_currency_id for pair in pairs})


def get_statistics_fiat_back_callback(pairs) -> str:
    if count_unique_cryptos(pairs) <= 1:
        return f"{CB_STATS_EXCHANGE_PREFIX}back"

    return CB_STATS_PAIR_BACK


def find_pair(pairs, crypto_currency_id: int, fiat_currency_id: int):
    return next(
        (
            pair
            for pair in pairs
            if pair.crypto_currency_id == crypto_currency_id
            and pair.fiat_currency_id == fiat_currency_id
        ),
        None,
    )


async def apply_filter_value(session, telegram_id: int, field: str, raw_value: str):
    if field == FILTER_SCREEN_ORDER_TIME:
        return await set_order_minutes(session, telegram_id, parse_optional_int(raw_value))

    if field == FILTER_SCREEN_MIN_TRADES:
        return await set_min_trades(session, telegram_id, parse_optional_int(raw_value))

    if field == FILTER_SCREEN_MIN_RATING:
        return await set_min_rating(session, telegram_id, parse_optional_float(raw_value))

    if field == FILTER_SCREEN_MIN_COMPLETION:
        return await set_min_completion(session, telegram_id, parse_optional_float(raw_value))

    if field == FILTER_SCREEN_DISPLAY_COUNT:
        return await set_display_order_count(session, telegram_id, int(raw_value))

    if field == FILTER_SCREEN_CANDIDATE_COUNT:
        return await set_candidate_order_count(session, telegram_id, int(raw_value))

    if field == FILTER_SCREEN_DESCRIPTION_CHECK:
        return await set_description_check_mode(session, telegram_id, raw_value)

    if field == FILTER_SCREEN_THIRD_PARTY:
        return await set_third_party_payments(session, telegram_id, raw_value == "1")

    if field == FILTER_SCREEN_SPLIT_PAYMENTS:
        return await set_split_payments(session, telegram_id, raw_value == "1")

    if field == FILTER_SCREEN_MONOBANK_JAR:
        return await set_monobank_jar_payments(session, telegram_id, raw_value == "1")

    return await get_filters(session, telegram_id)


def parse_optional_int(value: str) -> int | None:
    return None if value == "none" else int(value)


def parse_optional_float(value: str) -> float | None:
    return None if value == "none" else float(value)


def build_knowledge_base_answer_text(knowledge_answer) -> str:
    text = sanitize_telegram_html(
        knowledge_answer.answer or "Не знайшов відповідь у базі знань."
    )

    if not knowledge_answer.sources:
        return text

    sources = ", ".join(
        f"<code>{escape(source)}</code>"
        for source in knowledge_answer.sources
    )

    return f"{text}\n\n<b>Джерела:</b> {sources}"


def sanitize_telegram_html(text: str) -> str:
    normalized = normalize_knowledge_answer_markup(str(text or "").strip())
    placeholders: dict[str, str] = {}

    def replace_tag(match: re.Match) -> str:
        slash = "/" if match.group("slash") else ""
        tag = match.group("tag").lower()

        if tag not in ALLOWED_KNOWLEDGE_HTML_TAGS:
            return match.group(0)

        placeholder = f"@@TG_HTML_TAG_{len(placeholders)}@@"
        placeholders[placeholder] = f"<{slash}{tag}>"
        return placeholder

    protected = re.sub(
        r"<\s*(?P<slash>/)?\s*(?P<tag>b|i|u|s|code)\s*>",
        replace_tag,
        normalized,
        flags=re.IGNORECASE,
    )
    escaped = escape(protected)

    for placeholder, tag in placeholders.items():
        escaped = escaped.replace(placeholder, tag)

    return escaped


def normalize_knowledge_answer_markup(text: str) -> str:
    lines = text.splitlines()
    normalized_lines = []

    for index, line in enumerate(lines):
        heading_match = re.match(r"^\s{0,3}#{1,6}\s*(.+?)\s*$", line)

        if heading_match:
            if normalized_lines and normalized_lines[-1]:
                normalized_lines.append("")
            normalized_lines.append(f"<b>{heading_match.group(1)}</b>")
            continue

        section_match = re.match(
            r"^\s*((?:Перший|Другий|Третій|Четвертий)\s+тип\b.+?)\s*$",
            line,
            flags=re.IGNORECASE,
        )

        if section_match:
            next_line = lines[index + 1] if index + 1 < len(lines) else ""

            if re.match(r"^\s*[-*•]\s+", next_line):
                if normalized_lines and normalized_lines[-1]:
                    normalized_lines.append("")
                normalized_lines.append(f"<b>{section_match.group(1)}</b>")
                continue

        short_section_match = re.match(r"^\s*([^<>\n]{3,60})\s*$", line)

        if short_section_match:
            next_line = lines[index + 1] if index + 1 < len(lines) else ""
            section_title = short_section_match.group(1).strip()

            if (
                re.match(r"^\s*[-*•]\s+", next_line)
                and not section_title.endswith((".", ";", ","))
            ):
                if normalized_lines and normalized_lines[-1]:
                    normalized_lines.append("")
                normalized_lines.append(f"<b>{section_title.rstrip(':')}:</b>")
                continue

        top_bullet_match = re.match(r"^[-*•]\s+(.+?)\s*$", line)

        if top_bullet_match:
            content = top_bullet_match.group(1)
            next_line = lines[index + 1] if index + 1 < len(lines) else ""

            if re.match(r"^\s+[-*•]\s+", next_line):
                if normalized_lines and normalized_lines[-1]:
                    normalized_lines.append("")
                normalized_lines.append(f"<b>{content}</b>")
            else:
                normalized_lines.append(format_knowledge_bullet(content))

            continue

        nested_bullet_match = re.match(r"^\s+[-*•]\s+(.+?)\s*$", line)

        if nested_bullet_match:
            normalized_lines.append(format_knowledge_bullet(nested_bullet_match.group(1)))
            continue

        numbered_match = re.match(r"^\s{0,8}\d+[.)]\s+(.+?)\s*$", line)

        if numbered_match:
            normalized_lines.append(format_knowledge_bullet(numbered_match.group(1)))
            continue

        normalized_lines.append(line.rstrip())

    text = "\n".join(normalized_lines)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)

    return text


def format_knowledge_bullet(content: str) -> str:
    content = content.strip()
    label_match = re.match(r"^([^:]{3,40}):\s*(.+)$", content)

    if label_match:
        label, value = label_match.groups()
        return f"• <b>{label.strip()}:</b> {value.strip()}"

    return f"• {content}"


def strip_telegram_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", str(text or ""))


def split_long_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    if len(text) <= limit:
        return [text]

    parts = []
    current = ""

    for paragraph in text.split("\n\n"):
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph

        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            parts.append(current)

        current = paragraph

    if current:
        parts.append(current)

    return parts


async def send_profile_info(message: types.Message, user, roles: list[str]):
    await message.answer(
        build_profile_summary_text(user, roles),
        reply_markup=cabinet_kb(message.from_user.id),
    )


def build_profile_summary_text(user, roles: list[str]) -> str:
    username = f"@{user.username}" if user.username else "не вказано"
    notifications = "увімкнені" if user.is_notifications_enabled else "вимкнені"
    roles_text = ", ".join(roles) if roles else "немає"
    telegram_user_text = format_telegram_user_data(user.telegram_data)
    location_text = format_user_location_data(user)

    return (
        "<b>Інфо про себе</b>\n\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Username: {escape(username)}\n"
        f"Ролі: {escape(roles_text)}\n"
        f"Сповіщення: {notifications}\n"
        f"Дата реєстрації: {user.created_at:%Y-%m-%d %H:%M}\n\n"
        f"{location_text}\n\n"
        f"<b>Дані Telegram</b>\n{telegram_user_text}"
    )


def build_location_saved_text(user) -> str:
    timezone_text = user.location_timezone or "не визначено"

    return (
        "<b>Геолокацію збережено</b>\n\n"
        f"Timezone: <code>{escape(timezone_text)}</code>"
    )


def format_user_location_data(user) -> str:
    if not user.location_data:
        return (
            "<b>Геолокація</b>\n"
            "• Статус: ще не збережена\n"
            "• Щоб визначити timezone, натисніть “📍 Поділитися геолокацією”."
        )

    rows = [
        f"• Timezone: <code>{escape(user.location_timezone or 'не визначено')}</code>",
    ]

    if user.location_updated_at:
        rows.append(f"• Оновлено: {user.location_updated_at:%Y-%m-%d %H:%M}")

    return "<b>Геолокація</b>\n" + "\n".join(rows)


def format_optional_value(value) -> str:
    if value is None:
        return "не передано"

    return escape(str(value))


def format_telegram_user_data(telegram_user: types.User | dict | None) -> str:
    if telegram_user is None:
        return "Telegram не передав додаткових даних."

    if isinstance(telegram_user, dict):
        data = telegram_user
    else:
        data = telegram_user.model_dump(exclude_none=False)

    if not data:
        return "Telegram не передав додаткових даних."

    sections = [
        format_telegram_section("Основне", data, TELEGRAM_USER_MAIN_FIELDS),
        format_telegram_section("Можливості", data, TELEGRAM_USER_CAPABILITY_FIELDS),
        format_telegram_extra_fields(data),
    ]

    return "\n\n".join(section for section in sections if section)


def format_telegram_section(
    title: str,
    data: dict,
    fields: tuple[tuple[str, str], ...],
) -> str:
    rows = [
        f"• {label}: {format_telegram_value(key, data[key])}"
        for key, label in fields
        if key in data
    ]

    if not rows:
        return ""

    return f"<b>{title}</b>\n" + "\n".join(rows)


def format_telegram_extra_fields(data: dict) -> str:
    rows = [
        f"• {escape(format_telegram_field_name(key))}: {format_telegram_value(key, value)}"
        for key, value in data.items()
        if key not in TELEGRAM_USER_KNOWN_FIELDS
    ]

    if not rows:
        return ""

    return "<b>Інші поля</b>\n" + "\n".join(rows)


def format_telegram_value(key: str, value) -> str:
    if value is None:
        return "не передано"

    if isinstance(value, bool):
        return "✅ так" if value else "❌ ні"

    if isinstance(value, (dict, list)):
        return f"<code>{escape(json.dumps(value, ensure_ascii=False))}</code>"

    if key == "id":
        return f"<code>{escape(str(value))}</code>"

    if key == "username":
        return f"@{escape(str(value))}"

    return escape(str(value))


def format_telegram_field_name(key: str) -> str:
    return str(key).replace("_", " ").capitalize()
