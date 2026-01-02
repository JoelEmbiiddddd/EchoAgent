from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional


ToolConflictPolicy = Literal["error", "keep_first", "override"]


def _stringify_schema(schema: Any) -> Optional[str]:
    if schema is None:
        return None
    if isinstance(schema, str):
        return schema
    if isinstance(schema, type):
        return f"{schema.__module__}.{schema.__qualname__}"
    return schema.__class__.__name__


def _stringify_model_value(model: Any) -> Optional[str]:
    if model is None:
        return None
    if isinstance(model, str):
        return model
    if hasattr(model, "model"):
        value = getattr(model, "model", None)
        if isinstance(value, str):
            return value
    if hasattr(model, "model_name"):
        value = getattr(model, "model_name", None)
        if isinstance(value, str):
            return value
    if hasattr(model, "name"):
        value = getattr(model, "name", None)
        if isinstance(value, str):
            return value
    return model.__class__.__name__


def _serialize_config_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {key: _serialize_config_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_serialize_config_value(item) for item in value]
    return value.__class__.__name__


@dataclass
class ToolSpec:
    name: str
    type: str = "local"
    config: dict[str, Any] = field(default_factory=dict)
    tool: Optional[Any] = None

    def to_debug_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "config": _serialize_config_value(self.config),
        }


@dataclass
class ModelSpec:
    provider: Optional[str] = None
    model: Optional[Any] = None
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None
    params: dict[str, Any] = field(default_factory=dict)

    def to_debug_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": _stringify_model_value(self.model),
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "params": _serialize_config_value(self.params),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "params": dict(self.params),
        }


@dataclass
class RunPolicies:
    output_parse_mode: Literal["lenient", "strict"] = "lenient"
    context_budget: Optional[int] = None
    tool_policy: dict[str, Any] = field(default_factory=dict)
    retry_policy: dict[str, Any] = field(default_factory=dict)
    on_tool_name_conflict: ToolConflictPolicy = "error"

    def to_debug_dict(self) -> dict[str, Any]:
        return {
            "output_parse_mode": self.output_parse_mode,
            "context_budget": self.context_budget,
            "tool_policy": _serialize_config_value(self.tool_policy),
            "retry_policy": _serialize_config_value(self.retry_policy),
            "on_tool_name_conflict": self.on_tool_name_conflict,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_parse_mode": self.output_parse_mode,
            "context_budget": self.context_budget,
            "tool_policy": dict(self.tool_policy),
            "retry_policy": dict(self.retry_policy),
            "on_tool_name_conflict": self.on_tool_name_conflict,
        }


@dataclass
class ResolvedProfile:
    name: Optional[str]
    instructions: str
    runtime_template: str
    tools: list[ToolSpec]
    model: ModelSpec
    output_schema: Optional[Any]
    policies: RunPolicies
    context_policy: dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def render(self, **kwargs: Any) -> str:
        kwargs_lower = {k.lower(): str(v) for k, v in kwargs.items()}
        return self.runtime_template.format(**kwargs_lower)

    def get_description(self) -> str:
        if self.description:
            return self.description
        first_line = self.instructions.split("\n")[0].strip()
        if first_line.startswith("You are a "):
            desc = first_line[10:].strip()
        elif first_line.startswith("You are an "):
            desc = first_line[11:].strip()
        else:
            desc = first_line
        return desc[:-1] if desc.endswith(".") else desc

    def runtime_tools(self) -> list[Any]:
        tools: list[Any] = []
        for tool_spec in self.tools:
            if tool_spec.tool is not None:
                tools.append(tool_spec.tool)
            else:
                tools.append(tool_spec.name)
        return tools

    def to_debug_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "runtime_template": self.runtime_template,
            "tools": [tool.to_debug_dict() for tool in self.tools],
            "model": self.model.to_debug_dict(),
            "output_schema": _stringify_schema(self.output_schema),
            "policies": self.policies.to_debug_dict(),
            "context_policy": _serialize_config_value(self.context_policy),
            "metadata": _serialize_config_value(self.metadata),
        }
