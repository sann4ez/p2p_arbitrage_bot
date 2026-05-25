from db.dto import (
    PERMISSION_EDIT_P2P_FILTERS,
    PERMISSION_MANAGE_CURRENCIES,
    PERMISSION_MANAGE_EXCHANGES,
    PERMISSION_MANAGE_PAYMENT_METHODS,
    PERMISSION_MANAGE_ROLES,
    PERMISSION_MANAGE_USERS,
    PERMISSION_RECEIVE_ALERTS,
    PERMISSION_RUN_SCANNER,
    PERMISSION_VIEW_ADMIN_PANEL,
    PERMISSION_VIEW_LOGS,
    PERMISSION_VIEW_P2P,
    ROLE_ADMIN,
    ROLE_SUPER_ADMIN,
    ROLE_USER,
)


SYSTEM_PERMISSIONS = [
    {
        "code": PERMISSION_VIEW_P2P,
        "name": "View P2P",
        "description": "Can use P2P menus and see exchange offers.",
    },
    {
        "code": PERMISSION_EDIT_P2P_FILTERS,
        "name": "Edit P2P filters",
        "description": "Can configure personal P2P filters.",
    },
    {
        "code": PERMISSION_RECEIVE_ALERTS,
        "name": "Receive alerts",
        "description": "Can receive arbitrage alerts.",
    },
    {
        "code": PERMISSION_VIEW_ADMIN_PANEL,
        "name": "View admin panel",
        "description": "Can open Telegram admin menus.",
    },
    {
        "code": PERMISSION_MANAGE_EXCHANGES,
        "name": "Manage exchanges",
        "description": "Can add, edit, and disable exchanges.",
    },
    {
        "code": PERMISSION_MANAGE_CURRENCIES,
        "name": "Manage currencies",
        "description": "Can add, edit, and disable fiat/crypto currencies.",
    },
    {
        "code": PERMISSION_MANAGE_PAYMENT_METHODS,
        "name": "Manage payment methods",
        "description": "Can add, edit, and disable payment methods.",
    },
    {
        "code": PERMISSION_MANAGE_USERS,
        "name": "Manage users",
        "description": "Can manage users and their access.",
    },
    {
        "code": PERMISSION_MANAGE_ROLES,
        "name": "Manage roles",
        "description": "Can manage roles and permissions.",
    },
    {
        "code": PERMISSION_RUN_SCANNER,
        "name": "Run scanner",
        "description": "Can manually run P2P scanners.",
    },
    {
        "code": PERMISSION_VIEW_LOGS,
        "name": "View logs",
        "description": "Can view service logs and diagnostics.",
    },
]

SYSTEM_ROLES = [
    {
        "code": ROLE_USER,
        "name": "User",
        "description": "Default bot user.",
        "is_system": True,
    },
    {
        "code": ROLE_ADMIN,
        "name": "Admin",
        "description": "Can manage reference data and scanners.",
        "is_system": True,
    },
    {
        "code": ROLE_SUPER_ADMIN,
        "name": "Super admin",
        "description": "Full access to users, roles, and admin tools.",
        "is_system": True,
    },
]

SYSTEM_ROLE_PERMISSIONS = {
    ROLE_USER: {
        PERMISSION_VIEW_P2P,
        PERMISSION_EDIT_P2P_FILTERS,
        PERMISSION_RECEIVE_ALERTS,
    },
    ROLE_ADMIN: {
        PERMISSION_VIEW_P2P,
        PERMISSION_EDIT_P2P_FILTERS,
        PERMISSION_RECEIVE_ALERTS,
        PERMISSION_VIEW_ADMIN_PANEL,
        PERMISSION_MANAGE_EXCHANGES,
        PERMISSION_MANAGE_CURRENCIES,
        PERMISSION_MANAGE_PAYMENT_METHODS,
        PERMISSION_RUN_SCANNER,
        PERMISSION_VIEW_LOGS,
    },
    ROLE_SUPER_ADMIN: {
        permission["code"]
        for permission in SYSTEM_PERMISSIONS
    },
}
