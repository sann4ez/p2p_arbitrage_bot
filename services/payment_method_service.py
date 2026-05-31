from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.dto import (
    PaymentMethodOption,
    PaymentMethodUpsertResult,
    UserPaymentMethodOption,
    UserPaymentMethodToggleResult,
)
from db.models import FiatCurrency, PaymentMethod, UserPaymentMethod
from repositories.currency_repository import CurrencyRepository
from repositories.payment_method_repository import PaymentMethodRepository
from repositories.user_repository import UserRepository
from services import p2p_filters


class PaymentMethodService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.currency_repo = CurrencyRepository(session)
        self.repo = PaymentMethodRepository(session)
        self.user_repo = UserRepository(session)

    async def list_fiat_currencies(self) -> list[FiatCurrency]:
        return await self.currency_repo.list_fiat_currencies()

    async def get_fiat_by_id(self, fiat_currency_id: int) -> FiatCurrency | None:
        return await self.session.get(FiatCurrency, fiat_currency_id)

    async def get_fiat_by_code(self, code: str) -> FiatCurrency | None:
        return await self.currency_repo.get_by_code(FiatCurrency, code)

    async def list_for_fiat(self, fiat_currency_id: int) -> list[PaymentMethod]:
        return await self.repo.list_by_fiat(fiat_currency_id)

    async def list_all_grouped(self) -> list[tuple[FiatCurrency, list[PaymentMethod]]]:
        fiat_currencies = await self.list_fiat_currencies()
        result = []

        for fiat in fiat_currencies:
            result.append((fiat, await self.list_for_fiat(fiat.id)))

        return result

    async def get_existing_codes(self, fiat_currency_id: int) -> set[str]:
        methods = await self.list_for_fiat(fiat_currency_id)

        return {method.code for method in methods}

    async def upsert_method(
        self,
        fiat_currency_id: int,
        option: PaymentMethodOption,
    ) -> PaymentMethodUpsertResult:
        fiat = await self.get_fiat_by_id(fiat_currency_id)

        if not fiat:
            raise ValueError("Фіатна валюта не знайдена.")

        method, created = await self.repo.upsert_payment_method(
            fiat.id,
            option.code,
            option.name,
            option.category,
        )
        await self.session.commit()
        await self.sync_filter_keywords()

        return PaymentMethodUpsertResult(
            fiat_code=fiat.code,
            code=method.code,
            name=method.name,
            category=method.category or "",
            created=created,
        )

    async def sync_filter_keywords(self):
        methods = await self.repo.list_active()
        p2p_filters.set_extra_payment_method_keywords(methods)

    async def list_user_methods_for_fiat(
        self,
        telegram_id: int,
        fiat_currency_id: int,
    ) -> list[UserPaymentMethodOption]:
        user = await self.user_repo.get_by_telegram_id(telegram_id)

        if not user:
            return []

        fiat = await self.get_fiat_by_id(fiat_currency_id)

        if not fiat:
            return []

        methods = [
            method
            for method in await self.list_for_fiat(fiat.id)
            if method.is_active
        ]
        selected_ids = await self.get_user_selected_method_ids(user.id)

        return [
            UserPaymentMethodOption(
                payment_method_id=method.id,
                fiat_currency_id=fiat.id,
                fiat_code=fiat.code,
                code=method.code,
                name=method.name,
                category=method.category,
                is_selected=method.id in selected_ids,
            )
            for method in methods
        ]

    async def toggle_user_method(
        self,
        telegram_id: int,
        payment_method_id: int,
    ) -> UserPaymentMethodToggleResult:
        user = await self.user_repo.get_by_telegram_id(telegram_id)

        if not user:
            return UserPaymentMethodToggleResult(
                methods=[],
                changed=False,
                message="Профіль ще не створено. Натисніть /start.",
            )

        method = await self.session.get(PaymentMethod, payment_method_id)

        if not method or not method.is_active:
            return UserPaymentMethodToggleResult(
                methods=[],
                changed=False,
                message="Метод оплати вже недоступний.",
            )

        selected = await self.get_user_payment_method(user.id, method.id)

        if selected:
            await self.session.delete(selected)
            await self.session.commit()
            message = "Банк вимкнено"
        else:
            self.session.add(
                UserPaymentMethod(
                    user_id=user.id,
                    payment_method_id=method.id,
                )
            )
            await self.session.commit()
            message = "Банк увімкнено"

        return UserPaymentMethodToggleResult(
            methods=await self.list_user_methods_for_fiat(
                telegram_id,
                method.fiat_currency_id,
            ),
            message=message,
        )

    async def list_user_selected_methods_for_fiat_code(
        self,
        telegram_id: int,
        fiat_code: str,
    ) -> list[PaymentMethod]:
        user = await self.user_repo.get_by_telegram_id(telegram_id)

        if not user:
            return []

        fiat = await self.get_fiat_by_code(fiat_code)

        if not fiat:
            return []

        selected_ids = await self.get_user_selected_method_ids(user.id)

        if not selected_ids:
            return []

        methods = [
            method
            for method in await self.list_for_fiat(fiat.id)
            if method.is_active
        ]

        return [method for method in methods if method.id in selected_ids]

    async def get_user_selected_method_ids(self, user_id: int) -> set[int]:
        result = await self.session.execute(
            select(UserPaymentMethod.payment_method_id)
            .where(UserPaymentMethod.user_id == user_id)
        )

        return set(result.scalars().all())

    async def get_user_payment_method(
        self,
        user_id: int,
        payment_method_id: int,
    ) -> UserPaymentMethod | None:
        result = await self.session.execute(
            select(UserPaymentMethod).where(
                UserPaymentMethod.user_id == user_id,
                UserPaymentMethod.payment_method_id == payment_method_id,
            )
        )

        return result.scalar_one_or_none()
