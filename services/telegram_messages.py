from aiogram import types

from services.p2p_pagination import (
    create_pagination_session,
    get_pagination_page,
)


TELEGRAM_SAFE_MESSAGE_LIMIT = 3800


async def send_html_blocks(
    message: types.Message,
    *,
    title: str,
    blocks: list[str],
):
    current = f"<b>{title}</b>"

    for block in blocks:
        separator = "\n\n" if current else ""
        next_text = f"{current}{separator}{block}"

        if current and len(next_text) > TELEGRAM_SAFE_MESSAGE_LIMIT:
            await message.answer(current)
            current = block
            continue

        current = next_text

    if current:
        await message.answer(current)


async def send_paginated_html_blocks(
    message: types.Message,
    *,
    title: str,
    blocks: list[str],
    page_size: int | None = None,
):
    telegram_id = message.from_user.id if message.from_user else 0
    session_id = create_pagination_session(
        owner_telegram_id=telegram_id,
        title=title,
        blocks=blocks,
        page_size=page_size,
    )
    page = get_pagination_page(
        session_id=session_id,
        page_index=0,
        telegram_id=telegram_id,
    )

    if not page:
        await send_html_blocks(message, title=title, blocks=blocks)
        return

    await message.answer(page.text, reply_markup=page.reply_markup)
