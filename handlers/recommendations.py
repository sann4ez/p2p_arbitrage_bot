from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from db.base import AsyncSessionLocal
from fsm.states import AppMenu
from keyboards.menu import BTN_P2P_RECOMMENDATIONS, cabinet_kb
from keyboards.recommendations import (
    CB_RECOMMENDATION_ACCEPT_PREFIX,
    CB_RECOMMENDATION_BANK_PREFIX,
    CB_RECOMMENDATION_SKIP_PREFIX,
    recommendation_banks_kb,
)
from services.menu_service import can_use_recommendations
from services.p2p_recommendation_delivery import P2PRecommendationDeliveryService
from services.user_service import UserService


router = Router()


@router.message(F.text == BTN_P2P_RECOMMENDATIONS)
async def toggle_recommendations(message: types.Message, state: FSMContext):
    if not message.from_user or not can_use_recommendations(message.from_user.id):
        await message.answer("Цей функціонал недоступний для вашого акаунта.")
        return

    async with AsyncSessionLocal() as session:
        enabled = await UserService(session).toggle_recommendations(
            message.from_user.id,
        )

    await state.set_state(AppMenu.cabinet)
    status = "увімкнено" if enabled else "вимкнено"
    await message.answer(
        f"AI-рекомендації: <b>{status}</b>.",
        reply_markup=cabinet_kb(message.from_user.id),
    )


@router.callback_query(F.data.startswith(CB_RECOMMENDATION_ACCEPT_PREFIX))
async def choose_recommendation_bank(callback: types.CallbackQuery):
    delivery_id = parse_int(callback.data, CB_RECOMMENDATION_ACCEPT_PREFIX)

    if delivery_id is None or not callback.from_user:
        await callback.answer("Некоректна рекомендація.", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        result = await P2PRecommendationDeliveryService(session).get_bank_choices(
            delivery_id,
            callback.from_user.id,
        )

    if not result.methods:
        await callback.answer(result.message, show_alert=True)
        return

    if callback.message:
        await callback.message.edit_reply_markup(
            reply_markup=recommendation_banks_kb(delivery_id, result.methods),
        )

    await callback.answer(result.message)


@router.callback_query(F.data.startswith(CB_RECOMMENDATION_BANK_PREFIX))
async def complete_recommendation(callback: types.CallbackQuery):
    values = parse_int_pair(callback.data, CB_RECOMMENDATION_BANK_PREFIX)

    if values is None or not callback.from_user:
        await callback.answer("Некоректний банк.", show_alert=True)
        return

    delivery_id, payment_method_id = values

    async with AsyncSessionLocal() as session:
        result = await P2PRecommendationDeliveryService(session).mark_completed(
            delivery_id,
            payment_method_id,
            callback.from_user.id,
        )

    if result.ok and callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)

    await callback.answer(result.message, show_alert=not result.ok)


@router.callback_query(F.data.startswith(CB_RECOMMENDATION_SKIP_PREFIX))
async def skip_recommendation(callback: types.CallbackQuery):
    delivery_id = parse_int(callback.data, CB_RECOMMENDATION_SKIP_PREFIX)

    if delivery_id is None or not callback.from_user:
        await callback.answer("Некоректна рекомендація.", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        result = await P2PRecommendationDeliveryService(session).mark_skipped(
            delivery_id,
            callback.from_user.id,
        )

    if result.ok and callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)

    await callback.answer(result.message, show_alert=not result.ok)


def parse_int(value: str | None, prefix: str) -> int | None:
    try:
        return int((value or "")[len(prefix):])
    except (TypeError, ValueError):
        return None


def parse_int_pair(value: str | None, prefix: str) -> tuple[int, int] | None:
    try:
        first, second = (value or "")[len(prefix):].split(":", 1)
        return int(first), int(second)
    except (TypeError, ValueError):
        return None
