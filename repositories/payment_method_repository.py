from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import FiatCurrency, PaymentMethod


class PaymentMethodRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_payment_method(
        self,
        fiat_currency_id: int,
        code: str,
        name: str,
        category: str,
    ) -> tuple[PaymentMethod, bool]:
        item = await self.get_by_fiat_and_code(fiat_currency_id, code)

        if item is None:
            item = PaymentMethod(
                fiat_currency_id=fiat_currency_id,
                code=code,
                name=name,
                category=category,
                is_active=True,
            )
            self.session.add(item)
            await self.session.flush()

            return item, True

        item.name = name
        item.category = category
        item.is_active = True
        await self.session.flush()

        return item, False

    async def get_by_fiat_and_code(
        self,
        fiat_currency_id: int,
        code: str,
    ) -> PaymentMethod | None:
        result = await self.session.execute(
            select(PaymentMethod).where(
                PaymentMethod.fiat_currency_id == fiat_currency_id,
                PaymentMethod.code == code,
            )
        )

        return result.scalar_one_or_none()

    async def list_by_fiat(self, fiat_currency_id: int) -> list[PaymentMethod]:
        result = await self.session.execute(
            select(PaymentMethod)
            .where(PaymentMethod.fiat_currency_id == fiat_currency_id)
            .order_by(PaymentMethod.category, PaymentMethod.name)
        )

        return list(result.scalars().all())

    async def list_all_with_fiat(self) -> list[tuple[PaymentMethod, FiatCurrency]]:
        result = await self.session.execute(
            select(PaymentMethod, FiatCurrency)
            .join(FiatCurrency, FiatCurrency.id == PaymentMethod.fiat_currency_id)
            .order_by(FiatCurrency.code, PaymentMethod.category, PaymentMethod.name)
        )

        return list(result.all())

    async def list_active(self) -> list[PaymentMethod]:
        result = await self.session.execute(
            select(PaymentMethod)
            .where(PaymentMethod.is_active.is_(True))
            .order_by(PaymentMethod.category, PaymentMethod.name)
        )

        return list(result.scalars().all())
