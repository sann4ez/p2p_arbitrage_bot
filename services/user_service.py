from sqlalchemy.ext.asyncio import AsyncSession

from repositories.user_repository import UserRepository
from db.models import User


class UserService:

    def __init__(self, session: AsyncSession):
        self.repo = UserRepository(session)

    async def register_user(
        self,
        telegram_id: int,
        username: str | None
    ) -> User:

        return await self.repo.get_or_create(
            telegram_id=telegram_id,
            username=username
        )