from __future__ import annotations

from echoagent.llm.capabilities import resolve_model_capabilities
from echoagent.profiles.profile_types import ModelSpec


def test_capabilities_defaults() -> None:
    openai_spec = ModelSpec(provider="openai", model="gpt-4")
    openai_caps = resolve_model_capabilities(openai_spec)
    assert openai_caps.supports_structured_output()

    compat_spec = ModelSpec(provider="openai_compatible", model="deepseek")
    compat_caps = resolve_model_capabilities(compat_spec)
    assert not compat_caps.supports_structured_output()


def test_capabilities_override() -> None:
    spec = ModelSpec(
        provider="openai_compatible",
        model="deepseek",
        params={"capabilities": {"supports_structured_output": True}},
    )
    caps = resolve_model_capabilities(spec)
    assert caps.supports_structured_output()
