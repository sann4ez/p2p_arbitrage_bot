from aiogram.fsm.state import State, StatesGroup


class P2PExchange(StatesGroup):
    binance = State()
    okx = State()


class AppMenu(StatesGroup):
    p2p_exchanges = State()
    cabinet = State()
    p2p_filters = State()


class AdminMenu(StatesGroup):
    panel = State()
    currencies = State()
