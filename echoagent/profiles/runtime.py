from __future__ import annotations

from typing import Any, Mapping

from echoagent.context.policy import normalize_context_policy
from echoagent.profiles.profile_types import (
    ModelSpec,
    RunPolicies,
    ToolConflictPolicy,
    ToolSpec,
    _serialize_config_value,
    _stringify_schema,
)


# 原: echoagent/profiles/resolver.py:167-249 → 新: echoagent/profiles/runtime.py
def normalize_policies(policies: Any) -> RunPolicies:
    if policies is None:
        return RunPolicies()
    if isinstance(policies, RunPolicies):
        return policies
    if not isinstance(policies, Mapping):
        return RunPolicies()

    on_conflict = policies.get("on_tool_name_conflict", "error")
    if on_conflict not in ("error", "keep_first", "override"):
        raise ValueError(f"Unsupported tool conflict policy: {on_conflict}")

    output_parse_mode = policies.get("output_parse_mode", "lenient")
    if output_parse_mode not in ("lenient", "strict"):
        raise ValueError(f"Unsupported output_parse_mode: {output_parse_mode}")

    context_budget = policies.get("context_budget")
    tool_policy = policies.get("tool_policy") or {}
    retry_policy = policies.get("retry_policy") or {}

    return RunPolicies(
        output_parse_mode=output_parse_mode,
        context_budget=context_budget,
        tool_policy=dict(tool_policy),
        retry_policy=dict(retry_policy),
        on_tool_name_conflict=on_conflict,  # type: ignore[arg-type]
    )


# 原: echoagent/profiles/resolver.py:181-249 → 新: echoagent/profiles/runtime.py
def normalize_tools(tools: list[Any], conflict_policy: ToolConflictPolicy) -> list[ToolSpec]:
    normalized = [normalize_tool(tool) for tool in tools]
    return _apply_tool_conflict_policy(normalized, conflict_policy)


def normalize_tool(tool: Any) -> ToolSpec:
    if isinstance(tool, ToolSpec):
        return tool
    if isinstance(tool, str):
        return ToolSpec(name=tool, type="local", config={}, tool=tool)
    if isinstance(tool, Mapping):
        if _looks_like_function_tool(tool):
            function_tool = _rehydrate_function_tool(tool)
            return ToolSpec(name=function_tool.name, type="local", config={}, tool=function_tool)
        tool_obj = tool.get("tool") or tool.get("callable")
        name = tool.get("name")
        if not name and tool_obj is not None:
            name = getattr(tool_obj, "name", None) or getattr(tool_obj, "__name__", None)
        if not name:
            raise ValueError("Tool entry missing name")
        tool_type = tool.get("type", "local")
        config = dict(tool.get("config") or {})
        for key, value in tool.items():
            if key in {"name", "type", "config", "tool", "callable"}:
                continue
            config[key] = value
        return ToolSpec(name=str(name), type=str(tool_type), config=config, tool=tool_obj)

    name = getattr(tool, "name", None) or getattr(tool, "__name__", None) or tool.__class__.__name__
    return ToolSpec(name=str(name), type="local", config={}, tool=tool)


def _looks_like_function_tool(payload: Mapping[str, Any]) -> bool:
    return bool(payload.get("name") and payload.get("params_json_schema") and payload.get("on_invoke_tool"))


def _rehydrate_function_tool(payload: Mapping[str, Any]) -> Any:
    from agents.tool import FunctionTool

    on_invoke_tool = payload.get("on_invoke_tool")
    if not callable(on_invoke_tool):
        raise ValueError("Function tool payload missing on_invoke_tool")
    return FunctionTool(
        name=str(payload.get("name", "")),
        description=str(payload.get("description", "")),
        params_json_schema=dict(payload.get("params_json_schema") or {}),
        on_invoke_tool=on_invoke_tool,
        strict_json_schema=bool(payload.get("strict_json_schema", True)),
        is_enabled=payload.get("is_enabled", True),
        tool_input_guardrails=payload.get("tool_input_guardrails"),
        tool_output_guardrails=payload.get("tool_output_guardrails"),
    )


def _apply_tool_conflict_policy(tools: list[ToolSpec], conflict_policy: ToolConflictPolicy) -> list[ToolSpec]:
    seen: dict[str, int] = {}
    resolved: list[ToolSpec] = []
    for tool in tools:
        if tool.name in seen:
            if conflict_policy == "error":
                raise ValueError(f"Duplicate tool name: {tool.name}")
            if conflict_policy == "keep_first":
                continue
            if conflict_policy == "override":
                index = seen[tool.name]
                resolved[index] = tool
                continue
        seen[tool.name] = len(resolved)
        resolved.append(tool)
    return resolved


