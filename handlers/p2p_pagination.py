from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest

from services.p2p_pagination import (
    CB_P2P_PAGE_NOOP,
    CB_P2P_PAGE_PREFIX,
    get_pagination_page_from_callback,
)


router = Router()


@router.callback_query(F.data == CB_P2P_PAGE_NOOP)
async def p2p_page_noop(callback: types.CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith(CB_P2P_PAGE_PREFIX))
async def change_p2p_page(callback: types.CallbackQuery):
    page = get_pagination_page_from_callback(
        callback.data or "",
        callback.from_user.id,
    )

    if not page:
        await callback.answer(
            "Ця сторінка вже застаріла або належить іншому користувачу. Зробіть P2P-запит ще раз.",
            show_alert=True,
        )
        return

    await callback.answer()

    if not callback.message:
        return

    try:
        await callback.message.edit_text(
            page.text,
            reply_markup=page.reply_markup,
        )
    except TelegramBadRequest as error:
        if "message is not modified" in str(error).lower():
            return

        raise
