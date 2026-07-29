from html import escape

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from config import Config
from db.base import AsyncSessionLocal
from db.models import FiatCurrency, PaymentMethod
from db.dto import (
    CURRENCY_TYPE_CRYPTO,
    CURRENCY_TYPE_FIAT,
    PERMISSION_MANAGE_CURRENCIES,
    PERMISSION_MANAGE_PAYMENT_METHODS,
    PERMISSION_RUN_SCANNER,
    PERMISSION_VIEW_ADMIN_PANEL,
    get_currency_option,
    get_payment_method_option,
)
from filters.permission import PermissionRequired
from fsm.states import AdminMenu
from keyboards.menu import (
    BTN_ADD_CRYPTO_CURRENCY,
    BTN_ADD_FIAT_CURRENCY,
    BTN_ADMIN_CURRENCIES,
    BTN_ADMIN_PANEL,
    BTN_ADMIN_PAYMENT_METHODS,
    BTN_ADMIN_STATISTICS,
    BTN_BACK,
    BTN_LIST_CURRENCIES,
    BTN_STATISTICS,
    CB_ADMIN_STATS_BANK_FIAT_PREFIX,
    CB_ADMIN_STATS_BANK_TOGGLE_PREFIX,
    CB_ADMIN_STATS_BANKS_MENU,
    CB_ADMIN_STATS_EXCHANGE_TOGGLE_PREFIX,
    CB_ADMIN_STATS_EXCHANGES_MENU,
    CB_ADMIN_STATS_FILTER_PREFIX,
    CB_ADMIN_STATS_MENU,
    CB_ADMIN_STATS_PAY_PREFIX,
    CB_ADMIN_STATS_RESET,
    CB_ADMIN_STATS_RUN,
    CB_ADMIN_STATS_SET_PREFIX,
    CB_ADMIN_STATS_TOGGLE_PREFIX,
    CB_ADMIN_CURRENCIES_MENU,
    CB_ADMIN_CURRENCY_ADD_PREFIX,
    CB_ADMIN_PAYMENT_ADD_PREFIX,
    CB_ADMIN_PAYMENT_FIAT_PREFIX,
    CB_ADMIN_PAYMENT_FIATS_MENU,
    admin_statistics_bank_fiats_inline_kb,
    admin_statistics_bank_methods_inline_kb,
    admin_statistics_exchanges_inline_kb,
    admin_statistics_inline_kb,
    admin_currency_options_inline_kb,
    admin_currencies_kb,
    admin_payment_fiats_inline_kb,
    admin_payment_options_inline_kb,
    p2p_filter_values_inline_kb,
)
from services.currency_service import CurrencyService
from services.menu_service import admin_menu_for_user, root_menu_for_user
from services.payment_method_service import PaymentMethodService
from services.p2p_filters import filters_summary
from services.statistics_settings_service import StatisticsSettingsService
from tasks.statistics_scanner import schedule_global_statistics_scan

router = Router()


@router.message(F.text == BTN_ADMIN_PANEL, PermissionRequired(PERMISSION_VIEW_ADMIN_PANEL))
async def admin_panel(message: types.Message, state: FSMContext):
    await state.set_state(AdminMenu.panel)

    await message.answer(
        "Адмін панель:",
        reply_markup=await admin_menu_for_user(message.from_user.id),
    )


@router.message(F.text == BTN_ADMIN_PANEL)
async def admin_panel_forbidden(message: types.Message):
    await message.answer("У вас немає доступу до адмін панелі.")


@router.message(StateFilter(AdminMenu.panel), F.text == BTN_BACK)
async def admin_back_to_main(message: types.Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Головне меню:",
        reply_markup=await root_menu_for_user(message.from_user.id),
    )


@router.message(
    StateFilter(AdminMenu.panel),
    F.text == BTN_ADMIN_CURRENCIES,
    PermissionRequired(PERMISSION_MANAGE_CURRENCIES),
)
async def admin_currencies(message: types.Message, state: FSMContext):
    await state.set_state(AdminMenu.currencies)

    await message.answer(
        "Керування валютами:",
        reply_markup=admin_currencies_kb(),
    )


