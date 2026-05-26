from db.base import AsyncSessionLocal
from db.dto import PERMISSION_MANAGE_CURRENCIES, PERMISSION_VIEW_ADMIN_PANEL
from keyboards.menu import admin_menu_kb, root_menu_kb
from services.user_service import UserService


async def root_menu_for_user(telegram_id: int):
    async with AsyncSessionLocal() as session:
        service = UserService(session)
        can_view_admin = await service.has_permission(
            telegram_id,
            PERMISSION_VIEW_ADMIN_PANEL,
        )

    return root_menu_kb(can_view_admin=can_view_admin)


async def admin_menu_for_user(telegram_id: int):
    async with AsyncSessionLocal() as session:
        service = UserService(session)
        permissions = set(await service.get_user_permission_codes(telegram_id))

    return admin_menu_kb(
        can_manage_currencies=PERMISSION_MANAGE_CURRENCIES in permissions,
    )
