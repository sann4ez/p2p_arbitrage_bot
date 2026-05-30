import asyncio
import copy
import json
import logging
import time
from dataclasses import dataclass

import aiohttp

from config import Config
from db.dto import P2PDescriptionClassification


logger = logging.getLogger(__name__)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_P2P_MODEL = "gpt-5-nano"
DEFAULT_OPENAI_P2P_CLASSIFIER_TIMEOUT = 20
DEFAULT_OPENAI_P2P_CLASSIFIER_BATCH_SIZE = 10
DEFAULT_OPENAI_P2P_CLASSIFIER_CONCURRENCY = 3
DEFAULT_OPENAI_P2P_CLASSIFIER_SINGLE_BATCH = True
DEFAULT_OPENAI_FILE_SEARCH_MAX_RESULTS = 3
MAX_DESCRIPTION_CHARS = 2000
P2P_CLASSIFIER_INSTRUCTIONS = (
    "Classify three P2P description risks: split payments, third-party payments, "
    "and Monobank jar/banka payments. Set monobank_jar_payments=true only when "
    "the merchant asks for payment through a Monobank jar/banka, a Monobank "
    "savings jar link, or instructions like 'Nakapychennia -> Banka', "
    "'Banka po ssylke', or 'send/share/copy the banka link'. "
    "Ти вузькоспеціалізований класифікатор умов P2P-ордерів для криптообміну. "
    "Твоя роль: визначати з опису мерчанта три ризики: "
    "1) чи дозволяється або вимагається оплата кількома платежами/переказами; "
    "2) чи дозволяється або вимагається оплата від третьої особи, тобто відправник "
    "може мати інше ім'я, ніж власник акаунта; "
    "3) чи потрібно платити через Monobank «банку», посилання на банку або інструкції "
    "з розділу «Накопичення» -> «Банка». "
    "Поверни true лише коли це явно дозволено або явно вимагається. "
    "Для split_payments вважай явними фрази на кшталт 'платежей на поступление будет от 4+', "
    "'по 300 грн', 'оплата частями', 'несколько переводов'. "
    "Якщо текст це забороняє, наприклад 'не приймаю від 3-х осіб' або 'одним платежем', "
    "поверни false. Якщо доказів недостатньо, також поверни false. "
    "Розумій українську, російську та англійську. "
    "Відповідай тільки згідно з JSON schema."
)


@dataclass
class ClassificationCacheEntry:
    classification: P2PDescriptionClassification | None
    expires_at: float


_classification_cache: dict[str, ClassificationCacheEntry] = {}


async def classify_p2p_descriptions(
    descriptions: list[str | None],
) -> dict[int, P2PDescriptionClassification]:
    prepared = [
        {
            "index": index,
            "description": normalize_description(description),
        }
        for index, description in enumerate(descriptions)
        if normalize_description(description)
    ]

    if not prepared:
        logger.warning("OpenAI P2P classifier skipped: no order descriptions to classify")
        return {}

    (
        cached_classifications,
        missing_items,
        cached_failures_count,
    ) = split_cached_classifications(prepared)
    logger.info(
        "OpenAI P2P classifier cache: items=%s cached=%s cached_failures=%s missing=%s ttl=%ss",
        len(prepared),
        len(cached_classifications),
        cached_failures_count,
        len(missing_items),
        get_classifier_cache_ttl_seconds(),
    )

    if not missing_items:
        return cached_classifications

    if not get_openai_api_key():
        logger.warning("OpenAI P2P classifier skipped: OPENAI_API_KEY is empty")
        return cached_classifications

    started_at = time.monotonic()
    classifications = await classify_missing_items(missing_items)
    result = {
        **cached_classifications,
        **classifications,
    }

    logger.info(
        "OpenAI P2P classifier done: missing=%s fresh=%s cached=%s elapsed=%.2fs",
        len(missing_items),
        len(classifications),
        len(cached_classifications),
        time.monotonic() - started_at,
    )

    return result