# 原: echoagent/profiles/resolver.py:240-270 → 新: echoagent/profiles/runtime.py
def normalize_model(model_data: Any) -> ModelSpec:
    if isinstance(model_data, ModelSpec):
        return model_data
    if isinstance(model_data, Mapping):
        provider = model_data.get("provider") or "openai"
        base_url = model_data.get("base_url")
        api_key_env = model_data.get("api_key_env")
        params = model_data.get("params") or {}
        model_value = model_data.get("model")
        return ModelSpec(
            provider=provider,
            model=model_value,
            base_url=base_url,
            api_key_env=api_key_env,
            params=dict(params),
        )
    return ModelSpec(provider="openai", model=model_data)


# 原: echoagent/profiles/profile_types.py:147-156 → 新: echoagent/profiles/runtime.py
def runtime_tools(tool_specs: list[ToolSpec]) -> list[Any]:
    tools: list[Any] = []
    for tool_spec in tool_specs:
        tool_obj = tool_spec.tool
        if isinstance(tool_obj, str) or tool_obj is None:
            tools.append(_resolve_registry_tool(tool_spec.name))
            continue
        if callable(tool_obj):
            tools.append(_wrap_callable_tool(tool_obj))
            continue
        tools.append(tool_obj)
    return tools


def _wrap_callable_tool(tool: Any) -> Any:
    from agents import function_tool

    return function_tool(tool)


def _resolve_registry_tool(tool_name: str) -> Any:
    import json
    import uuid

    from agents.tool import FunctionTool
    from echoagent.tools.builtins import register_builtin_tools
    from echoagent.tools.executor import ToolExecutor
    from echoagent.tools.models import ToolCall
    from echoagent.tools.registry import get_default_registry

    registry = get_default_registry()
    register_builtin_tools(registry)
    spec, _handler = registry.get(tool_name)

    async def _invoke_tool(ctx: Any, args_json: str) -> Any:
        try:
            args = json.loads(args_json) if args_json else {}
        except json.JSONDecodeError as exc:
            return f"Invalid tool arguments: {exc}"

        call_id = getattr(ctx, "tool_call_id", None) or uuid.uuid4().hex
        result = await ToolExecutor(registry=registry).execute(
            ToolCall(name=spec.name, args=args, call_id=call_id)
        )
        if result.ok:
            return result.data
        if result.error and result.error.message:
            return f"Tool error: {result.error.message}"
        return "Tool error: Unknown error"

    return FunctionTool(
        name=spec.name,
        description=spec.description,
        params_json_schema=spec.args_schema,
        on_invoke_tool=_invoke_tool,
    )


def profile_debug_dict(profile: Any) -> dict[str, Any]:
    policies = normalize_policies(getattr(profile, "policies", None))
    raw_tools = list(getattr(profile, "tools", []) or [])
    tool_specs = normalize_tools(raw_tools, policies.on_tool_name_conflict)
    model_spec = normalize_model(getattr(profile, "model", None))
    context_policy = normalize_context_policy(getattr(profile, "context_policy", None))
    return {
        "name": getattr(profile, "id", None),
        "runtime_template": getattr(profile, "runtime_template", ""),
        "tools": [tool.to_debug_dict() for tool in tool_specs],
        "model": model_spec.to_debug_dict(),
        "output_schema": _stringify_schema(getattr(profile, "output_schema", None)),
        "policies": policies.to_debug_dict(),
        "context_policy": _serialize_config_value(_context_policy_to_dict(context_policy)),
        "metadata": _serialize_config_value(getattr(profile, "metadata", {}) or {}),
    }


def _context_policy_to_dict(policy: Any) -> dict[str, Any]:
    if policy is None:
        return {}
    blocks = {}
    for name, block_policy in (getattr(policy, "blocks", {}) or {}).items():
        payload = {"enabled": block_policy.enabled}
        if block_policy.max_chars is not None:
            payload["max_chars"] = block_policy.max_chars
        blocks[name] = payload
    data: dict[str, Any] = {}
    total_budget = getattr(policy, "total_budget", None)
    if total_budget is not None:
        data["total_budget"] = total_budget
    if blocks:
        data["blocks"] = blocks
    return data
