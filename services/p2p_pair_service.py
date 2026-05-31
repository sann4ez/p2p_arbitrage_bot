from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.dto import P2PUserPair
from db.models import CryptoCurrency, FiatCurrency, UserPair
from repositories.user_repository import UserRepository


@dataclass
class P2PPairToggleResult:
    pairs: list[P2PUserPair]
    changed: bool = True
    message: str = "Оновлено"


class P2PPairService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)

    async def list_available_pairs(self, telegram_id: int) -> list[P2PUserPair]:
        user = await self.user_repo.get_by_telegram_id(telegram_id)

        if not user:
            return []

        crypto_currencies = await self.list_crypto_currencies()
        fiat_currencies = await self.list_fiat_currencies()

        if not crypto_currencies or not fiat_currencies:
            return []

        await self.ensure_default_pair(user.id, crypto_currencies, fiat_currencies)
        selected_pairs = await self.get_selected_pair_ids(user.id)

        return [
            P2PUserPair(
                crypto_currency_id=crypto.id,
                fiat_currency_id=fiat.id,
                crypto_code=crypto.code,
                fiat_code=fiat.code,
                is_selected=(crypto.id, fiat.id) in selected_pairs,
            )
            for crypto in crypto_currencies
            for fiat in fiat_currencies
        ]

    async def list_selected_pairs(self, telegram_id: int) -> list[P2PUserPair]:
        pairs = await self.list_available_pairs(telegram_id)

        return [pair for pair in pairs if pair.is_selected]

    async def toggle_pair(
        self,
        telegram_id: int,
        crypto_currency_id: int,
        fiat_currency_id: int,
    ) -> P2PPairToggleResult:
        user = await self.user_repo.get_by_telegram_id(telegram_id)

        if not user:
            return P2PPairToggleResult(
                pairs=[],
                changed=False,
                message="Профіль ще не створено. Натисніть /start.",
            )

        if not await self.pair_exists(crypto_currency_id, fiat_currency_id):
            return P2PPairToggleResult(
                pairs=await self.list_available_pairs(telegram_id),
                changed=False,
                message="Пара вже недоступна.",
            )

        selected_pairs = await self.get_selected_pair_ids(user.id)
        pair_id = (crypto_currency_id, fiat_currency_id)

        if pair_id in selected_pairs:
            if len(selected_pairs) <= 1:
                return P2PPairToggleResult(
                    pairs=await self.list_available_pairs(telegram_id),
                    changed=False,
                    message="Має залишитись хоча б одна P2P пара.",
                )

            await self.remove_user_pair(user.id, crypto_currency_id, fiat_currency_id)
            await self.session.commit()

            return P2PPairToggleResult(
                pairs=await self.list_available_pairs(telegram_id),
                message="Пару вимкнено",
            )

        self.session.add(
            UserPair(
                user_id=user.id,
                crypto_currency_id=crypto_currency_id,
                fiat_currency_id=fiat_currency_id,
            )
        )
        await self.session.commit()

        return P2PPairToggleResult(
            pairs=await self.list_available_pairs(telegram_id),
            message="Пару увімкнено",
        )

    async def ensure_default_pair(
        self,
        user_id: int,
        crypto_currencies: list[CryptoCurrency],
        fiat_currencies: list[FiatCurrency],
    ):
        if await self.get_selected_pair_ids(user_id):
            return

        crypto = find_currency_by_code(crypto_currencies, "USDT") or crypto_currencies[0]
        fiat = find_currency_by_code(fiat_currencies, "UAH") or fiat_currencies[0]

        self.session.add(
            UserPair(
                user_id=user_id,
                crypto_currency_id=crypto.id,
                fiat_currency_id=fiat.id,
            )
        )
        await self.session.commit()

    async def list_crypto_currencies(self) -> list[CryptoCurrency]:
        result = await self.session.execute(select(CryptoCurrency).order_by(CryptoCurrency.code))

        return list(result.scalars().all())

    async def list_fiat_currencies(self) -> list[FiatCurrency]:
        result = await self.session.execute(select(FiatCurrency).order_by(FiatCurrency.code))

        return list(result.scalars().all())

    async def get_selected_pair_ids(self, user_id: int) -> set[tuple[int, int]]:
        result = await self.session.execute(
            select(UserPair.crypto_currency_id, UserPair.fiat_currency_id)
            .where(UserPair.user_id == user_id)
        )

        return {
            (crypto_currency_id, fiat_currency_id)
            for crypto_currency_id, fiat_currency_id in result.all()
        }

    async def pair_exists(self, crypto_currency_id: int, fiat_currency_id: int) -> bool:
        crypto = await self.session.get(CryptoCurrency, crypto_currency_id)
        fiat = await self.session.get(FiatCurrency, fiat_currency_id)

        return bool(crypto and fiat)

    async def remove_user_pair(
        self,
        user_id: int,
        crypto_currency_id: int,
        fiat_currency_id: int,
    ):
        await self.session.execute(
            delete(UserPair)
            .where(UserPair.user_id == user_id)
            .where(UserPair.crypto_currency_id == crypto_currency_id)
            .where(UserPair.fiat_currency_id == fiat_currency_id)
        )


def find_currency_by_code(currencies, code: str):
    return next((currency for currency in currencies if currency.code == code), None)


def format_pairs_summary(pairs: list[P2PUserPair]) -> str:
    if not pairs:
        return "немає"

    grouped = {}

    for pair in pairs:
        grouped.setdefault(pair.crypto_code, []).append(pair.fiat_code)

    return "; ".join(
        f"{crypto_code}: {', '.join(fiat_codes)}"
        for crypto_code, fiat_codes in grouped.items()
    )
