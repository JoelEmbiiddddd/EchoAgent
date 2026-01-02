from __future__ import annotations

from typing import Any

from echoagent.llm.providers import openai, openai_compatible


_PROVIDERS: dict[str, Any] = {
    "openai": openai,
    "openai_compatible": openai_compatible,
}


def get_provider(name: str):
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise ValueError(f"Unsupported provider: {name}")
    return provider


__all__ = ["get_provider"]
