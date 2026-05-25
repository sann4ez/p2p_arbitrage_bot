import asyncio
import json
import logging
import time

import aiohttp

from config import Config
from db.dto import P2PDescriptionClassification


logger = logging.getLogger(__name__)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_P2P_MODEL = "gpt-5-nano"
DEFAULT_OPENAI_P2P_CLASSIFIER_TIMEOUT = 20
DEFAULT_OPENAI_FILE_SEARCH_MAX_RESULTS = 3
MAX_DESCRIPTION_CHARS = 2000
P2P_CLASSIFIER_INSTRUCTIONS = (
    "Ти вузькоспеціалізований класифікатор умов P2P-ордерів для криптообміну. "
    "Твоя роль: визначати з опису мерчанта тільки два ризики: "
    "1) чи дозволяється або вимагається оплата кількома платежами/переказами; "
    "2) чи дозволяється або вимагається оплата від третьої особи, тобто відправник "
    "може мати інше ім'я, ніж власник акаунта. "
    "Поверни true лише коли це явно дозволено або явно вимагається. "
    "Якщо текст це забороняє, наприклад 'не приймаю від 3-х осіб' або 'одним платежем', "
    "поверни false. Якщо доказів недостатньо, також поверни false. "
    "Розумій українську, російську та англійську. "
    "Відповідай тільки згідно з JSON schema."
)


async def classify_p2p_descriptions(
    descriptions: list[str | None],
) -> dict[int, P2PDescriptionClassification]:
    if not get_openai_api_key():
        logger.warning("OpenAI P2P classifier skipped: OPENAI_API_KEY is empty")
        return {}

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

    payload = build_responses_payload(prepared)
    headers = {
        "Authorization": f"Bearer {get_openai_api_key()}",
        "Content-Type": "application/json",
    }
    timeout = aiohttp.ClientTimeout(total=get_classifier_timeout())
    started_at = time.monotonic()

    logger.info(
        "OpenAI P2P classifier request start: items=%s model=%s vector_stores=%s timeout=%ss file_search_results=%s",
        len(prepared),
        get_openai_model(),
        len(get_vector_store_ids()),
        get_classifier_timeout(),
        get_file_search_max_results(),
    )
    log_description_snippets(prepared)

    try:
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.post(OPENAI_RESPONSES_URL, json=payload) as response:
                if response.status >= 400:
                    body = await response.text()
                    logger.warning(
                        "OpenAI P2P classifier request failed: HTTP %s body=%s",
                        response.status,
                        safe_log_snippet(body, 500),
                    )
                    return {}

                response.raise_for_status()
                data = await response.json(content_type=None)
    except aiohttp.ClientError as error:
        logger.warning(
            "OpenAI P2P classifier request failed after %.2fs: %s",
            time.monotonic() - started_at,
            type(error).__name__,
        )
        return {}
    except asyncio.TimeoutError:
        logger.warning(
            "OpenAI P2P classifier request timed out after %.2fs",
            time.monotonic() - started_at,
        )
        return {}
    except json.JSONDecodeError:
        logger.warning(
            "OpenAI P2P classifier returned invalid JSON after %.2fs",
            time.monotonic() - started_at,
        )
        return {}

    classifications = parse_classification_response(data)
    logger.info(
        "OpenAI P2P classifier request done: items=%s classifications=%s elapsed=%.2fs",
        len(prepared),
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
                    "split_payments means the merchant allows or requires one order to be "
                    "paid by several payments/transfers, including phrases like 'по 300 грн'. "
                    "third_party_payments means the merchant allows payment from a person "
                    "whose name is different from the account owner. "
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
                                    "confidence": {
                                        "type": "number",
                                    },
                                    "reason": {"type": "string"},
                                },
                                "required": [
                                    "index",
                                    "split_payments",
                                    "third_party_payments",
                                    "confidence",
                                    "reason",
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
            confidence=parse_confidence(item.get("confidence")),
            reason=str(item.get("reason") or ""),
        )

    return classifications


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
