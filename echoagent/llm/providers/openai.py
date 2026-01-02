from __future__ import annotations

from typing import Any

from agents import OpenAIResponsesModel
from openai import AsyncOpenAI

from echoagent.llm.capabilities import ModelCapabilities


DEFAULT_BASE_URL = "https://api.openai.com/v1"


def create_models(config: dict[str, Any]) -> tuple[Any, Any, Any]:
    model_name = config.get("model")
    if not model_name:
        raise ValueError("model is required for OpenAI provider")
    base_url = config.get("base_url") or DEFAULT_BASE_URL
    client = AsyncOpenAI(api_key=config.get("api_key"), base_url=base_url)
    model = OpenAIResponsesModel(model=model_name, openai_client=client)
    return model, model, model


def default_capabilities() -> ModelCapabilities:
    return ModelCapabilities(supports_json_output=True, supports_tool_calls=True)
