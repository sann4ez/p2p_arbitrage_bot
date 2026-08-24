import json
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


def parse_model_chain(value: str | None) -> list[str]:
    if not value:
        return []

    normalized = value.strip()

    if normalized.startswith("["):
        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError as error:
            raise ValueError("AI model chain must be a valid JSON array") from error

        if not isinstance(parsed, list) or not all(
            isinstance(item, str) for item in parsed
        ):
            raise ValueError("AI model chain must contain only model-name strings")

        return [item.strip() for item in parsed if item.strip()]

    return parse_env_list(normalized)


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def normalize_database_url(value: str) -> str:
    value = value.strip()

    if value.startswith("postgres://"):
        return f"postgresql+asyncpg://{value[len('postgres://'):]}"

    if value.startswith("postgresql://"):
        return f"postgresql+asyncpg://{value[len('postgresql://'):]}"

    return value


class Config:
    LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING").upper()
    DISPLAY_TIMEZONE = os.getenv("DISPLAY_TIMEZONE", "Europe/Kiev")
    DISPLAY_UTC_OFFSET = os.getenv("DISPLAY_UTC_OFFSET", "+03:00")
    P2P_LOG_DESCRIPTION_SNIPPETS = parse_bool(os.getenv("P2P_LOG_DESCRIPTION_SNIPPETS"))
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "")
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
    DASHSCOPE_API_BASE = os.getenv(
        "DASHSCOPE_API_BASE",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "")
    OPENAI_P2P_MODEL = os.getenv("OPENAI_P2P_MODEL", "gpt-5-nano")
    LITELLM_P2P_MODEL = os.getenv(
        "LITELLM_P2P_MODEL",
        OPENAI_P2P_MODEL,
    )
    LITELLM_P2P_FALLBACK_MODELS = parse_env_list(
        os.getenv("LITELLM_P2P_FALLBACK_MODELS")
    )
    LITELLM_P2P_MODELS = parse_model_chain(os.getenv("LITELLM_P2P_MODELS"))
    LITELLM_NUM_RETRIES = max(0, int(os.getenv("LITELLM_NUM_RETRIES", "1")))
    LITELLM_ALLOWED_FAILURES = max(
        0,
        int(os.getenv("LITELLM_ALLOWED_FAILURES", "1")),
    )
    LITELLM_COOLDOWN_SECONDS = max(
        0.0,
        float(os.getenv("LITELLM_COOLDOWN_SECONDS", "60")),
    )
    P2P_AI_CLASSIFIER_TIMEOUT = float(
        os.getenv(
            "P2P_AI_CLASSIFIER_TIMEOUT",
            os.getenv("OPENAI_P2P_CLASSIFIER_TIMEOUT", "20"),
        )
    )
    P2P_AI_CLASSIFIER_BATCH_SIZE = int(
        os.getenv(
            "P2P_AI_CLASSIFIER_BATCH_SIZE",
            os.getenv("OPENAI_P2P_CLASSIFIER_BATCH_SIZE", "10"),
        )
    )
    P2P_AI_CLASSIFIER_CONCURRENCY = int(
        os.getenv(
            "P2P_AI_CLASSIFIER_CONCURRENCY",
            os.getenv("OPENAI_P2P_CLASSIFIER_CONCURRENCY", "3"),
        )
    )
    P2P_AI_CLASSIFIER_SINGLE_BATCH = parse_bool(
        os.getenv("P2P_AI_CLASSIFIER_SINGLE_BATCH")
        or os.getenv("OPENAI_P2P_CLASSIFIER_SINGLE_BATCH"),
        True,
    )
    P2P_AI_CLASSIFICATION_CACHE_TTL_SECONDS = float(
        os.getenv(
            "P2P_AI_CLASSIFICATION_CACHE_TTL_SECONDS",
            os.getenv("OPENAI_P2P_CLASSIFICATION_CACHE_TTL_SECONDS", "864000"),
        )
    )
    P2P_AI_CLASSIFICATION_CACHE_MAX_ENTRIES = int(
        os.getenv(
            "P2P_AI_CLASSIFICATION_CACHE_MAX_ENTRIES",
            os.getenv("OPENAI_P2P_CLASSIFICATION_CACHE_MAX_ENTRIES", "1000"),
        )
    )
    P2P_AI_CLASSIFICATION_FAILURE_CACHE_TTL_SECONDS = float(
        os.getenv(
            "P2P_AI_CLASSIFICATION_FAILURE_CACHE_TTL_SECONDS",
            os.getenv(
                "OPENAI_P2P_CLASSIFICATION_FAILURE_CACHE_TTL_SECONDS",
                "0",
            ),
        )
    )
    OPENAI_VECTOR_STORE_IDS = parse_env_list(
        os.getenv("OPENAI_VECTOR_STORE_IDS") or os.getenv("OPENAI_VECTOR_STORE_ID")
    )
    OPENAI_FILE_SEARCH_MAX_RESULTS = int(os.getenv("OPENAI_FILE_SEARCH_MAX_RESULTS", "3"))
    P2P_USER_COOLDOWN_SECONDS = float(os.getenv("P2P_USER_COOLDOWN_SECONDS", "8"))
    P2P_GLOBAL_COOLDOWN_SECONDS = float(os.getenv("P2P_GLOBAL_COOLDOWN_SECONDS", "2"))
    P2P_CACHE_TTL_SECONDS = float(os.getenv("P2P_CACHE_TTL_SECONDS", "30"))
    P2P_DETAILS_CACHE_TTL_SECONDS = float(os.getenv("P2P_DETAILS_CACHE_TTL_SECONDS", "90"))
    P2P_DETAIL_FETCH_CONCURRENCY = max(
        1,
        int(os.getenv("P2P_DETAIL_FETCH_CONCURRENCY", "10")),
    )
    P2P_CACHE_MAX_ENTRIES = int(os.getenv("P2P_CACHE_MAX_ENTRIES", "1000"))
    P2P_CACHE_CLEANUP_INTERVAL_SECONDS = float(
        os.getenv("P2P_CACHE_CLEANUP_INTERVAL_SECONDS", "60")
    )
    P2P_ORDERS_PER_PAGE = int(os.getenv("P2P_ORDERS_PER_PAGE", "3"))
    P2P_PAGINATION_TTL_SECONDS = float(os.getenv("P2P_PAGINATION_TTL_SECONDS", "600"))
    P2P_PAGINATION_MAX_SESSIONS = int(os.getenv("P2P_PAGINATION_MAX_SESSIONS", "200"))
    ADMIN_ALERTS_ENABLED = parse_bool(os.getenv("ADMIN_ALERTS_ENABLED"), True)
    ADMIN_ALERT_COOLDOWN_SECONDS = float(
        os.getenv("ADMIN_ALERT_COOLDOWN_SECONDS", "900")
    )
    OKX_AUTHORIZATION = os.getenv("OKX_AUTHORIZATION", "")
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    DB_POOL_SIZE = max(1, int(os.getenv("DB_POOL_SIZE", "5")))
    DB_MAX_OVERFLOW = max(0, int(os.getenv("DB_MAX_OVERFLOW", "5")))
    DB_POOL_TIMEOUT_SECONDS = max(
        1.0,
        float(os.getenv("DB_POOL_TIMEOUT_SECONDS", "30")),
    )
    DB_POOL_RECYCLE_SECONDS = max(
        0,
        int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
    )
    DB_AUTO_CREATE_TABLES = parse_bool(os.getenv("DB_AUTO_CREATE_TABLES"), True)
    DB_AUTO_MIGRATE_SCHEMA = parse_bool(
        os.getenv("DB_AUTO_MIGRATE_SCHEMA"),
        True,
    )
    DB_AUTO_SEED_REFERENCE_DATA = parse_bool(
        os.getenv("DB_AUTO_SEED_REFERENCE_DATA"),
        True,
    )
    SUPER_ADMIN_TELEGRAM_IDS = parse_telegram_ids(os.getenv("SUPER_ADMIN_TELEGRAM_IDS"))
    P2P_KNOWLEDGE_BASE_TELEGRAM_IDS = parse_telegram_ids(
        os.getenv("P2P_KNOWLEDGE_BASE_TELEGRAM_IDS")
    )
    P2P_RECOMMENDATIONS_ENABLED = parse_bool(
        os.getenv("P2P_RECOMMENDATIONS_ENABLED"),
        True,
    )
    P2P_RECOMMENDATIONS_TELEGRAM_IDS = parse_telegram_ids(
        os.getenv("P2P_RECOMMENDATIONS_TELEGRAM_IDS")
    )
    P2P_RECOMMENDATION_MIN_INTERVAL_SECONDS = int(
        os.getenv("P2P_RECOMMENDATION_MIN_INTERVAL_SECONDS", "360")
    )
    P2P_RECOMMENDATION_MAX_INTERVAL_SECONDS = int(
        os.getenv("P2P_RECOMMENDATION_MAX_INTERVAL_SECONDS", "720")
    )
    P2P_RECOMMENDATION_MIN_HISTORY_POINTS = int(
        os.getenv("P2P_RECOMMENDATION_MIN_HISTORY_POINTS", "24")
    )
    P2P_RECOMMENDATION_SIGNAL_THRESHOLD = float(
        os.getenv("P2P_RECOMMENDATION_SIGNAL_THRESHOLD", "0.72")
    )
    P2P_RECOMMENDATION_NOTIFICATION_COOLDOWN_SECONDS = int(
        os.getenv("P2P_RECOMMENDATION_NOTIFICATION_COOLDOWN_SECONDS", "21600")
    )
    P2P_RECOMMENDATION_MAX_DATA_AGE_SECONDS = int(
        os.getenv("P2P_RECOMMENDATION_MAX_DATA_AGE_SECONDS", "1800")
    )
    P2P_RECOMMENDATION_NEWS_REFRESH_SECONDS = int(
        os.getenv("P2P_RECOMMENDATION_NEWS_REFRESH_SECONDS", "21600")
    )
    P2P_RECOMMENDATION_WEB_SEARCH_ENABLED = parse_bool(
        os.getenv("P2P_RECOMMENDATION_WEB_SEARCH_ENABLED"),
        True,
    )
    OPENAI_RECOMMENDATION_MODEL = os.getenv(
        "OPENAI_RECOMMENDATION_MODEL",
        "gpt-5.6-terra",
    )
    LITELLM_RECOMMENDATION_MODEL = os.getenv(
        "LITELLM_RECOMMENDATION_MODEL",
        OPENAI_RECOMMENDATION_MODEL,
    )
    LITELLM_RECOMMENDATION_FALLBACK_MODELS = parse_env_list(
        os.getenv("LITELLM_RECOMMENDATION_FALLBACK_MODELS")
    )
    LITELLM_RECOMMENDATION_MODELS = parse_model_chain(
        os.getenv("LITELLM_RECOMMENDATION_MODELS")
    )
    LITELLM_WEB_MODEL = os.getenv(
        "LITELLM_WEB_MODEL",
        "dashscope/qwen-plus",
    )
    LITELLM_WEB_FALLBACK_MODELS = parse_env_list(
        os.getenv("LITELLM_WEB_FALLBACK_MODELS")
    ) or [OPENAI_RECOMMENDATION_MODEL]
    LITELLM_WEB_MODELS = parse_model_chain(os.getenv("LITELLM_WEB_MODELS"))
    P2P_RECOMMENDATION_AI_REASONING_EFFORT = os.getenv(
        "P2P_RECOMMENDATION_AI_REASONING_EFFORT",
        os.getenv("OPENAI_RECOMMENDATION_REASONING_EFFORT", "high"),
    )
    P2P_RECOMMENDATION_AI_TIMEOUT = float(
        os.getenv(
            "P2P_RECOMMENDATION_AI_TIMEOUT",
            os.getenv("OPENAI_RECOMMENDATION_TIMEOUT", "120"),
        )
    )
    P2P_DETAIL_PERSISTENT_TTL_SECONDS = int(
        os.getenv("P2P_DETAIL_PERSISTENT_TTL_SECONDS", "864000")
    )
    P2P_DETAIL_REFRESH_FAILURE_RETRY_SECONDS = int(
        os.getenv("P2P_DETAIL_REFRESH_FAILURE_RETRY_SECONDS", "3600")
    )
    P2P_DETAIL_CACHE_RETENTION_DAYS = max(
        0,
        int(os.getenv("P2P_DETAIL_CACHE_RETENTION_DAYS", "14")),
    )
    P2P_DETAIL_CACHE_CLEANUP_BATCH_SIZE = max(
        1,
        int(os.getenv("P2P_DETAIL_CACHE_CLEANUP_BATCH_SIZE", "1000")),
    )
    P2P_RAW_SCAN_RETENTION_HOURS = int(
        os.getenv("P2P_RAW_SCAN_RETENTION_HOURS", "24")
    )
    SPREAD_THRESHOLD = 1.5  # мінімальний спред у %
    POLL_INTERVAL = 15      # секунд між опитуванням бірж

    DB_URL = normalize_database_url(
        DATABASE_URL or (
            f"postgresql+asyncpg://"
            f"{os.getenv('DB_USER')}:"
            f"{os.getenv('DB_PASSWORD')}@"
            f"{os.getenv('DB_HOST')}:"
            f"{os.getenv('DB_PORT')}/"
            f"{os.getenv('DB_NAME')}"
        )
    )
