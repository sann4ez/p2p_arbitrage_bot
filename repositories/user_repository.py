from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User


class UserRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        stmt = select(User).where(User.telegram_id == telegram_id)

        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def create(
        self,
        telegram_id: int,
        username: str | None
    ) -> User:

        user = User(
            telegram_id=telegram_id,
            username=username,
        )

        self.session.add(user)

        await self.session.commit()

        return user

    async def get_or_create(
        self,
        telegram_id: int,
        username: str | None
    ) -> User:

        user = await self.get_by_telegram_id(telegram_id)

        if user:
            return user

        return await self.create(
            telegram_id=telegram_id,
            username=username
        )