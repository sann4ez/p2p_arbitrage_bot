from sqlalchemy import select

from db.base import AsyncSessionLocal
from db.models import CryptoCurrency, Exchange, FiatCurrency, PaymentMethod
from repositories.rbac_repository import RbacRepository


EXCHANGES = [
    {"code": "BINANCE", "name": "Binance"},
    {"code": "OKX", "name": "OKX"},
]

FIAT_CURRENCIES = [
    {"code": "UAH", "name": "Ukrainian hryvnia"},
]

CRYPTO_CURRENCIES = [
    {"code": "USDT", "name": "Tether USD"},
]

UAH_PAYMENT_METHODS = [
    {"code": "MONOBANK", "name": "Monobank", "category": "person"},
    {"code": "PRIVATBANK", "name": "PrivatBank", "category": "person"},
    {"code": "PUMB", "name": "PUMB", "category": "person"},
    {"code": "A_BANK", "name": "A-Bank", "category": "person"},
    {"code": "RAIFFEISEN_BANK", "name": "Raiffeisen Bank", "category": "person"},
    {"code": "SENSE_SUPERAPP", "name": "Sense SuperApp", "category": "person"},
    {"code": "IZIBANK", "name": "Izibank", "category": "person"},
    {"code": "OTP_BANK", "name": "OTP Bank", "category": "person"},
    {"code": "KREDOBANK", "name": "KredoBank", "category": "person"},
    {"code": "OSCHAD_BANK", "name": "Oschad Bank", "category": "person"},
    {"code": "TASCOMBANK", "name": "Tascombank", "category": "person"},
    {"code": "IBAN", "name": "IBAN", "category": "fop"},
    {"code": "FOP", "name": "FOP account", "category": "fop"},
    {"code": "BANK_TRANSFER", "name": "Bank transfer", "category": "other"},
    {"code": "WESTERN_UNION", "name": "Western Union", "category": "other"},
]


async def seed_reference_data():
    async with AsyncSessionLocal() as session:
        rbac_repo = RbacRepository(session)
        await rbac_repo.ensure_system_roles_and_permissions()

        for item in EXCHANGES:
            await upsert_by_code(session, Exchange, item)

        for item in FIAT_CURRENCIES:
            await upsert_by_code(session, FiatCurrency, item)

        for item in CRYPTO_CURRENCIES:
            await upsert_by_code(session, CryptoCurrency, item)

        uah = await get_by_code(session, FiatCurrency, "UAH")

        for item in UAH_PAYMENT_METHODS:
            await upsert_payment_method(session, uah.id, item)

        await session.commit()


async def upsert_by_code(session, model, data: dict):
    item = await get_by_code(session, model, data["code"])

    if item is None:
        session.add(model(**data))
        return

    for key, value in data.items():
        setattr(item, key, value)


async def get_by_code(session, model, code: str):
    result = await session.execute(select(model).where(model.code == code))

    return result.scalar_one_or_none()


async def upsert_payment_method(session, fiat_currency_id: int, data: dict):
    result = await session.execute(
        select(PaymentMethod).where(
            PaymentMethod.fiat_currency_id == fiat_currency_id,
            PaymentMethod.code == data["code"],
        )
    )
    item = result.scalar_one_or_none()

    if item is None:
        session.add(PaymentMethod(fiat_currency_id=fiat_currency_id, **data))
        return

    for key, value in data.items():
        setattr(item, key, value)
