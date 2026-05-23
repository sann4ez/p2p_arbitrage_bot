from html import escape

from aiogram import F, Router, types
from aiogram.filters import StateFilter

from fsm.states import P2PExchange
from keyboards.menu import BTN_UAH_TO_USDT, BTN_USDT_TO_UAH
from services.binance_client import fetch_binance_p2p

router = Router()


@router.message(StateFilter(P2PExchange.binance), F.text == BTN_UAH_TO_USDT)
async def uah_to_usdt(message: types.Message):
    await send_binance_ads(
        message=message,
        trade_type="BUY",
        title="Binance P2P | Купівля USDT за UAH",
    )


@router.message(StateFilter(P2PExchange.binance), F.text == BTN_USDT_TO_UAH)
async def usdt_to_uah(message: types.Message):
    await send_binance_ads(
        message=message,
        trade_type="SELL",
        title="Binance P2P | Продаж USDT за UAH",
    )


async def send_binance_ads(
    *,
    message: types.Message,
    trade_type: str,
    title: str,
):
    ads = await fetch_binance_p2p(
        trade_type=trade_type,
        asset="USDT",
        fiat="UAH",
        rows=5,
    )

    if not ads:
        await message.answer("Немає даних з Binance")
        return

    text = f"<b>{title}</b>\n\n"

    for ad in ads:
        adv = ad.get("adv", {})
        advertiser = ad.get("advertiser", {})

        price = adv.get("price")
        min_amt = adv.get("minSingleTransAmount")
        max_amt = adv.get("dynamicMaxSingleTransAmount")
        merchant = advertiser.get("nickName", "Невідомий мерчант")
        available = adv.get("tradableQuantity") or adv.get("surplusAmount")
        payment_methods = format_binance_payment_methods(adv.get("tradeMethods", []))
        orders_count = advertiser.get("monthOrderCount") or advertiser.get("orderCount")
        rating = format_percent(advertiser.get("positiveRate"))
        completion_rate = format_percent(advertiser.get("monthFinishRate"))
        trade_minutes = adv.get("payTimeLimit")

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

        if completion_rate:
            lines.append(f"✅ Виконання: {completion_rate}")

        if trade_minutes:
            lines.append(f"⏱ Час угоди: {trade_minutes} хв")

        text += "\n".join(lines) + "\n\n"

    await message.answer(text)


def format_binance_payment_methods(methods: list[dict]) -> str:
    names = []

    for method in methods[:3]:
        name = (
            method.get("tradeMethodShortName")
            or method.get("tradeMethodName")
            or method.get("identifier")
            or method.get("payType")
        )

        if name:
            names.append(str(name))

    return ", ".join(names)


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
