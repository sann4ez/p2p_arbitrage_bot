import os
from dotenv import load_dotenv

load_dotenv()


def parse_telegram_ids(value: str | None) -> set[int]:
    ids = set()

    if not value:
        return ids

    for item in value.split(","):
        item = item.strip()

        if not item:
            continue

        try:
            ids.add(int(item))
        except ValueError:
            continue

    return ids


def parse_env_list(value: str | None) -> list[str]:
    if not value:
        return []

    return [item.strip() for item in value.split(",") if item.strip()]


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


class Config:
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    P2P_LOG_DESCRIPTION_SNIPPETS = parse_bool(os.getenv("P2P_LOG_DESCRIPTION_SNIPPETS"))
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_P2P_MODEL = os.getenv("OPENAI_P2P_MODEL", "gpt-5-nano")
    OPENAI_P2P_CLASSIFIER_TIMEOUT = float(os.getenv("OPENAI_P2P_CLASSIFIER_TIMEOUT", "20"))
    OPENAI_P2P_CLASSIFIER_BATCH_SIZE = int(
        os.getenv("OPENAI_P2P_CLASSIFIER_BATCH_SIZE", "10")
    )
    OPENAI_P2P_CLASSIFIER_CONCURRENCY = int(
        os.getenv("OPENAI_P2P_CLASSIFIER_CONCURRENCY", "3")
    )
    OPENAI_P2P_CLASSIFIER_SINGLE_BATCH = parse_bool(
        os.getenv("OPENAI_P2P_CLASSIFIER_SINGLE_BATCH"),
        True,
    )
    OPENAI_P2P_CLASSIFICATION_CACHE_TTL_SECONDS = float(
        os.getenv("OPENAI_P2P_CLASSIFICATION_CACHE_TTL_SECONDS", "600")
    )
    OPENAI_VECTOR_STORE_IDS = parse_env_list(
        os.getenv("OPENAI_VECTOR_STORE_IDS") or os.getenv("OPENAI_VECTOR_STORE_ID")
    )
    OPENAI_FILE_SEARCH_MAX_RESULTS = int(os.getenv("OPENAI_FILE_SEARCH_MAX_RESULTS", "3"))
    P2P_USER_COOLDOWN_SECONDS = float(os.getenv("P2P_USER_COOLDOWN_SECONDS", "8"))
    P2P_GLOBAL_COOLDOWN_SECONDS = float(os.getenv("P2P_GLOBAL_COOLDOWN_SECONDS", "2"))
    P2P_CACHE_TTL_SECONDS = float(os.getenv("P2P_CACHE_TTL_SECONDS", "30"))
    P2P_DETAILS_CACHE_TTL_SECONDS = float(os.getenv("P2P_DETAILS_CACHE_TTL_SECONDS", "90"))
    P2P_ORDERS_PER_PAGE = int(os.getenv("P2P_ORDERS_PER_PAGE", "3"))
    P2P_PAGINATION_TTL_SECONDS = float(os.getenv("P2P_PAGINATION_TTL_SECONDS", "600"))
    OKX_AUTHORIZATION = os.getenv("OKX_AUTHORIZATION", "")
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    DB_AUTO_CREATE_TABLES = parse_bool(os.getenv("DB_AUTO_CREATE_TABLES"), True)
    DB_AUTO_SEED_REFERENCE_DATA = parse_bool(
        os.getenv("DB_AUTO_SEED_REFERENCE_DATA"),
        True,
    )
    SUPER_ADMIN_TELEGRAM_IDS = parse_telegram_ids(os.getenv("SUPER_ADMIN_TELEGRAM_IDS"))
    SPREAD_THRESHOLD = 1.5  # мінімальний спред у %
    POLL_INTERVAL = 15      # секунд між опитуванням бірж

    DB_URL = DATABASE_URL or (
        f"postgresql+asyncpg://"
        f"{os.getenv('DB_USER')}:"
        f"{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}:"
        f"{os.getenv('DB_PORT')}/"
        f"{os.getenv('DB_NAME')}"
    )
