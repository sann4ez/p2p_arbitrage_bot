from aiogram.filters import BaseFilter
from aiogram.types import Message

from db.base import AsyncSessionLocal
from services.user_service import UserService


class PermissionRequired(BaseFilter):

    def __init__(self, permission_code: str):
        self.permission_code = permission_code

    async def __call__(self, message: Message) -> bool:
        if not message.from_user:
            return False

        async with AsyncSessionLocal() as session:
            service = UserService(session)

            return await service.has_permission(
                telegram_id=message.from_user.id,
                permission_code=self.permission_code,
            )
