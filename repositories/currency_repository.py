from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import CryptoCurrency, FiatCurrency


class CurrencyRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_fiat_currency(self, code: str, name: str) -> tuple[FiatCurrency, bool]:
        return await self.upsert_by_code(FiatCurrency, code, name)

    async def upsert_crypto_currency(
        self,
        code: str,
        name: str,
    ) -> tuple[CryptoCurrency, bool]:
        return await self.upsert_by_code(CryptoCurrency, code, name)

    async def upsert_by_code(self, model, code: str, name: str):
        item = await self.get_by_code(model, code)

        if item is None:
            item = model(code=code, name=name)
            self.session.add(item)
            await self.session.flush()

            return item, True

        item.name = name
        await self.session.flush()

        return item, False

    async def list_fiat_currencies(self) -> list[FiatCurrency]:
        return await self.list_by_code(FiatCurrency)

    async def list_crypto_currencies(self) -> list[CryptoCurrency]:
        return await self.list_by_code(CryptoCurrency)

    async def list_by_code(self, model):
        result = await self.session.execute(select(model).order_by(model.code))

        return list(result.scalars().all())

    async def get_by_code(self, model, code: str):
        result = await self.session.execute(select(model).where(model.code == code))

        return result.scalar_one_or_none()
