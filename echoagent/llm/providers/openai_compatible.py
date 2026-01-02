from __future__ import annotations

from typing import Any

from agents import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

from echoagent.llm.capabilities import ModelCapabilities


def create_models(config: dict[str, Any]) -> tuple[Any, Any, Any]:
    model_name = config.get("model")
    if not model_name:
        raise ValueError("model is required for openai_compatible provider")
    base_url = config.get("base_url")
    if not base_url:
        raise ValueError("base_url is required for openai_compatible provider")
    client = AsyncOpenAI(api_key=config.get("api_key"), base_url=base_url)
    model = OpenAIChatCompletionsModel(model=model_name, openai_client=client)
    return model, model, model


def default_capabilities() -> ModelCapabilities:
    return ModelCapabilities(supports_json_output=False, supports_tool_calls=False)