async def classify_missing_items(
    items: list[dict],
) -> dict[int, P2PDescriptionClassification]:
    single_batch = should_use_single_batch()
    batches = [items] if single_batch else chunk_items(items, get_classifier_batch_size())
    concurrency = 1 if single_batch else get_classifier_concurrency()
    batch_size = len(items) if single_batch else get_classifier_batch_size()

    logger.info(
        "OpenAI P2P classifier batches start: items=%s batches=%s batch_size=%s concurrency=%s single_batch=%s model=%s vector_stores=%s timeout=%ss file_search_results=%s",
        len(items),
        len(batches),
        batch_size,
        concurrency,
        single_batch,
        get_openai_model(),
        len(get_vector_store_ids()),
        get_classifier_timeout(),
        get_file_search_max_results(),
    )

    semaphore = asyncio.Semaphore(concurrency)

    async def run_batch(
        batch_index: int,
        batch_items: list[dict],
    ) -> dict[int, P2PDescriptionClassification]:
        async with semaphore:
            return await request_classification_batch(
                batch_items,
                batch_index=batch_index,
                batch_count=len(batches),
            )

    results = await asyncio.gather(
        *(
            run_batch(batch_index, batch_items)
            for batch_index, batch_items in enumerate(batches, start=1)
        )
    )
    classifications = {}

    for batch_result in results:
        classifications.update(batch_result)

    return classifications


async def request_classification_batch(
    items: list[dict],
    *,
    batch_index: int,
    batch_count: int,
) -> dict[int, P2PDescriptionClassification]:
    payload = build_responses_payload(items)
    headers = {
        "Authorization": f"Bearer {get_openai_api_key()}",
        "Content-Type": "application/json",
    }
    timeout = aiohttp.ClientTimeout(total=get_classifier_timeout())
    started_at = time.monotonic()

    logger.info(
        "OpenAI P2P classifier batch start: batch=%s/%s items=%s",
        batch_index,
        batch_count,
        len(items),
    )
    log_description_snippets(items)

    try:
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.post(OPENAI_RESPONSES_URL, json=payload) as response:
                if response.status >= 400:
                    body = await response.text()
                    logger.warning(
                        "OpenAI P2P classifier batch failed: batch=%s/%s HTTP %s body=%s",
                        batch_index,
                        batch_count,
                        response.status,
                        safe_log_snippet(body, 500),
                    )
                    cache_classification_failures(items)
                    return {}

                response.raise_for_status()
                data = await response.json(content_type=None)
    except aiohttp.ClientError as error:
        logger.warning(
            "OpenAI P2P classifier batch failed after %.2fs: batch=%s/%s error=%s",
            time.monotonic() - started_at,
            batch_index,
            batch_count,
            type(error).__name__,
        )
        cache_classification_failures(items)
        return {}
    except asyncio.TimeoutError:
        logger.warning(
            "OpenAI P2P classifier batch timed out after %.2fs: batch=%s/%s",
            time.monotonic() - started_at,
            batch_index,
            batch_count,
        )
        cache_classification_failures(items)
        return {}
    except json.JSONDecodeError:
        logger.warning(
            "OpenAI P2P classifier batch returned invalid JSON after %.2fs: batch=%s/%s",
            time.monotonic() - started_at,
            batch_index,
            batch_count,
        )
        cache_classification_failures(items)
        return {}

    classifications = parse_classification_response(data)
    cache_classifications(items, classifications)
    cache_classification_failures(items, classifications)

    logger.info(
        "OpenAI P2P classifier batch done: batch=%s/%s items=%s classifications=%s elapsed=%.2fs",
        batch_index,
        batch_count,
        len(items),
        len(classifications),
        time.monotonic() - started_at,
    )

    return classifications