@router.message(StateFilter(AdminMenu.currencies), F.text == BTN_BACK)
async def currencies_back_to_admin(message: types.Message, state: FSMContext):
    await state.set_state(AdminMenu.panel)

    await message.answer(
        "Адмін панель:",
        reply_markup=await admin_menu_for_user(message.from_user.id),
    )


@router.message(StateFilter(AdminMenu.payment_methods), F.text == BTN_BACK)
async def payment_methods_back_to_admin(message: types.Message, state: FSMContext):
    await state.set_state(AdminMenu.panel)

    await message.answer(
        "Адмін панель:",
        reply_markup=await admin_menu_for_user(message.from_user.id),
    )


@router.message(
    StateFilter(AdminMenu.statistics, AdminMenu.statistics_banks),
    F.text == BTN_BACK,
)
async def statistics_back_to_admin(message: types.Message, state: FSMContext):
    await state.set_state(AdminMenu.panel)

    await message.answer(
        "Адмін панель:",
        reply_markup=await admin_menu_for_user(message.from_user.id),
    )


@router.message(
    StateFilter(AdminMenu.panel),
    F.text == BTN_ADMIN_PAYMENT_METHODS,
    PermissionRequired(PERMISSION_MANAGE_PAYMENT_METHODS),
)
async def admin_payment_methods(message: types.Message, state: FSMContext):
    await state.set_state(AdminMenu.payment_methods)
    await send_payment_fiats_menu(message)


@router.message(StateFilter(AdminMenu.panel), F.text == BTN_ADMIN_PAYMENT_METHODS)
async def admin_payment_methods_forbidden(message: types.Message):
    await message.answer("У вас немає доступу до керування методами оплати.")


@router.message(
    StateFilter(AdminMenu.panel),
    F.text == BTN_ADMIN_STATISTICS,
    PermissionRequired(PERMISSION_RUN_SCANNER),
)
@router.message(
    StateFilter(AdminMenu.panel),
    F.text == BTN_STATISTICS,
    PermissionRequired(PERMISSION_RUN_SCANNER),
)
async def admin_statistics(message: types.Message, state: FSMContext):
    await state.set_state(AdminMenu.statistics)
    await send_admin_statistics_menu(message)


@router.message(StateFilter(AdminMenu.panel), F.text == BTN_ADMIN_STATISTICS)
@router.message(StateFilter(AdminMenu.panel), F.text == BTN_STATISTICS)
async def admin_statistics_forbidden(message: types.Message):
    await message.answer("У вас немає доступу до налаштувань статистики.")


@router.message(
    StateFilter(AdminMenu.currencies),
    F.text == BTN_ADD_FIAT_CURRENCY,
    PermissionRequired(PERMISSION_MANAGE_CURRENCIES),
)
async def add_fiat_currency(message: types.Message, state: FSMContext):
    await state.set_state(AdminMenu.currencies)

    await message.answer(
        "<b>Оберіть фіатну валюту</b>\n\n"
        "Валюта буде додана з контрольованого списку.",
        reply_markup=admin_currency_options_inline_kb(
            CURRENCY_TYPE_FIAT,
            await get_existing_currency_codes(CURRENCY_TYPE_FIAT),
        ),
    )


@router.message(
    StateFilter(AdminMenu.currencies),
    F.text == BTN_ADD_CRYPTO_CURRENCY,
    PermissionRequired(PERMISSION_MANAGE_CURRENCIES),
)
async def add_crypto_currency(message: types.Message, state: FSMContext):
    await state.set_state(AdminMenu.currencies)

    await message.answer(
        "<b>Оберіть криптовалюту</b>\n\n"
        "Валюта буде додана з контрольованого списку.",
        reply_markup=admin_currency_options_inline_kb(
            CURRENCY_TYPE_CRYPTO,
            await get_existing_currency_codes(CURRENCY_TYPE_CRYPTO),
        ),
    )


@router.message(
    StateFilter(AdminMenu.currencies),
    F.text == BTN_LIST_CURRENCIES,
    PermissionRequired(PERMISSION_MANAGE_CURRENCIES),
)
async def list_currencies(message: types.Message):
    async with AsyncSessionLocal() as session:
        service = CurrencyService(session)
        fiat_currencies, crypto_currencies = await service.list_currencies()
        payment_groups = await PaymentMethodService(session).list_all_grouped()

    await message.answer(
        build_currencies_list_text(
            fiat_currencies,
            crypto_currencies,
            payment_groups,
        ),
        reply_markup=admin_currencies_kb(),
    )


