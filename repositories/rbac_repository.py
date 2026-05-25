from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Permission, Role, RolePermission, UserRole
from db.seeders.rbac_defaults import (
    SYSTEM_PERMISSIONS,
    SYSTEM_ROLES,
    SYSTEM_ROLE_PERMISSIONS,
)


class RbacRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def ensure_system_roles_and_permissions(self):
        permissions = {}
        roles = {}

        for data in SYSTEM_PERMISSIONS:
            permission = await self.upsert_by_code(Permission, data)
            permissions[permission.code] = permission

        for data in SYSTEM_ROLES:
            role = await self.upsert_by_code(Role, data)
            roles[role.code] = role

        for role_code, permission_codes in SYSTEM_ROLE_PERMISSIONS.items():
            role = roles[role_code]

            for permission_code in permission_codes:
                permission = permissions[permission_code]
                await self.ensure_role_permission(role.id, permission.id)

    async def upsert_by_code(self, model, data: dict):
        item = await self.get_by_code(model, data["code"])

        if item is None:
            item = model(**data)
            self.session.add(item)
            await self.session.flush()

            return item

        for key, value in data.items():
            setattr(item, key, value)

        await self.session.flush()

        return item

    async def get_by_code(self, model, code: str):
        result = await self.session.execute(select(model).where(model.code == code))

        return result.scalar_one_or_none()

    async def ensure_role_permission(self, role_id: int, permission_id: int):
        item = await self.session.get(RolePermission, (role_id, permission_id))

        if item:
            return item

        item = RolePermission(role_id=role_id, permission_id=permission_id)

        self.session.add(item)
        await self.session.flush()

        return item

    async def ensure_user_role(self, user_id: int, role_code: str):
        await self.ensure_system_roles_and_permissions()

        role = await self.get_by_code(Role, role_code)

        if not role:
            raise ValueError(f"Unknown role: {role_code}")

        item = await self.session.get(UserRole, (user_id, role.id))

        if item:
            return item

        item = UserRole(user_id=user_id, role_id=role.id)

        self.session.add(item)
        await self.session.flush()

        return item

    async def has_permission(self, user_id: int, permission_code: str) -> bool:
        stmt = (
            select(Permission.id)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(
                UserRole.user_id == user_id,
                Permission.code == permission_code,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)

        return result.scalar_one_or_none() is not None

    async def get_user_role_codes(self, user_id: int) -> list[str]:
        stmt = (
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .order_by(Role.code)
        )
        result = await self.session.execute(stmt)

        return list(result.scalars().all())
