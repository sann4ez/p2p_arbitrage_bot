from html import escape

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from db.base import AsyncSessionLocal
from db.dto import CURRENCY_TYPE_CRYPTO, CURRENCY_TYPE_FIAT, get_currency_option
from db.dto import PERMISSION_MANAGE_CURRENCIES, PERMISSION_VIEW_ADMIN_PANEL
from filters.permission import PermissionRequired
from fsm.states import AdminMenu
from keyboards.menu import (
    BTN_ADD_CRYPTO_CURRENCY,
    BTN_ADD_FIAT_CURRENCY,
    BTN_ADMIN_CURRENCIES,
    BTN_ADMIN_PANEL,
    BTN_BACK,
    BTN_LIST_CURRENCIES,
    CB_ADMIN_CURRENCIES_MENU,
    CB_ADMIN_CURRENCY_ADD_PREFIX,
    admin_currency_options_inline_kb,
    admin_currencies_kb,
)
from services.currency_service import CurrencyService
from services.menu_service import admin_menu_for_user, root_menu_for_user

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

    await message.answer(
        build_currencies_list_text(fiat_currencies, crypto_currencies),
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


def build_currencies_list_text(fiat_currencies: list, crypto_currencies: list) -> str:
    return "\n\n".join(
        [
            "<b>Фіатні валюти</b>\n" + format_currency_rows(fiat_currencies),
            "<b>Криптовалюти</b>\n" + format_currency_rows(crypto_currencies),
        ]
    )


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
