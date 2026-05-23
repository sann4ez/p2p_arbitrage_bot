from html import escape

from aiogram import F, Router, types
from aiogram.filters import StateFilter

from fsm.states import P2PExchange
from keyboards.menu import BTN_UAH_TO_USDT, BTN_USDT_TO_UAH
from services.okx_client import fetch_okx_p2p

router = Router()


@router.message(StateFilter(P2PExchange.okx), F.text == BTN_UAH_TO_USDT)
async def uah_to_usdt(message: types.Message):
    await send_okx_ads(
        message=message,
        side="sell",
        title="OKX P2P | Купівля USDT за UAH",
    )


@router.message(StateFilter(P2PExchange.okx), F.text == BTN_USDT_TO_UAH)
async def usdt_to_uah(message: types.Message):
    await send_okx_ads(
        message=message,
        side="buy",
        title="OKX P2P | Продаж USDT за UAH",
    )


async def send_okx_ads(
    *,
    message: types.Message,
    side: str,
    title: str,
):
    ads = await fetch_okx_p2p(
        side=side,
        asset="USDT",
        fiat="UAH",
        rows=5,
    )

    if not ads:
        await message.answer("Немає даних з OKX")
        return

    text = f"<b>{title}</b>\n\n"

    for ad in ads:
        price = ad.get("price")
        min_amt = ad.get("quoteMinAmountPerOrder")
        max_amt = ad.get("quoteMaxAmountPerOrder")
        merchant = ad.get("nickName", "Невідомий мерчант")
        available = ad.get("availableAmount")
        payment_methods = ", ".join(ad.get("paymentMethods", [])[:3])
        orders_count = ad.get("completedOrderQuantity")
        rating = format_okx_rating(ad)
        completion_rate = format_percent(ad.get("completedRate"))
        trade_minutes = ad.get("paymentTimeoutMinutes")

        lines = [
            f"👤 {escape(str(merchant))}",
            f"💰 Ціна: <b>{price} UAH</b>",
            f"📦 Ліміт: {min_amt} – {max_amt}",
        ]

        if payment_methods:
            lines.append(f"🏦 Оплата: {escape(payment_methods)}")

        if available:
            lines.append(f"💵 Доступно: {available} USDT")

        if orders_count is not None:
            lines.append(f"📊 Угоди: {orders_count}")

        if rating:
            lines.append(f"⭐ Оцінка: {rating}")

        if completion_rate and completion_rate != rating:
            lines.append(f"✅ Виконання: {completion_rate}")

        if trade_minutes:
            lines.append(f"⏱ Час угоди: {trade_minutes} хв")

        text += "\n".join(lines) + "\n\n"

    await message.answer(text)


def format_okx_rating(ad: dict) -> str | None:
    positive_rating = format_percent(ad.get("posReviewPercentage"))

    if positive_rating:
        return positive_rating

    return format_percent(ad.get("completedRate"))


def format_percent(value) -> str | None:
    if value in (None, "", -1, "-1"):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    if number <= 1:
        number *= 100

    return f"{number:.2f}".rstrip("0").rstrip(".") + "%"
