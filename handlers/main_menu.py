import json
from html import escape

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from db.base import AsyncSessionLocal
from fsm.states import AppMenu
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
    BTN_MY_INFO,
    BTN_P2P,
    BTN_P2P_FILTERS,
    BTN_RESET_FILTERS,
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
    exchanges_kb,
    p2p_filter_values_inline_kb,
    p2p_filters_inline_kb,
)
from services.menu_service import root_menu_for_user
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
from services.user_service import UserService

router = Router()

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
        "Monobank Банка",
        "Якщо заборонити, бот прибере ордери, де в описі просять оплату через Monobank «банку» або посилання на банку.",
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

    await message.answer(
        "Оберіть біржу:",
        reply_markup=exchanges_kb(),
    )


@router.message(F.text == BTN_CABINET)
async def cabinet_menu(message: types.Message, state: FSMContext):
    await state.set_state(AppMenu.cabinet)

    await message.answer(
        "Особистий кабінет:",
        reply_markup=cabinet_kb(),
    )


@router.message(StateFilter(AppMenu.p2p_filters), F.text == BTN_BACK)
async def back_to_cabinet(message: types.Message, state: FSMContext):
    await state.set_state(AppMenu.cabinet)

    await message.answer(
        "Особистий кабінет:",
        reply_markup=cabinet_kb(),
    )


@router.message(StateFilter(AppMenu.p2p_exchanges, AppMenu.cabinet, None), F.text == BTN_BACK)
async def back_to_main_menu(message: types.Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Головне меню:",
        reply_markup=await root_menu_for_user(message.from_user.id),
    )


@router.message(F.text == BTN_MY_INFO)
async def my_info(message: types.Message):
    async with AsyncSessionLocal() as session:
        service = UserService(session)
        user = await service.get_user_by_telegram_id(message.from_user.id)
        roles = await service.get_user_role_codes(message.from_user.id)

    if not user:
        await message.answer("Профіль ще не створено. Натисніть /start.")
        return

    username = f"@{user.username}" if user.username else "не вказано"
    notifications = "увімкнені" if user.is_notifications_enabled else "вимкнені"
    roles_text = ", ".join(roles) if roles else "немає"
    telegram_user_text = format_telegram_user_data(message.from_user)

    await message.answer(
        "<b>Інфо про себе</b>\n\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Username: {escape(username)}\n"
        f"Ролі: {escape(roles_text)}\n"
        f"Сповіщення: {notifications}\n"
        f"Дата реєстрації: {user.created_at:%Y-%m-%d %H:%M}\n\n"
        f"<b>Дані Telegram</b>\n{telegram_user_text}",
        reply_markup=cabinet_kb(),
    )


@router.message(F.text == BTN_P2P_FILTERS)
async def p2p_filters(message: types.Message, state: FSMContext):
    await state.set_state(AppMenu.p2p_filters)
    await send_filters_menu(message)


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


def format_telegram_user_data(telegram_user: types.User) -> str:
    data = telegram_user.model_dump(exclude_none=True)

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
