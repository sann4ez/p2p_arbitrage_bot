from __future__ import annotations

import importlib
import json
import logging
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from config import Config


logger = logging.getLogger(__name__)

AI_PROFILE_P2P = "p2p"
AI_PROFILE_RECOMMENDATION = "recommendation"
AI_PROFILE_WEB = "web"
AI_PROFILES = (
    AI_PROFILE_P2P,
    AI_PROFILE_RECOMMENDATION,
    AI_PROFILE_WEB,
)

_PROFILE_CONFIG_FIELDS = {
    AI_PROFILE_P2P: (
        "LITELLM_P2P_MODELS",
        "LITELLM_P2P_MODEL",
        "LITELLM_P2P_FALLBACK_MODELS",
    ),
    AI_PROFILE_RECOMMENDATION: (
        "LITELLM_RECOMMENDATION_MODELS",
        "LITELLM_RECOMMENDATION_MODEL",
        "LITELLM_RECOMMENDATION_FALLBACK_MODELS",
    ),
    AI_PROFILE_WEB: (
        "LITELLM_WEB_MODELS",
        "LITELLM_WEB_MODEL",
        "LITELLM_WEB_FALLBACK_MODELS",
    ),
}


@dataclass(frozen=True)
class AIModelDeployment:
    model: str
    api_key: str = field(default="", repr=False)
    api_base: str = ""


@dataclass(frozen=True)
class AIProfileConfig:
    name: str
    models: tuple[AIModelDeployment, ...]

    @property
    def aliases(self) -> tuple[str, ...]:
        return tuple(
            build_model_alias(self.name, index)
            for index in range(len(self.models))
        )


@dataclass(frozen=True)
class AITextResponse:
    text: str
    model: str
    raw_response: Any = field(repr=False)


class AIConfigurationError(RuntimeError):
    pass


class AIRequestError(RuntimeError):
    pass


_router = None
_router_signature: tuple | None = None
_router_lock = threading.Lock()


def normalize_model_name(value: str | None) -> str:
    model = str(value or "").strip()

    if not model:
        return ""

    if "/" not in model:
        return f"openai/{model}"

    return model


def get_profile_config(profile: str) -> AIProfileConfig:
    try:
        (
            models_field,
            primary_field,
            fallbacks_field,
        ) = _PROFILE_CONFIG_FIELDS[profile]
    except KeyError as error:
        raise ValueError(f"Unknown AI profile: {profile}") from error

    raw_models = list(getattr(Config, models_field, []) or [])

    if not raw_models:
        raw_models = [
            getattr(Config, primary_field, ""),
            *list(getattr(Config, fallbacks_field, []) or []),
        ]
    deployments = []
    seen_models = set()

    for raw_model in raw_models:
        model = normalize_model_name(raw_model)

        if not model or model in seen_models:
            continue

        deployment = build_deployment(model)

        if deployment is None:
            continue

        deployments.append(deployment)
        seen_models.add(model)

    return AIProfileConfig(
        name=profile,
        models=tuple(deployments),
    )


def build_deployment(model: str) -> AIModelDeployment | None:
    provider = model.split("/", 1)[0].lower()
    provider_settings = {
        "dashscope": (
            getattr(Config, "DASHSCOPE_API_KEY", ""),
            getattr(Config, "DASHSCOPE_API_BASE", ""),
        ),
        "deepseek": (
            getattr(Config, "DEEPSEEK_API_KEY", ""),
            getattr(Config, "DEEPSEEK_API_BASE", ""),
        ),
        "openai": (
            getattr(Config, "OPENAI_API_KEY", ""),
            getattr(Config, "OPENAI_API_BASE", ""),
        ),
    }
    settings = provider_settings.get(provider)

    if settings is None:
        return AIModelDeployment(model=model)

    api_key, api_base = (str(value or "").strip() for value in settings)

    if not api_key:
        return None

    return AIModelDeployment(
        model=model,
        api_key=api_key,
        api_base=api_base,
    )


def is_ai_configured(profile: str) -> bool:
    return bool(get_profile_config(profile).models)


def get_profile_model_signature(profile: str) -> str:
    models = get_profile_config(profile).models
    return ">".join(deployment.model for deployment in models) or "unconfigured"


def build_model_alias(profile: str, index: int) -> str:
    if index == 0:
        return f"{profile}-primary"

    return f"{profile}-fallback-{index}"


