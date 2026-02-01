from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="UAH → USDT"),
                KeyboardButton(text="USDT → UAH"),
            ],
        ],
        resize_keyboard=True,
    )