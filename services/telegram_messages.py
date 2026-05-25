from aiogram import types


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
