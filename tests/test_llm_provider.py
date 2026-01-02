from __future__ import annotations

from agents import OpenAIChatCompletionsModel

from echoagent.utils.llm_setup import LLMConfig


def test_openai_compatible_provider_creates_chat_model() -> None:
    config = {
        "provider": "openai_compatible",
        "api_key": "test-key",
        "model": "test-model",
        "base_url": "https://example.com/v1",
    }

    llm = LLMConfig(config)

    assert isinstance(llm.main_model, OpenAIChatCompletionsModel)