def build_responses_payload(items: list[dict]) -> dict:
    payload = {
        "model": get_openai_model(),
        "store": False,
        "instructions": P2P_CLASSIFIER_INSTRUCTIONS,
        "input": [
            {
                "role": "user",
                "content": (
                    "Classify these order descriptions. "
                    "split_payments means the merchant allows, requires, or warns that one "
                    "order may be paid/credited by several payments, transfers, receipts, "
                    "or incoming deposits. Treat 'платежей на поступление будет от 4+' "
                    "as split_payments=true. "
                    "third_party_payments means the merchant allows or requires payment from "
                    "a person/bank/card/account whose name is different from the account owner. "
                    "monobank_jar_payments means the merchant asks for payment through a "
                    "Monobank jar/banka or a jar link, including Monobank savings jar "
                    "instructions. "
                    "Return only the requested JSON fields, without explanations. "
                    "Descriptions:\n"
                    f"{json.dumps(items, ensure_ascii=False)}"
                ),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "p2p_terms_classification",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "orders": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "index": {"type": "integer"},
                                    "split_payments": {"type": "boolean"},
                                    "third_party_payments": {"type": "boolean"},
                                    "monobank_jar_payments": {"type": "boolean"},
                                },
                                "required": [
                                    "index",
                                    "split_payments",
                                    "third_party_payments",
                                    "monobank_jar_payments",
                                ],
                            },
                        },
                    },
                    "required": ["orders"],
                },
            },
        },
    }

    tools = build_tools()

    if tools:
        payload["tools"] = tools

    return payload


def build_tools() -> list[dict]:
    vector_store_ids = get_vector_store_ids()

    if not vector_store_ids:
        return []

    return [
        {
            "type": "file_search",
            "vector_store_ids": vector_store_ids,
            "max_num_results": get_file_search_max_results(),
        }
    ]


def get_openai_api_key() -> str:
    return getattr(Config, "OPENAI_API_KEY", "")


def get_openai_model() -> str:
    return getattr(Config, "OPENAI_P2P_MODEL", DEFAULT_OPENAI_P2P_MODEL)


def get_classifier_timeout() -> float:
    return getattr(
        Config,
        "OPENAI_P2P_CLASSIFIER_TIMEOUT",
        DEFAULT_OPENAI_P2P_CLASSIFIER_TIMEOUT,
    )


def get_classifier_batch_size() -> int:
    try:
        return max(
            1,
            int(
                getattr(
                    Config,
                    "OPENAI_P2P_CLASSIFIER_BATCH_SIZE",
                    DEFAULT_OPENAI_P2P_CLASSIFIER_BATCH_SIZE,
                )
            ),
        )
    except (TypeError, ValueError):
        return DEFAULT_OPENAI_P2P_CLASSIFIER_BATCH_SIZE


def get_classifier_concurrency() -> int:
    try:
        return max(
            1,
            int(
                getattr(
                    Config,
                    "OPENAI_P2P_CLASSIFIER_CONCURRENCY",
                    DEFAULT_OPENAI_P2P_CLASSIFIER_CONCURRENCY,
                )
            ),
        )
    except (TypeError, ValueError):
        return DEFAULT_OPENAI_P2P_CLASSIFIER_CONCURRENCY


def should_use_single_batch() -> bool:
    return bool(
        getattr(
            Config,
            "OPENAI_P2P_CLASSIFIER_SINGLE_BATCH",
            DEFAULT_OPENAI_P2P_CLASSIFIER_SINGLE_BATCH,
        )
    )


def get_classifier_cache_ttl_seconds() -> float:
    return max(
        0.0,
        float(getattr(Config, "OPENAI_P2P_CLASSIFICATION_CACHE_TTL_SECONDS", 600)),
    )


def get_vector_store_ids() -> list[str]:
    vector_store_ids = getattr(Config, "OPENAI_VECTOR_STORE_IDS", [])

    if vector_store_ids:
        return vector_store_ids

    vector_store_id = getattr(Config, "OPENAI_VECTOR_STORE_ID", "")

    return [vector_store_id] if vector_store_id else []


def get_file_search_max_results() -> int:
    return getattr(
        Config,
        "OPENAI_FILE_SEARCH_MAX_RESULTS",
        DEFAULT_OPENAI_FILE_SEARCH_MAX_RESULTS,
    )


def chunk_items(items: list[dict], chunk_size: int) -> list[list[dict]]:
    return [
        items[index:index + chunk_size]
        for index in range(0, len(items), chunk_size)
    ]


