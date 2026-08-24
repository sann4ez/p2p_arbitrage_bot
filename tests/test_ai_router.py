import unittest
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, Mock, patch

from config import Config, parse_model_chain
from services.ai_router import (
    AI_PROFILE_P2P,
    AI_PROFILE_WEB,
    build_router_settings,
    complete_ai_chat,
    complete_ai_response,
    extract_response_text,
    get_profile_config,
    normalize_model_name,
)


@contextmanager
def patched_ai_config(**overrides):
    values = {
        "DASHSCOPE_API_KEY": "dashscope-key",
        "DASHSCOPE_API_BASE": "https://dashscope.example/v1",
        "DEEPSEEK_API_KEY": "deepseek-key",
        "DEEPSEEK_API_BASE": "",
        "OPENAI_API_KEY": "openai-key",
        "OPENAI_API_BASE": "",
        "LITELLM_P2P_MODEL": "dashscope/qwen-plus",
        "LITELLM_P2P_FALLBACK_MODELS": [
            "deepseek/deepseek-chat",
            "openai/gpt-5-mini",
        ],
        "LITELLM_P2P_MODELS": [
            "dashscope/qwen-plus",
            "deepseek/deepseek-chat",
            "openai/gpt-5-mini",
        ],
        "LITELLM_RECOMMENDATION_MODEL": "",
        "LITELLM_RECOMMENDATION_FALLBACK_MODELS": [],
        "LITELLM_RECOMMENDATION_MODELS": [],
        "LITELLM_WEB_MODEL": "",
        "LITELLM_WEB_FALLBACK_MODELS": [],
        "LITELLM_WEB_MODELS": [],
    }
    values.update(overrides)

    with ExitStack() as stack:
        for name, value in values.items():
            stack.enter_context(patch.object(Config, name, value))

        yield


class ModelChainParsingTests(unittest.TestCase):
    def test_parses_json_array(self):
        self.assertEqual(
            parse_model_chain(
                '["dashscope/qwen-plus", "deepseek/deepseek-chat"]'
            ),
            ["dashscope/qwen-plus", "deepseek/deepseek-chat"],
        )

    def test_parses_comma_separated_chain(self):
        self.assertEqual(
            parse_model_chain("dashscope/qwen-plus, openai/gpt-5-mini"),
            ["dashscope/qwen-plus", "openai/gpt-5-mini"],
        )

    def test_rejects_invalid_json_array(self):
        with self.assertRaises(ValueError):
            parse_model_chain('["dashscope/qwen-plus",]')


class AIProfileConfigTests(unittest.TestCase):
    def test_plain_openai_model_name_is_normalized(self):
        self.assertEqual(
            normalize_model_name("gpt-5-mini"),
            "openai/gpt-5-mini",
        )

    def test_router_preserves_ordered_fallback_chain(self):
        with patched_ai_config():
            model_list, fallbacks = build_router_settings()

        self.assertEqual(
            [item["model_name"] for item in model_list],
            ["p2p-primary", "p2p-fallback-1", "p2p-fallback-2"],
        )
        self.assertEqual(
            [item["litellm_params"]["model"] for item in model_list],
            [
                "dashscope/qwen-plus",
                "deepseek/deepseek-chat",
                "openai/gpt-5-mini",
            ],
        )
        self.assertEqual(
            fallbacks,
            [
                {
                    "p2p-primary": [
                        "p2p-fallback-1",
                        "p2p-fallback-2",
                    ]
                },
                {"p2p-fallback-1": ["p2p-fallback-2"]},
            ],
        )

    def test_explicit_chain_overrides_legacy_fields(self):
        with patched_ai_config(
            LITELLM_P2P_MODELS=["openai/gpt-5-mini"],
        ):
            profile = get_profile_config(AI_PROFILE_P2P)

        self.assertEqual(
            [deployment.model for deployment in profile.models],
            ["openai/gpt-5-mini"],
        )

    def test_legacy_fields_work_when_chain_is_empty(self):
        with patched_ai_config(LITELLM_P2P_MODELS=[]):
            profile = get_profile_config(AI_PROFILE_P2P)

        self.assertEqual(
            [deployment.model for deployment in profile.models],
            [
                "dashscope/qwen-plus",
                "deepseek/deepseek-chat",
                "openai/gpt-5-mini",
            ],
        )

    def test_provider_without_credentials_is_skipped(self):
        with patched_ai_config(DASHSCOPE_API_KEY=""):
            profile = get_profile_config(AI_PROFILE_P2P)

        self.assertEqual(
            [deployment.model for deployment in profile.models],
            ["deepseek/deepseek-chat", "openai/gpt-5-mini"],
        )
        self.assertEqual(
            profile.aliases,
            ("p2p-primary", "p2p-fallback-1"),
        )


class AIRouterRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_json_uses_next_model(self):
        router = Mock()
        router.acompletion = AsyncMock(
            side_effect=[
                {
                    "model": "dashscope/qwen-plus",
                    "choices": [
                        {"message": {"content": "not-json"}},
                    ],
                },
                {
                    "model": "deepseek/deepseek-chat",
                    "choices": [
                        {"message": {"content": '{"orders": []}'}},
                    ],
                },
            ]
        )

        with (
            patched_ai_config(),
            patch("services.ai_router.get_ai_router", return_value=router),
        ):
            result = await complete_ai_chat(
                profile=AI_PROFILE_P2P,
                instructions="Return JSON.",
                input_text="Classify.",
                timeout=20,
                json_schema={
                    "type": "object",
                    "properties": {"orders": {"type": "array"}},
                    "required": ["orders"],
                },
                schema_name="test_schema",
            )

        self.assertEqual(result.model, "deepseek/deepseek-chat")
        self.assertEqual(router.acompletion.await_count, 2)
        self.assertEqual(
            [
                call.kwargs["model"]
                for call in router.acompletion.await_args_list
            ],
            ["p2p-primary", "p2p-fallback-1"],
        )

    async def test_schema_mismatch_uses_next_model(self):
        router = Mock()
        router.acompletion = AsyncMock(
            side_effect=[
                {
                    "model": "dashscope/qwen-plus",
                    "choices": [
                        {"message": {"content": '{"wrong": []}'}},
                    ],
                },
                {
                    "model": "deepseek/deepseek-chat",
                    "choices": [
                        {"message": {"content": '{"orders": []}'}},
                    ],
                },
            ]
        )

        with (
            patched_ai_config(),
            patch("services.ai_router.get_ai_router", return_value=router),
        ):
            result = await complete_ai_chat(
                profile=AI_PROFILE_P2P,
                instructions="Return JSON.",
                input_text="Classify.",
                timeout=20,
                json_schema={
                    "type": "object",
                    "properties": {"orders": {"type": "array"}},
                    "required": ["orders"],
                },
                schema_name="test_schema",
            )

        self.assertEqual(result.model, "deepseek/deepseek-chat")
        self.assertEqual(router.acompletion.await_count, 2)

    async def test_responses_profile_passes_web_tools(self):
        router = Mock()
        router.aresponses = AsyncMock(
            return_value={
                "model": "openai/gpt-5-mini",
                "output_text": '{"impact_score": 0}',
            }
        )

        with (
            patched_ai_config(
                LITELLM_P2P_MODEL="",
                LITELLM_P2P_FALLBACK_MODELS=[],
                LITELLM_WEB_MODEL="openai/gpt-5-mini",
            ),
            patch("services.ai_router.get_ai_router", return_value=router),
        ):
            result = await complete_ai_response(
                profile=AI_PROFILE_WEB,
                instructions="Analyze.",
                input_data="UAH",
                timeout=30,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "macro",
                        "schema": {"type": "object"},
                    }
                },
                tools=[{"type": "web_search"}],
            )

        self.assertEqual(result.model, "openai/gpt-5-mini")
        router.aresponses.assert_awaited_once()
        self.assertEqual(
            router.aresponses.await_args.kwargs["model"],
            "web-primary",
        )
        self.assertEqual(
            router.aresponses.await_args.kwargs["tools"],
            [{"type": "web_search"}],
        )

    async def test_qwen_web_profile_enables_dashscope_search(self):
        router = Mock()
        router.acompletion = AsyncMock(
            return_value={
                "model": "dashscope/qwen-plus",
                "choices": [
                    {"message": {"content": '{"impact_score": 0}'}}
                ],
            }
        )
        router.aresponses = AsyncMock()

        with (
            patched_ai_config(
                LITELLM_P2P_MODEL="",
                LITELLM_P2P_FALLBACK_MODELS=[],
                LITELLM_WEB_MODELS=[
                    "dashscope/qwen-plus",
                    "openai/gpt-5-mini",
                ],
            ),
            patch("services.ai_router.get_ai_router", return_value=router),
        ):
            result = await complete_ai_response(
                profile=AI_PROFILE_WEB,
                instructions="Analyze.",
                input_data="UAH",
                timeout=30,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "macro",
                        "schema": {"type": "object"},
                    }
                },
                tools=[{"type": "web_search"}],
            )

        self.assertEqual(result.model, "dashscope/qwen-plus")
        router.acompletion.assert_awaited_once()
        router.aresponses.assert_not_awaited()
        kwargs = router.acompletion.await_args.kwargs
        self.assertEqual(kwargs["model"], "web-primary")
        self.assertTrue(kwargs["disable_fallbacks"])
        self.assertEqual(
            kwargs["extra_body"],
            {
                "enable_search": True,
                "search_options": {
                    "forced_search": True,
                    "enable_source": True,
                    "enable_citation": False,
                },
            },
        )

    async def test_qwen_web_failure_uses_openai_fallback(self):
        router = Mock()
        router.acompletion = AsyncMock(side_effect=RuntimeError("qwen failed"))
        router.aresponses = AsyncMock(
            return_value={
                "model": "openai/gpt-5-mini",
                "output_text": '{"impact_score": 0}',
            }
        )

        with (
            patched_ai_config(
                LITELLM_P2P_MODEL="",
                LITELLM_P2P_FALLBACK_MODELS=[],
                LITELLM_WEB_MODELS=[
                    "dashscope/qwen-plus",
                    "openai/gpt-5-mini",
                ],
            ),
            patch("services.ai_router.get_ai_router", return_value=router),
        ):
            result = await complete_ai_response(
                profile=AI_PROFILE_WEB,
                instructions="Analyze.",
                input_data="UAH",
                timeout=30,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "macro",
                        "schema": {"type": "object"},
                    }
                },
                tools=[{"type": "web_search"}],
            )

        self.assertEqual(result.model, "openai/gpt-5-mini")
        self.assertEqual(
            router.aresponses.await_args.kwargs["model"],
            "web-fallback-1",
        )

    def test_extracts_responses_api_text(self):
        self.assertEqual(
            extract_response_text(
                {
                    "output": [
                        {
                            "content": [
                                {"type": "output_text", "text": "answer"},
                            ]
                        }
                    ]
                }
            ),
            "answer",
        )


if __name__ == "__main__":
    unittest.main()