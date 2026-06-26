from aiogram.fsm.state import State, StatesGroup


class P2PExchange(StatesGroup):
    binance = State()
    okx = State()


class AppMenu(StatesGroup):
    p2p_exchanges = State()
    cabinet = State()
    p2p_filters = State()
    p2p_pairs = State()
    payment_methods = State()
    statistics = State()
    statistics_period_input = State()
    knowledge_base = State()


class AdminMenu(StatesGroup):
    panel = State()
    currencies = State()
    payment_methods = State()
    statistics = State()
    statistics_banks = State()
