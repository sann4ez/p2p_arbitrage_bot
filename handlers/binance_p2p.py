from aiogram import Router, types
from services.binance_client import fetch_binance_p2p

router = Router()


@router.message(lambda m: m.text == "UAH → USDT")
async def uah_to_usdt(message: types.Message):
    ads = await fetch_binance_p2p(
        trade_type="BUY",
        asset="USDT",
        fiat="UAH",
        rows=5,
    )

    if not ads:
        await message.answer("Немає даних з Binance")
        return

    text = "<b>Binance P2P | Купівля USDT за UAH</b>\n\n"

    for ad in ads:
        price = ad["adv"]["price"]
        min_amt = ad["adv"]["minSingleTransAmount"]
        max_amt = ad["adv"]["dynamicMaxSingleTransAmount"]
        merchant = ad["advertiser"]["nickName"]

        text += (
            f"👤 {merchant}\n"
            f"💰 Ціна: <b>{price} UAH</b>\n"
            f"📦 Ліміт: {min_amt} – {max_amt}\n\n"
        )

    await message.answer(text)


@router.message(lambda m: m.text == "USDT → UAH")
async def usdt_to_uah(message: types.Message):
    ads = await fetch_binance_p2p(
        trade_type="SELL",
        asset="USDT",
        fiat="UAH",
        rows=5,
    )

    if not ads:
        await message.answer("Немає даних з Binance")
        return

    text = "<b>Binance P2P | Продаж USDT за UAH</b>\n\n"

    for ad in ads:
        price = ad["adv"]["price"]
        min_amt = ad["adv"]["minSingleTransAmount"]
        max_amt = ad["adv"]["dynamicMaxSingleTransAmount"]
        merchant = ad["advertiser"]["nickName"]

        text += (
            f"👤 {merchant}\n"
            f"💰 Ціна: <b>{price} UAH</b>\n"
            f"📦 Ліміт: {min_amt} – {max_amt}\n\n"
        )

    await message.answer(text)