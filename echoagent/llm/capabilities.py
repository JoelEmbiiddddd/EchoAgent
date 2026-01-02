from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping


@dataclass(frozen=True)
class ModelCapabilities:
    supports_json_output: bool = False
    supports_tool_calls: bool = False

    def supports_structured_output(self) -> bool:
        return self.supports_json_output and self.supports_tool_calls


_PROVIDER_DEFAULTS: dict[str, ModelCapabilities] = {
    "openai": ModelCapabilities(supports_json_output=True, supports_tool_calls=True),
    "openai_compatible": ModelCapabilities(supports_json_output=False, supports_tool_calls=False),
}


def resolve_model_capabilities(model_spec: Any) -> ModelCapabilities:
    if isinstance(model_spec, Mapping):
        provider = model_spec.get("provider")
        params = model_spec.get("params")
    else:
        provider = getattr(model_spec, "provider", None)
        params = getattr(model_spec, "params", None)
    if not isinstance(params, Mapping):
        params = {}
    override = _extract_override(params)
    base = _PROVIDER_DEFAULTS.get(provider or "", ModelCapabilities())
    if not override:
        return base
    return _apply_override(base, override)


def _extract_override(params: Mapping[str, Any]) -> dict[str, Any]:
    if "capabilities" in params and isinstance(params["capabilities"], Mapping):
        return dict(params["capabilities"])
    override: dict[str, Any] = {}
    for key in ("supports_structured_output", "supports_json_output", "supports_tool_calls"):
        if key in params:
            override[key] = params[key]
    return override


def _apply_override(base: ModelCapabilities, override: Mapping[str, Any]) -> ModelCapabilities:
    updated = base
    if "supports_structured_output" in override:
        enabled = bool(override["supports_structured_output"])
        updated = replace(updated, supports_json_output=enabled, supports_tool_calls=enabled)
    if "supports_json_output" in override:
        updated = replace(updated, supports_json_output=bool(override["supports_json_output"]))
    if "supports_tool_calls" in override:
        updated = replace(updated, supports_tool_calls=bool(override["supports_tool_calls"]))
    return updated