def build_router_settings() -> tuple[list[dict], list[dict]]:
    model_list = []
    fallbacks = []

    for profile_name in AI_PROFILES:
        profile = get_profile_config(profile_name)
        aliases = profile.aliases

        for alias, deployment in zip(aliases, profile.models, strict=True):
            litellm_params = {"model": deployment.model}

            if deployment.api_key:
                litellm_params["api_key"] = deployment.api_key

            if deployment.api_base:
                litellm_params["api_base"] = deployment.api_base

            model_list.append(
                {
                    "model_name": alias,
                    "litellm_params": litellm_params,
                }
            )

        for index, alias in enumerate(aliases[:-1]):
            fallbacks.append({alias: list(aliases[index + 1:])})

    return model_list, fallbacks


def get_ai_router():
    global _router, _router_signature

    model_list, fallbacks = build_router_settings()

    if not model_list:
        raise AIConfigurationError(
            "No AI models have both a model name and provider credentials."
        )

    signature = build_router_signature(model_list, fallbacks)

    if _router is not None and _router_signature == signature:
        return _router

    with _router_lock:
        if _router is not None and _router_signature == signature:
            return _router

        litellm = importlib.import_module("litellm")
        litellm.telemetry = False
        litellm.suppress_debug_info = True
        litellm.turn_off_message_logging = True
        litellm.drop_params = True
        router_class = getattr(litellm, "Router")
        _router = router_class(
            model_list=model_list,
            fallbacks=fallbacks,
            num_retries=max(0, int(getattr(Config, "LITELLM_NUM_RETRIES", 1))),
            allowed_fails=max(
                0,
                int(getattr(Config, "LITELLM_ALLOWED_FAILURES", 1)),
            ),
            cooldown_time=max(
                0.0,
                float(getattr(Config, "LITELLM_COOLDOWN_SECONDS", 60.0)),
            ),
            cache_responses=False,
        )
        _router_signature = signature

    return _router


async def complete_ai_chat(
    *,
    profile: str,
    instructions: str,
    input_text: str,
    timeout: float,
    json_schema: dict | None = None,
    schema_name: str = "structured_response",
    reasoning_effort: str | None = None,
) -> AITextResponse:
    response_format = None

    if json_schema is not None:
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": json_schema,
            },
        }

    async def invoke(alias: str, deployment: AIModelDeployment):
        del deployment
        kwargs = {
            "model": alias,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": input_text},
            ],
            "timeout": max(1.0, float(timeout)),
            "store": False,
            "drop_params": True,
        }

        if response_format is not None:
            kwargs["response_format"] = response_format

        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort

        return await get_ai_router().acompletion(**kwargs)

    return await request_with_fallback_validation(
        profile=profile,
        invoke=invoke,
        json_schema=json_schema,
    )


async def complete_ai_response(
    *,
    profile: str,
    instructions: str,
    input_data: str | list[dict],
    timeout: float,
    text: dict | None = None,
    tools: list[dict] | None = None,
    reasoning_effort: str | None = None,
) -> AITextResponse:
    text_format = text.get("format") if isinstance(text, dict) else None
    json_schema = (
        text_format.get("schema")
        if isinstance(text_format, dict)
        and text_format.get("type") == "json_schema"
        and isinstance(text_format.get("schema"), dict)
        else None
    )

    web_search_requested = has_web_search_tool(tools)

    async def invoke(alias: str, deployment: AIModelDeployment):
        if (
            profile == AI_PROFILE_WEB
            and web_search_requested
            and uses_dashscope_chat_web_search(deployment.model)
        ):
            kwargs = {
                "model": alias,
                "messages": [
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": serialize_chat_input(input_data)},
                ],
                "timeout": max(1.0, float(timeout)),
                "store": False,
                "drop_params": True,
                "disable_fallbacks": True,
                "extra_body": {
                    "enable_search": True,
                    "search_options": {
                        "forced_search": True,
                        "enable_source": True,
                        "enable_citation": False,
                    },
                },
            }

            return await get_ai_router().acompletion(**kwargs)

        kwargs = {
            "model": alias,
            "instructions": instructions,
            "input": input_data,
            "timeout": max(1.0, float(timeout)),
            "store": False,
            "drop_params": True,
        }

        if text:
            kwargs["text"] = text

        if tools:
            kwargs["tools"] = tools

        if reasoning_effort:
            kwargs["reasoning"] = {"effort": reasoning_effort}

        if profile == AI_PROFILE_WEB and web_search_requested:
            kwargs["disable_fallbacks"] = True

        return await get_ai_router().aresponses(**kwargs)

    return await request_with_fallback_validation(
        profile=profile,
        invoke=invoke,
        json_schema=json_schema,
    )


