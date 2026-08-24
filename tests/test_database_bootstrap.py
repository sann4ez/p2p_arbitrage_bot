import unittest
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

from config import Config
from db import bootstrap


MIGRATION_FUNCTIONS = (
    "add_p2p_filter_columns",
    "add_statistics_scope_columns",
    "add_statistics_order_amount_columns",
    "add_user_profile_columns",
    "add_recommendation_columns",
    "add_performance_indexes",
)


class DatabaseBootstrapTests(unittest.IsolatedAsyncioTestCase):
    async def test_migrations_run_when_table_creation_is_disabled(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(Config, "DB_AUTO_CREATE_TABLES", False))
            stack.enter_context(patch.object(Config, "DB_AUTO_MIGRATE_SCHEMA", True))
            migration_mocks = [
                stack.enter_context(
                    patch.object(bootstrap, name, new=AsyncMock())
                )
                for name in MIGRATION_FUNCTIONS
            ]
            seed_mock = stack.enter_context(
                patch.object(bootstrap, "seed_reference_data", new=AsyncMock())
            )

            await bootstrap.bootstrap_database()

        for migration_mock in migration_mocks:
            migration_mock.assert_awaited_once_with()

        seed_mock.assert_not_awaited()

    async def test_bootstrap_can_disable_all_schema_management(self):
        migration_mock = AsyncMock()

        with (
            patch.object(Config, "DB_AUTO_CREATE_TABLES", False),
            patch.object(Config, "DB_AUTO_MIGRATE_SCHEMA", False),
            patch.object(
                bootstrap,
                "add_statistics_order_amount_columns",
                new=migration_mock,
            ),
        ):
            await bootstrap.bootstrap_database()

        migration_mock.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