def parse_classification_response(data: dict) -> dict[int, P2PDescriptionClassification]:
    text = extract_output_text(data)

    if not text:
        logger.warning("OpenAI P2P classifier response has no output_text")
        return {}

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("OpenAI P2P classifier output is not valid JSON")
        return {}

    classifications = {}

    for item in payload.get("orders", []):
        try:
            index = int(item["index"])
        except (KeyError, TypeError, ValueError):
            continue

        classifications[index] = P2PDescriptionClassification(
            split_payments=bool(item.get("split_payments")),
            third_party_payments=bool(item.get("third_party_payments")),
            monobank_jar_payments=bool(item.get("monobank_jar_payments")),
            confidence=parse_confidence(item.get("confidence")),
            reason=str(item.get("reason") or ""),
        )

    return classifications


def split_cached_classifications(
    items: list[dict],
) -> tuple[dict[int, P2PDescriptionClassification], list[dict], int]:
    cached_classifications = {}
    missing_items = []
    cached_failures_count = 0
    now = time.monotonic()

    for item in items:
        description = item["description"]
        cached = _classification_cache.get(description)

        if cached and cached.expires_at > now:
            if cached.classification is None:
                cached_failures_count += 1
            else:
                cached_classifications[item["index"]] = copy.deepcopy(
                    cached.classification
                )
            continue

        if cached:
            _classification_cache.pop(description, None)

        missing_items.append(item)

    return cached_classifications, missing_items, cached_failures_count


def cache_classifications(
    items: list[dict],
    classifications: dict[int, P2PDescriptionClassification],
):
    ttl_seconds = get_classifier_cache_ttl_seconds()

    if ttl_seconds <= 0:
        return

    descriptions_by_index = {
        item["index"]: item["description"]
        for item in items
    }
    expires_at = time.monotonic() + ttl_seconds
    stored = 0

    for index, classification in classifications.items():
        description = descriptions_by_index.get(index)

        if not description:
            continue

        _classification_cache[description] = ClassificationCacheEntry(
            classification=copy.deepcopy(classification),
            expires_at=expires_at,
        )
        stored += 1

    logger.info(
        "OpenAI P2P classifier cache stored: items=%s ttl=%ss",
        stored,
        ttl_seconds,
    )


def cache_classification_failures(
    items: list[dict],
    classifications: dict[int, P2PDescriptionClassification] | None = None,
):
    ttl_seconds = get_classifier_cache_ttl_seconds()

    if ttl_seconds <= 0:
        return

    classified_indexes = set(classifications or {})
    expires_at = time.monotonic() + ttl_seconds
    stored = 0

    for item in items:
        if item["index"] in classified_indexes:
            continue

        description = item.get("description")

        if not description:
            continue

        _classification_cache[description] = ClassificationCacheEntry(
            classification=None,
            expires_at=expires_at,
        )
        stored += 1

    if stored:
        logger.info(
            "OpenAI P2P classifier failure cache stored: items=%s ttl=%ss",
            stored,
            ttl_seconds,
        )


def extract_output_text(data: dict) -> str | None:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]

    for output_item in data.get("output", []):
        for content_item in output_item.get("content", []):
            if isinstance(content_item.get("text"), str):
                return content_item["text"]

    return None


def normalize_description(description: str | None) -> str:
    if not description:
        return ""

    text = "\n".join(
        line.strip()
        for line in str(description).replace("\r", "\n").split("\n")
        if line.strip()
    )

    return text[:MAX_DESCRIPTION_CHARS]


def parse_confidence(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def log_description_snippets(items: list[dict]):
    if not getattr(Config, "P2P_LOG_DESCRIPTION_SNIPPETS", False):
        return

    for item in items:
        logger.debug(
            "OpenAI P2P classifier item: index=%s description=%s",
            item.get("index"),
            safe_log_snippet(item.get("description", ""), 250),
        )


def safe_log_snippet(value: str, limit: int) -> str:
    return " ".join(str(value).split())[:limit]