async def request_with_fallback_validation(
    *,
    profile: str,
    invoke,
    json_schema: dict | None,
) -> AITextResponse:
    profile_config = get_profile_config(profile)

    if not profile_config.models:
        raise AIConfigurationError(f"AI profile is not configured: {profile}")

    last_problem = "empty response"
    last_error = None

    for model_index, (alias, deployment) in enumerate(
        zip(profile_config.aliases, profile_config.models, strict=True)
    ):
        try:
            response = await invoke(alias, deployment)
        except Exception as error:
            last_error = error
            last_problem = type(error).__name__
            logger.debug(
                "AI provider request failed: profile=%s model=%s error=%s",
                profile,
                deployment.model,
                last_problem,
            )
            continue

        text = extract_response_text(response)

        if not text:
            last_problem = "empty response"
        elif json_schema is None or is_valid_structured_response(text, json_schema):
            return AITextResponse(
                text=text,
                model=extract_response_model(response)
                or profile_config.models[model_index].model,
                raw_response=response,
            )
        else:
            last_problem = "invalid structured response"

        logger.debug(
            "AI provider returned %s: profile=%s model=%s",
            last_problem,
            profile,
            extract_response_model(response) or alias,
        )

    request_error = AIRequestError(f"{profile} request failed: {last_problem}")

    if last_error is not None:
        raise request_error from last_error

    raise request_error


def has_web_search_tool(tools: list[dict] | None) -> bool:
    return any(
        str(tool.get("type") or "").startswith("web_search")
        for tool in tools or []
        if isinstance(tool, dict)
    )


def uses_dashscope_chat_web_search(model: str) -> bool:
    provider, _, model_name = str(model or "").lower().partition("/")

    if provider != "dashscope":
        return False

    # Versioned Qwen 3.x models expose web_search through Responses API.
    # Stable aliases such as qwen-plus use Chat Completions + enable_search.
    return not model_name.startswith(("qwen3.", "qwen3-"))


def serialize_chat_input(input_data: str | list[dict]) -> str:
    if isinstance(input_data, str):
        return input_data

    return json.dumps(input_data, ensure_ascii=False)


def is_valid_structured_response(text: str, schema: dict) -> bool:
    payload = decode_json_object(text)

    if payload is None:
        return False

    jsonschema = importlib.import_module("jsonschema")
    validator_class = jsonschema.validators.validator_for(schema)
    validator_class.check_schema(schema)
    return validator_class(schema).is_valid(payload)


def extract_response_text(response: Any) -> str:
    output_text = get_value(response, "output_text")

    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output_parts = []

    for output_item in get_value(response, "output", []) or []:
        for content_item in get_value(output_item, "content", []) or []:
            text = get_value(content_item, "text")

            if isinstance(text, str) and text.strip():
                output_parts.append(text.strip())

    if output_parts:
        return "\n".join(output_parts)

    choices = get_value(response, "choices", []) or []

    if not choices:
        return ""

    message = get_value(choices[0], "message", {})
    content = get_value(message, "content", "")

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []

        for item in content:
            text = get_value(item, "text")

            if isinstance(text, str) and text.strip():
                parts.append(text.strip())

        return "\n".join(parts)

    return ""


def extract_response_model(response: Any) -> str:
    return str(get_value(response, "model", "") or "").strip()


def response_to_dict(response: Any) -> dict:
    if isinstance(response, dict):
        return response

    model_dump = getattr(response, "model_dump", None)

    if callable(model_dump):
        value = model_dump()
        return value if isinstance(value, dict) else {}

    as_dict = getattr(response, "dict", None)

    if callable(as_dict):
        value = as_dict()
        return value if isinstance(value, dict) else {}

    return {}


def decode_json_object(value: str) -> dict | None:
    text = str(value or "").strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    try:
        result = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None

    return result if isinstance(result, dict) else None


def get_value(value: Any, key: str, default=None):
    if isinstance(value, Mapping):
        return value.get(key, default)

    return getattr(value, key, default)


def build_router_signature(model_list: list[dict], fallbacks: list[dict]) -> tuple:
    deployments = tuple(
        (
            item["model_name"],
            item["litellm_params"].get("model", ""),
            item["litellm_params"].get("api_key", ""),
            item["litellm_params"].get("api_base", ""),
        )
        for item in model_list
    )
    fallback_signature = tuple(
        (source, tuple(targets))
        for item in fallbacks
        for source, targets in item.items()
    )
    router_settings = (
        int(getattr(Config, "LITELLM_NUM_RETRIES", 1)),
        int(getattr(Config, "LITELLM_ALLOWED_FAILURES", 1)),
        float(getattr(Config, "LITELLM_COOLDOWN_SECONDS", 60.0)),
    )
    return deployments, fallback_signature, router_settings


def reset_ai_router():
    global _router, _router_signature
    _router = None
    _router_signature = None