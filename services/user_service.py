from sqlalchemy.ext.asyncio import AsyncSession

from config import Config
from db.dto import ROLE_SUPER_ADMIN, ROLE_USER
from repositories.rbac_repository import RbacRepository
from repositories.user_repository import UserRepository
from db.models import User


class UserService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = UserRepository(session)
        self.rbac_repo = RbacRepository(session)

    async def register_user(
        self,
        telegram_id: int,
        username: str | None
    ) -> User:

        user = await self.repo.get_or_create(
            telegram_id=telegram_id,
            username=username
        )

        role_code = self.get_default_role_code(telegram_id)
        await self.rbac_repo.ensure_user_role(user.id, role_code)
        await self.session.commit()

        return user

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        return await self.repo.get_by_telegram_id(telegram_id)

    async def has_permission(self, telegram_id: int, permission_code: str) -> bool:
        user = await self.get_user_by_telegram_id(telegram_id)

        if not user:
            return False

        return await self.rbac_repo.has_permission(user.id, permission_code)

    async def get_user_role_codes(self, telegram_id: int) -> list[str]:
        user = await self.get_user_by_telegram_id(telegram_id)

        if not user:
            return []

        return await self.rbac_repo.get_user_role_codes(user.id)

    def get_default_role_code(self, telegram_id: int) -> str:
        if telegram_id in Config.SUPER_ADMIN_TELEGRAM_IDS:
            return ROLE_SUPER_ADMIN

        return ROLE_USER
