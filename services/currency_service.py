import re

from sqlalchemy.ext.asyncio import AsyncSession

from db.dto import CURRENCY_TYPE_CRYPTO, CURRENCY_TYPE_FIAT, CurrencyUpsertResult
from repositories.currency_repository import CurrencyRepository


CODE_PATTERN = re.compile(r"^[A-Z0-9]{2,10}$")


class CurrencyService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CurrencyRepository(session)

    async def upsert_currency(
        self,
        currency_type: str,
        code: str,
        name: str,
    ) -> CurrencyUpsertResult:
        code = normalize_currency_code(code)
        name = normalize_currency_name(name)

        if currency_type == CURRENCY_TYPE_FIAT:
            currency, created = await self.repo.upsert_fiat_currency(code, name)
        elif currency_type == CURRENCY_TYPE_CRYPTO:
            currency, created = await self.repo.upsert_crypto_currency(code, name)
        else:
            raise ValueError("Невідомий тип валюти.")

        await self.session.commit()

        return CurrencyUpsertResult(
            currency_type=currency_type,
            code=currency.code,
            name=currency.name,
            created=created,
        )

    async def list_currencies(self) -> tuple[list, list]:
        return (
            await self.repo.list_fiat_currencies(),
            await self.repo.list_crypto_currencies(),
        )


def normalize_currency_code(value: str) -> str:
    code = " ".join(str(value).split()).upper()

    if not CODE_PATTERN.fullmatch(code):
        raise ValueError("Код має містити 2-10 латинських літер або цифр, наприклад UAH чи USDT.")

    return code


def normalize_currency_name(value: str) -> str:
    name = " ".join(str(value).split())

    if not 2 <= len(name) <= 50:
        raise ValueError("Назва має містити від 2 до 50 символів.")

    return name
