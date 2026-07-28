from db.base import AsyncSessionLocal
from config import Config
from db.dto import (
    PERMISSION_MANAGE_CURRENCIES,
    PERMISSION_MANAGE_PAYMENT_METHODS,
    PERMISSION_RUN_SCANNER,
    PERMISSION_VIEW_ADMIN_PANEL,
)
from keyboards.menu import admin_menu_kb, root_menu_kb
from services.user_service import UserService


async def root_menu_for_user(telegram_id: int):
    async with AsyncSessionLocal() as session:
        service = UserService(session)
        can_view_admin = await service.has_permission(
            telegram_id,
            PERMISSION_VIEW_ADMIN_PANEL,
        )

    return root_menu_kb(
        can_view_admin=can_view_admin,
        can_use_knowledge_base=can_use_knowledge_base(telegram_id),
    )


def can_use_knowledge_base(telegram_id: int | None) -> bool:
    return bool(
        telegram_id
        and telegram_id in Config.P2P_KNOWLEDGE_BASE_TELEGRAM_IDS
    )


def can_use_recommendations(telegram_id: int | None) -> bool:
    return bool(
        Config.P2P_RECOMMENDATIONS_ENABLED
        and telegram_id
        and telegram_id in Config.P2P_RECOMMENDATIONS_TELEGRAM_IDS
    )


async def admin_menu_for_user(telegram_id: int):
    async with AsyncSessionLocal() as session:
        service = UserService(session)
        permissions = set(await service.get_user_permission_codes(telegram_id))

    return admin_menu_kb(
        can_manage_currencies=PERMISSION_MANAGE_CURRENCIES in permissions,
        can_manage_payment_methods=PERMISSION_MANAGE_PAYMENT_METHODS in permissions,
        can_manage_statistics=PERMISSION_RUN_SCANNER in permissions,
    )
