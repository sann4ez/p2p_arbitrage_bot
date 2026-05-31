from html import escape

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from db.base import AsyncSessionLocal
from db.dto import (
    CURRENCY_TYPE_CRYPTO,
    CURRENCY_TYPE_FIAT,
    PERMISSION_MANAGE_CURRENCIES,
    PERMISSION_MANAGE_PAYMENT_METHODS,
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
    BTN_BACK,
    BTN_LIST_CURRENCIES,
    CB_ADMIN_CURRENCIES_MENU,
    CB_ADMIN_CURRENCY_ADD_PREFIX,
    CB_ADMIN_PAYMENT_ADD_PREFIX,
    CB_ADMIN_PAYMENT_FIAT_PREFIX,
    CB_ADMIN_PAYMENT_FIATS_MENU,
    admin_currency_options_inline_kb,
    admin_currencies_kb,
    admin_payment_fiats_inline_kb,
    admin_payment_options_inline_kb,
)
from services.currency_service import CurrencyService
from services.menu_service import admin_menu_for_user, root_menu_for_user
from services.payment_method_service import PaymentMethodService

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
