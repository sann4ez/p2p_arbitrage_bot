from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


CB_RECOMMENDATION_ACCEPT_PREFIX = "p2prec:accept:"
CB_RECOMMENDATION_SKIP_PREFIX = "p2prec:skip:"
CB_RECOMMENDATION_BANK_PREFIX = "p2prec:bank:"


def recommendation_action_kb(delivery_id: int, *, can_complete: bool):
    rows = []

    if can_complete:
        rows.append(
            [
                InlineKeyboardButton(
                    text="✅ Виконав",
                    callback_data=f"{CB_RECOMMENDATION_ACCEPT_PREFIX}{delivery_id}",
                ),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⏭ Пропустити",
                callback_data=f"{CB_RECOMMENDATION_SKIP_PREFIX}{delivery_id}",
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def recommendation_banks_kb(delivery_id: int, payment_methods):
    rows = [
        [
            InlineKeyboardButton(
                text=method.name,
                callback_data=(
                    f"{CB_RECOMMENDATION_BANK_PREFIX}"
                    f"{delivery_id}:{method.id}"
                ),
            )
        ]
        for method in payment_methods
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="⏭ Пропустити",
                callback_data=f"{CB_RECOMMENDATION_SKIP_PREFIX}{delivery_id}",
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)
