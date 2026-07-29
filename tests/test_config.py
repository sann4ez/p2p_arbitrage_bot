import unittest

from config import normalize_database_url


class DatabaseUrlTests(unittest.TestCase):
    def test_railway_postgresql_url_uses_asyncpg_driver(self):
        self.assertEqual(
            normalize_database_url("postgresql://user:pass@host:5432/database"),
            "postgresql+asyncpg://user:pass@host:5432/database",
        )

    def test_legacy_postgres_url_uses_asyncpg_driver(self):
        self.assertEqual(
            normalize_database_url("postgres://user:pass@host:5432/database"),
            "postgresql+asyncpg://user:pass@host:5432/database",
        )

    def test_existing_asyncpg_url_is_preserved(self):
        url = "postgresql+asyncpg://user:pass@host:5432/database"
        self.assertEqual(normalize_database_url(url), url)


if __name__ == "__main__":
    unittest.main()
