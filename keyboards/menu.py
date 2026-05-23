import os

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


BINANCE_ICON_CUSTOM_EMOJI_ID = os.getenv("BINANCE_ICON_CUSTOM_EMOJI_ID")
OKX_ICON_CUSTOM_EMOJI_ID = os.getenv("OKX_ICON_CUSTOM_EMOJI_ID")

BTN_BINANCE = "Binance" if BINANCE_ICON_CUSTOM_EMOJI_ID else "🟡 Binance"
BTN_OKX = "OKX" if OKX_ICON_CUSTOM_EMOJI_ID else "⚫ OKX"
BTN_UAH_TO_USDT = "₴ UAH → ₮ USDT"
BTN_USDT_TO_UAH = "₮ USDT → ₴ UAH"
BTN_BACK_EXCHANGES = "⬅️ Біржі"


def keyboard_button(text: str, icon_custom_emoji_id: str | None = None):
    kwargs = {"text": text}

    if icon_custom_emoji_id:
        kwargs["icon_custom_emoji_id"] = icon_custom_emoji_id

    return KeyboardButton(**kwargs)


def exchanges_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                keyboard_button(BTN_BINANCE, BINANCE_ICON_CUSTOM_EMOJI_ID),
                keyboard_button(BTN_OKX, OKX_ICON_CUSTOM_EMOJI_ID),
            ],
        ],
        resize_keyboard=True,
    )


def main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=BTN_UAH_TO_USDT),
                KeyboardButton(text=BTN_USDT_TO_UAH),
            ],
            [
                KeyboardButton(text=BTN_BACK_EXCHANGES),
            ],
        ],
        resize_keyboard=True,
    )
