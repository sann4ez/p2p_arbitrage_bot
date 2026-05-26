from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, UserSettings


class UserRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        stmt = select(User).where(User.telegram_id == telegram_id)

        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_settings_by_user_id(self, user_id: int) -> UserSettings | None:
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)

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
        await self.session.flush()

        return user

    async def ensure_settings(self, user_id: int) -> UserSettings:
        settings = await self.get_settings_by_user_id(user_id)

        if settings:
            return settings

        settings = UserSettings(user_id=user_id)

        self.session.add(settings)
        await self.session.flush()

        return settings

    async def get_or_create(
        self,
        telegram_id: int,
        username: str | None
    ) -> User:

        user = await self.get_by_telegram_id(telegram_id)

        if user:
            if user.username != username:
                user.username = username

            await self.ensure_settings(user.id)
            await self.session.commit()

            return user

        user = await self.create(
            telegram_id=telegram_id,
            username=username
        )

        await self.ensure_settings(user.id)
        await self.session.commit()

        return user