@router.callback_query(
    F.data == CB_ADMIN_CURRENCIES_MENU,
    PermissionRequired(PERMISSION_MANAGE_CURRENCIES),
)
async def currency_options_back(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminMenu.currencies)
    await callback.answer()

    if callback.message:
        await callback.message.edit_text("Керування валютами:")


@router.callback_query(
    F.data.startswith(CB_ADMIN_CURRENCY_ADD_PREFIX),
    PermissionRequired(PERMISSION_MANAGE_CURRENCIES),
)
async def add_currency_from_catalog(callback: types.CallbackQuery, state: FSMContext):
    currency_type, code = parse_currency_callback(callback.data)
    option = get_currency_option(currency_type, code)

    if not option:
        await callback.answer("Валюта не знайдена в дозволеному списку.", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        service = CurrencyService(session)
        result = await service.upsert_currency(
            currency_type,
            option.code,
            option.name,
        )

    await state.set_state(AdminMenu.currencies)
    action = "додано" if result.created else "оновлено"
    await callback.answer(f"{result.code} {action}")

    if callback.message:
        if currency_type == CURRENCY_TYPE_FIAT:
            await edit_payment_options_for_fiat_code(
                callback,
                state,
                result.code,
                prefix=(
                    f"Фіатну валюту {action}: <b>{escape(result.code)}</b> — "
                    f"{escape(result.name)}\n\n"
                    "Тепер додайте хоча б один банк або метод оплати для цієї валюти."
                ),
            )
            return

        await callback.message.edit_text(
            f"Валюту {action}: <b>{escape(result.code)}</b> — {escape(result.name)}\n\n"
            "Можна додати ще одну валюту з цього списку.",
            reply_markup=admin_currency_options_inline_kb(
                currency_type,
                await get_existing_currency_codes(currency_type),
            ),
        )


@router.callback_query(F.data.startswith(CB_ADMIN_CURRENCY_ADD_PREFIX))
async def add_currency_from_catalog_forbidden(callback: types.CallbackQuery):
    await callback.answer("У вас немає доступу до керування валютами.", show_alert=True)


@router.callback_query(
    F.data == CB_ADMIN_PAYMENT_FIATS_MENU,
    PermissionRequired(PERMISSION_MANAGE_PAYMENT_METHODS),
)
async def payment_fiats_back(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminMenu.payment_methods)
    await callback.answer()
    await edit_payment_fiats_menu(callback)


@router.callback_query(
    F.data.startswith(CB_ADMIN_PAYMENT_FIAT_PREFIX),
    PermissionRequired(PERMISSION_MANAGE_PAYMENT_METHODS),
)
async def choose_payment_fiat(callback: types.CallbackQuery, state: FSMContext):
    fiat_currency_id = parse_payment_fiat_callback(callback.data or "")

    if not fiat_currency_id:
        await callback.answer("Не вдалося прочитати валюту.", show_alert=True)
        return

    await state.set_state(AdminMenu.payment_methods)
    await callback.answer()
    await edit_payment_options_for_fiat_id(callback, state, fiat_currency_id)


@router.callback_query(
    F.data.startswith(CB_ADMIN_PAYMENT_ADD_PREFIX),
    PermissionRequired(PERMISSION_MANAGE_PAYMENT_METHODS),
)
async def add_payment_method_from_catalog(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    fiat_currency_id, method_code = parse_payment_method_callback(callback.data or "")

    if not fiat_currency_id or not method_code:
        await callback.answer("Не вдалося прочитати метод оплати.", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        service = PaymentMethodService(session)
        fiat = await service.get_fiat_by_id(fiat_currency_id)

        if not fiat:
            await callback.answer("Фіатна валюта не знайдена.", show_alert=True)
            return

        option = get_payment_method_option(fiat.code, method_code)

        if not option:
            await callback.answer("Метод оплати не знайдений у списку.", show_alert=True)
            return

        result = await service.upsert_method(fiat.id, option)

    await state.set_state(AdminMenu.payment_methods)
    action = "додано" if result.created else "оновлено"
    await callback.answer(f"{result.name} {action}")
    await edit_payment_options_for_fiat_id(
        callback,
        state,
        fiat_currency_id,
        prefix=(
            f"Метод оплати {action}: <b>{escape(result.name)}</b> "
            f"для <b>{escape(result.fiat_code)}</b>."
        ),
    )


@router.callback_query(F.data.startswith(CB_ADMIN_PAYMENT_ADD_PREFIX))
async def add_payment_method_forbidden(callback: types.CallbackQuery):
    await callback.answer("У вас немає доступу до методів оплати.", show_alert=True)


@router.callback_query(
    F.data == CB_ADMIN_STATS_MENU,
    PermissionRequired(PERMISSION_RUN_SCANNER),
)
async def admin_statistics_menu_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminMenu.statistics)
    await callback.answer()
    await edit_admin_statistics_menu(callback)


@router.callback_query(
    F.data.startswith(CB_ADMIN_STATS_TOGGLE_PREFIX),
    PermissionRequired(PERMISSION_RUN_SCANNER),
)
async def admin_statistics_toggle(callback: types.CallbackQuery, state: FSMContext):
    field = callback.data[len(CB_ADMIN_STATS_TOGGLE_PREFIX):]

    async with AsyncSessionLocal() as session:
        await StatisticsSettingsService(session).toggle_bool(field)

    await state.set_state(AdminMenu.statistics)
    await callback.answer("Оновлено")
    await edit_admin_statistics_menu(callback)


@router.callback_query(
    F.data.startswith(CB_ADMIN_STATS_FILTER_PREFIX),
    PermissionRequired(PERMISSION_RUN_SCANNER),
)
async def admin_statistics_filter(callback: types.CallbackQuery, state: FSMContext):
    screen = callback.data[len(CB_ADMIN_STATS_FILTER_PREFIX):]

    async with AsyncSessionLocal() as session:
        settings = await StatisticsSettingsService(session).get_filter_settings()

    await state.set_state(AdminMenu.statistics)
    await callback.answer()

    if callback.message:
        await callback.message.edit_text(
            build_admin_statistics_filter_screen_text(screen),
            reply_markup=p2p_filter_values_inline_kb(
                settings,
                screen,
                set_prefix=CB_ADMIN_STATS_SET_PREFIX,
                pay_prefix=CB_ADMIN_STATS_PAY_PREFIX,
                back_callback=CB_ADMIN_STATS_MENU,
            ),
        )


@router.callback_query(
    F.data.startswith(CB_ADMIN_STATS_SET_PREFIX),
    PermissionRequired(PERMISSION_RUN_SCANNER),
)
async def admin_statistics_set_filter(callback: types.CallbackQuery, state: FSMContext):
    field, raw_value = parse_admin_statistics_set_callback(callback.data or "")

    if not field or raw_value is None:
        await callback.answer("Не вдалося прочитати значення.", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        await StatisticsSettingsService(session).set_filter_value(field, raw_value)

    await state.set_state(AdminMenu.statistics)
    await callback.answer("Збережено")
    await edit_admin_statistics_menu(callback)


@router.callback_query(
    F.data.startswith(CB_ADMIN_STATS_PAY_PREFIX),
    PermissionRequired(PERMISSION_RUN_SCANNER),
)
async def admin_statistics_toggle_payment_category(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    category = callback.data[len(CB_ADMIN_STATS_PAY_PREFIX):]

    async with AsyncSessionLocal() as session:
        settings = await StatisticsSettingsService(session).toggle_payment_category(category)

    await state.set_state(AdminMenu.statistics)
    await callback.answer("Оновлено")

    if callback.message:
        await callback.message.edit_text(
            build_admin_statistics_filter_screen_text("pay_methods"),
            reply_markup=p2p_filter_values_inline_kb(
                settings,
                "pay_methods",
                set_prefix=CB_ADMIN_STATS_SET_PREFIX,
                pay_prefix=CB_ADMIN_STATS_PAY_PREFIX,
                back_callback=CB_ADMIN_STATS_MENU,
            ),
        )


@router.callback_query(
    F.data == CB_ADMIN_STATS_RESET,
    PermissionRequired(PERMISSION_RUN_SCANNER),
)
async def admin_statistics_reset(callback: types.CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        await StatisticsSettingsService(session).reset_filters()

    await state.set_state(AdminMenu.statistics)
    await callback.answer("Фільтри скинуто")
    await edit_admin_statistics_menu(callback)


@router.callback_query(
    F.data == CB_ADMIN_STATS_RUN,
    PermissionRequired(PERMISSION_RUN_SCANNER),
)
async def admin_statistics_run_now(callback: types.CallbackQuery):
    if schedule_global_statistics_scan():
        message = "Скан статистики запущено у фоні"
    else:
        message = "Скан статистики вже виконується"

    await callback.answer(message, show_alert=True)


@router.callback_query(
    F.data == CB_ADMIN_STATS_EXCHANGES_MENU,
    PermissionRequired(PERMISSION_RUN_SCANNER),
)
async def admin_statistics_exchanges(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminMenu.statistics)
    await callback.answer()
    await edit_admin_statistics_exchanges(callback)


@router.callback_query(
    F.data.startswith(CB_ADMIN_STATS_EXCHANGE_TOGGLE_PREFIX),
    PermissionRequired(PERMISSION_RUN_SCANNER),
)
async def admin_statistics_exchange_toggle(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    field = callback.data[len(CB_ADMIN_STATS_EXCHANGE_TOGGLE_PREFIX):]

    async with AsyncSessionLocal() as session:
        await StatisticsSettingsService(session).toggle_bool(field)

    await state.set_state(AdminMenu.statistics)
    await callback.answer("Оновлено")
    await edit_admin_statistics_exchanges(callback)


@router.callback_query(
    F.data == CB_ADMIN_STATS_BANKS_MENU,
    PermissionRequired(PERMISSION_RUN_SCANNER),
)
async def admin_statistics_banks(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminMenu.statistics_banks)
    await callback.answer()
    await edit_admin_statistics_bank_fiats(callback)


@router.callback_query(
    F.data.startswith(CB_ADMIN_STATS_BANK_FIAT_PREFIX),
    PermissionRequired(PERMISSION_RUN_SCANNER),
)
async def admin_statistics_bank_fiat(callback: types.CallbackQuery, state: FSMContext):
    fiat_currency_id = parse_admin_statistics_bank_fiat_callback(callback.data or "")

    if not fiat_currency_id:
        await callback.answer("Не вдалося прочитати валюту.", show_alert=True)
        return

    await state.set_state(AdminMenu.statistics_banks)
    await callback.answer()
    await edit_admin_statistics_bank_methods(callback, fiat_currency_id)


@router.callback_query(
    F.data.startswith(CB_ADMIN_STATS_BANK_TOGGLE_PREFIX),
    PermissionRequired(PERMISSION_RUN_SCANNER),
)
async def admin_statistics_bank_toggle(callback: types.CallbackQuery, state: FSMContext):
    payment_method_id = parse_admin_statistics_bank_toggle_callback(callback.data or "")

    if not payment_method_id:
        await callback.answer("Не вдалося прочитати банк.", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        service = StatisticsSettingsService(session)
        method = await session.get(PaymentMethod, payment_method_id)

        await service.toggle_payment_method(payment_method_id)

        fiat_currency_id = method.fiat_currency_id if method else None

    await state.set_state(AdminMenu.statistics_banks)
    await callback.answer("Оновлено")

    if fiat_currency_id:
        await edit_admin_statistics_bank_methods(callback, fiat_currency_id)
    else:
        await edit_admin_statistics_bank_fiats(callback)


async def send_admin_statistics_menu(message: types.Message):
    async with AsyncSessionLocal() as session:
        service = StatisticsSettingsService(session)
        settings = await service.get_or_create_settings()
        filter_settings = await service.get_filter_settings()
        selected_method_ids = await service.list_selected_payment_method_ids()
        crypto_currencies = await service.list_crypto_currencies()
        fiat_currencies = await service.list_fiat_currencies()

    await message.answer(
        build_admin_statistics_text(
            settings,
            filter_settings,
            selected_method_ids,
            crypto_currencies,
            fiat_currencies,
        ),
        reply_markup=admin_statistics_inline_kb(settings, filter_settings),
    )


async def edit_admin_statistics_menu(callback: types.CallbackQuery):
    async with AsyncSessionLocal() as session:
        service = StatisticsSettingsService(session)
        settings = await service.get_or_create_settings()
        filter_settings = await service.get_filter_settings()
        selected_method_ids = await service.list_selected_payment_method_ids()
        crypto_currencies = await service.list_crypto_currencies()
        fiat_currencies = await service.list_fiat_currencies()

    if callback.message:
        await callback.message.edit_text(
            build_admin_statistics_text(
                settings,
                filter_settings,
                selected_method_ids,
                crypto_currencies,
                fiat_currencies,
            ),
            reply_markup=admin_statistics_inline_kb(settings, filter_settings),
        )


async def edit_admin_statistics_exchanges(callback: types.CallbackQuery):
    async with AsyncSessionLocal() as session:
        settings = await StatisticsSettingsService(session).get_or_create_settings()

    if callback.message:
        await callback.message.edit_text(
            "<b>Біржі для глобальної статистики</b>\n\n"
            "Увімкніть біржі, які мають скануватись автоматично для загальної статистики.",
            reply_markup=admin_statistics_exchanges_inline_kb(settings),
        )


async def edit_admin_statistics_bank_fiats(callback: types.CallbackQuery):
    async with AsyncSessionLocal() as session:
        service = StatisticsSettingsService(session)
        fiat_currencies = await service.list_fiat_currencies()
        selected_ids = await service.list_selected_payment_method_ids()
        selected_counts = {}

        for fiat in fiat_currencies:
            methods = await service.list_payment_methods_for_fiat(fiat.id)
            selected_counts[fiat.id] = sum(
                1 for method in methods if method.id in selected_ids
            )

    if callback.message:
        await callback.message.edit_text(
            "<b>Банки для глобальної статистики</b>\n\n"
            "Якщо для валюти нічого не обрано, статистика не обмежується банками цієї валюти.",
            reply_markup=admin_statistics_bank_fiats_inline_kb(
                fiat_currencies,
                selected_counts,
            ),
        )


async def edit_admin_statistics_bank_methods(
    callback: types.CallbackQuery,
    fiat_currency_id: int,
):
    async with AsyncSessionLocal() as session:
        service = StatisticsSettingsService(session)
        fiat = await session.get(FiatCurrency, fiat_currency_id)

        if not fiat:
            await callback.answer("Фіатна валюта не знайдена.", show_alert=True)
            return

        methods = await service.list_payment_methods_for_fiat(fiat.id)
        selected_ids = await service.list_selected_payment_method_ids()

    if callback.message:
        await callback.message.edit_text(
            f"<b>Банки для статистики · {escape(fiat.code)}</b>\n\n"
            "Увімкніть банки, які мають враховуватись у глобальній статистиці.",
            reply_markup=admin_statistics_bank_methods_inline_kb(
                methods,
                selected_ids,
            ),
        )


def build_admin_statistics_text(
    settings,
    filter_settings,
    selected_method_ids: set[int],
    crypto_currencies,
    fiat_currencies,
) -> str:
    exchanges = []

    if settings.scan_binance:
        exchanges.append("Binance")

    if settings.scan_okx:
        exchanges.append("OKX")

    directions = []

    if settings.scan_buy:
        directions.append("BUY")

    if settings.scan_sell:
        directions.append("SELL")

    pairs_count = len(crypto_currencies) * len(fiat_currencies)
    min_interval_seconds = max(
        60,
        Config.P2P_RECOMMENDATION_MIN_INTERVAL_SECONDS,
    )
    max_interval_seconds = max(
        min_interval_seconds,
        Config.P2P_RECOMMENDATION_MAX_INTERVAL_SECONDS,
    )
    min_interval_minutes = round(min_interval_seconds / 60, 1)
    max_interval_minutes = round(max_interval_seconds / 60, 1)

    return (
        "<b>Глобальна статистика P2P</b>\n\n"
        f"Стан: <b>{'увімкнено' if settings.is_enabled else 'вимкнено'}</b>\n"
        f"Інтервал: <b>{min_interval_minutes:g}-{max_interval_minutes:g}</b> хв\n"
        f"Біржі: <b>{escape(', '.join(exchanges) or 'немає')}</b>\n"
        f"Напрямки: <b>{escape(', '.join(directions) or 'немає')}</b>\n"
        f"Пар для скану: <b>{pairs_count}</b>\n"
        f"Банків обрано: <b>{len(selected_method_ids)}</b>\n\n"
        f"{filters_summary(filter_settings)}\n\n"
        "Автоматичний скан формує загальну статистику по всіх доданих "
        "crypto/fiat парах через випадкові проміжки часу."
    )


def build_admin_statistics_filter_screen_text(screen: str) -> str:
    titles = {
        "time": "Час угоди",
        "trades": "Кількість угод",
        "rating": "Оцінка мерчанта",
        "completion": "Виконання угод",
        "pay_methods": "Методи оплати",
        "third_party": "Треті особи",
        "split": "Кілька платежів",
        "mono_jar": "Банка / збір / конверт",
        "desc": "Перевірка опису",
        "display": "Кількість виводу",
        "candidates": "Кандидати для перевірки",
    }
    title = titles.get(screen, "Фільтр статистики")

    return (
        f"<b>{escape(title)}</b>\n\n"
        "Оберіть значення для автоматичного фільтра глобальної статистики."
    )


def parse_admin_statistics_set_callback(
    callback_data: str,
) -> tuple[str | None, str | None]:
    payload = callback_data[len(CB_ADMIN_STATS_SET_PREFIX):]
    parts = payload.split(":", 1)

    if len(parts) != 2:
        return None, None

    return parts[0], parts[1]


def parse_admin_statistics_bank_fiat_callback(callback_data: str) -> int | None:
    payload = callback_data[len(CB_ADMIN_STATS_BANK_FIAT_PREFIX):]

    try:
        return int(payload)
    except ValueError:
        return None


def parse_admin_statistics_bank_toggle_callback(callback_data: str) -> int | None:
    payload = callback_data[len(CB_ADMIN_STATS_BANK_TOGGLE_PREFIX):]

    try:
        return int(payload)
    except ValueError:
        return None


def build_currencies_list_text(
    fiat_currencies: list,
    crypto_currencies: list,
    payment_groups: list | None = None,
) -> str:
    return "\n\n".join(
        [
            "<b>Фіатні валюти</b>\n"
            + format_fiat_currency_rows(fiat_currencies, payment_groups or []),
            "<b>Криптовалюти</b>\n" + format_currency_rows(crypto_currencies),
        ]
    )


def format_fiat_currency_rows(currencies: list, payment_groups: list) -> str:
    if not currencies:
        return "немає"

    methods_by_fiat_id = {
        fiat.id: methods
        for fiat, methods in payment_groups
    }

    rows = []

    for currency in currencies:
        methods = methods_by_fiat_id.get(currency.id, [])
        method_names = ", ".join(method.name for method in methods[:5])

        if len(methods) > 5:
            method_names = f"{method_names} +{len(methods) - 5}"

        if not method_names:
            method_names = "немає методів"

        rows.append(
            f"• <b>{escape(currency.code)}</b> — {escape(currency.name)}\n"
            f"  Методи: {escape(method_names)}"
        )

    return "\n".join(rows)


def format_currency_rows(currencies: list) -> str:
    if not currencies:
        return "немає"

    return "\n".join(
        f"• <b>{escape(currency.code)}</b> — {escape(currency.name)}"
        for currency in currencies
    )


def parse_currency_callback(callback_data: str) -> tuple[str, str]:
    payload = callback_data[len(CB_ADMIN_CURRENCY_ADD_PREFIX):]
    parts = payload.split(":", 1)

    if len(parts) != 2:
        return "", ""

    return parts[0], parts[1]


async def get_existing_currency_codes(currency_type: str) -> set[str]:
    async with AsyncSessionLocal() as session:
        service = CurrencyService(session)
        fiat_currencies, crypto_currencies = await service.list_currencies()

    currencies = fiat_currencies if currency_type == CURRENCY_TYPE_FIAT else crypto_currencies

    return {currency.code for currency in currencies}


async def send_payment_fiats_menu(message: types.Message):
    async with AsyncSessionLocal() as session:
        service = PaymentMethodService(session)
        fiat_currencies = await service.list_fiat_currencies()
        method_counts = await get_payment_method_counts(service, fiat_currencies)

    await message.answer(
        build_payment_fiats_text(fiat_currencies),
        reply_markup=(
            admin_payment_fiats_inline_kb(fiat_currencies, method_counts)
            if fiat_currencies
            else None
        ),
    )


async def edit_payment_fiats_menu(callback: types.CallbackQuery):
    async with AsyncSessionLocal() as session:
        service = PaymentMethodService(session)
        fiat_currencies = await service.list_fiat_currencies()
        method_counts = await get_payment_method_counts(service, fiat_currencies)

    if callback.message:
        await callback.message.edit_text(
            build_payment_fiats_text(fiat_currencies),
            reply_markup=(
                admin_payment_fiats_inline_kb(fiat_currencies, method_counts)
                if fiat_currencies
                else None
            ),
        )


async def edit_payment_options_for_fiat_code(
    callback: types.CallbackQuery,
    state: FSMContext,
    fiat_code: str,
    *,
    prefix: str | None = None,
):
    async with AsyncSessionLocal() as session:
        service = PaymentMethodService(session)
        fiat = await service.get_fiat_by_code(fiat_code)

    if not fiat:
        return

    await edit_payment_options_for_fiat_id(
        callback,
        state,
        fiat.id,
        prefix=prefix,
    )


async def edit_payment_options_for_fiat_id(
    callback: types.CallbackQuery,
    state: FSMContext,
    fiat_currency_id: int,
    *,
    prefix: str | None = None,
):
    async with AsyncSessionLocal() as session:
        service = PaymentMethodService(session)
        fiat = await service.get_fiat_by_id(fiat_currency_id)

        if not fiat:
            await callback.answer("Фіатна валюта не знайдена.", show_alert=True)
            return

        existing_codes = await service.get_existing_codes(fiat.id)

    await state.set_state(AdminMenu.payment_methods)

    if callback.message:
        await callback.message.edit_text(
            build_payment_options_text(fiat, existing_codes, prefix=prefix),
            reply_markup=admin_payment_options_inline_kb(fiat, existing_codes),
        )


async def get_payment_method_counts(
    service: PaymentMethodService,
    fiat_currencies: list,
) -> dict[int, int]:
    counts = {}

    for fiat in fiat_currencies:
        counts[fiat.id] = len(await service.list_for_fiat(fiat.id))

    return counts


def build_payment_fiats_text(fiat_currencies: list) -> str:
    if not fiat_currencies:
        return (
            "<b>Методи оплати</b>\n\n"
            "Спочатку додайте хоча б одну фіатну валюту."
        )

    return (
        "<b>Методи оплати</b>\n\n"
        "Оберіть фіатну валюту, до якої потрібно додати банки або способи оплати."
    )


def build_payment_options_text(
    fiat,
    existing_codes: set[str],
    *,
    prefix: str | None = None,
) -> str:
    title = f"<b>Методи оплати · {escape(fiat.code)}</b>"
    hint = "Оберіть хоча б один банк або спосіб оплати для цієї валюти."
    current = f"Додано: <b>{len(existing_codes)}</b>"

    if prefix:
        return f"{prefix}\n\n{title}\n\n{hint}\n\n{current}"

    return f"{title}\n\n{hint}\n\n{current}"


def parse_payment_fiat_callback(callback_data: str) -> int | None:
    payload = callback_data[len(CB_ADMIN_PAYMENT_FIAT_PREFIX):]

    try:
        return int(payload)
    except ValueError:
        return None


def parse_payment_method_callback(callback_data: str) -> tuple[int | None, str | None]:
    payload = callback_data[len(CB_ADMIN_PAYMENT_ADD_PREFIX):]
    parts = payload.split(":", 1)

    if len(parts) != 2:
        return None, None

    try:
        return int(parts[0]), parts[1]
    except ValueError:
        return None, None
