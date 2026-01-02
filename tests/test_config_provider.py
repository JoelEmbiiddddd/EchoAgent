from __future__ import annotations

from agents import OpenAIChatCompletionsModel

from echoagent.utils.config import resolve_config


def test_resolve_config_auto_downgrades_provider(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("OPENAI_API", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config = resolve_config({"pipeline": {"max_iterations": 1}})

    assert config.provider == "openai_compatible"
    assert isinstance(config.llm.main_model, OpenAIChatCompletionsModel)
