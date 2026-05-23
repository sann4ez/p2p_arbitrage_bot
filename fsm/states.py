from aiogram.fsm.state import State, StatesGroup


class P2PExchange(StatesGroup):
    binance = State()
    okx = State()
