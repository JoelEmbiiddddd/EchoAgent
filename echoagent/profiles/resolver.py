from __future__ import annotations

from typing import Any, Mapping, Optional

from echoagent.profiles.base import Profile
from echoagent.profiles.profile_types import (
    ModelSpec,
    ResolvedProfile,
    RunPolicies,
    ToolSpec,
    ToolConflictPolicy,
)
from echoagent.utils.config import _deep_merge


ProfileLike = Any


class ProfileResolver:
    def resolve(self, profile: ProfileLike, overrides: Optional[dict[str, Any]] = None) -> ResolvedProfile:
        loaded = self._load(profile)
        merged = self._merge_overrides(loaded, overrides or {})
        resolved = self._normalize(merged)
        self._validate(resolved)
        return resolved

    def _load(self, profile: ProfileLike) -> dict[str, Any]:
        if isinstance(profile, Profile):
            return {
                "name": getattr(profile, "_key", None),
                "instructions": profile.instructions,
                "runtime_template": profile.runtime_template,
                "tools": profile.tools,
                "model": profile.model,
                "output_schema": profile.output_schema,
                "description": profile.description,
                "policies": None,
                "context_policy": getattr(profile, "context_policy", None),
                "provider": None,
                "base_url": None,
                "api_key_env": None,
                "params": None,
            }
        if isinstance(profile, Mapping):
            return {
                "name": profile.get("name"),
                "instructions": profile.get("instructions"),
                "runtime_template": profile.get("runtime_template", ""),
                "tools": profile.get("tools"),
                "model": profile.get("model"),
                "output_schema": profile.get("output_schema"),
                "description": profile.get("description"),
                "policies": profile.get("policies"),
                "context_policy": profile.get("context_policy"),
                "provider": profile.get("provider"),
                "base_url": profile.get("base_url"),
                "api_key_env": profile.get("api_key_env"),
                "params": profile.get("params"),
            }
        if hasattr(profile, "model_dump"):
            data = profile.model_dump()
            return self._load(data)
        if hasattr(profile, "dict"):
            data = profile.dict()  # type: ignore[call-arg]
            return self._load(data)
        if hasattr(profile, "__dict__"):
            data = dict(getattr(profile, "__dict__"))
            return self._load(data)
        raise TypeError(f"Unsupported profile type: {type(profile).__name__}")

    def _merge_overrides(self, raw: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
        policies = self._merge_policies(raw.get("policies"), overrides.get("policies"))
        model_data = self._merge_model(raw, overrides)

        merged = {
            "name": raw.get("name"),
            "instructions": overrides.get("instructions", raw.get("instructions", "")),
            "runtime_template": raw.get("runtime_template", "") or "",
            "tools": overrides.get("tools", raw.get("tools") or []),
            "model": model_data,
            "output_schema": overrides.get("output_schema", raw.get("output_schema")),
            "description": raw.get("description"),
            "policies": policies,
            "context_policy": overrides.get("context_policy", raw.get("context_policy") or {}),
            "metadata": overrides.get("metadata", {}),
        }
        return merged

    def _merge_model(self, raw: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
        raw_model = raw.get("model")
        provider = raw.get("provider")
        base_url = raw.get("base_url")
        api_key_env = raw.get("api_key_env")
        params = raw.get("params") or {}
        if not isinstance(params, Mapping):
            params = {}

        if isinstance(raw_model, ModelSpec):
            provider = raw_model.provider
            base_url = raw_model.base_url
            api_key_env = raw_model.api_key_env
            params = dict(raw_model.params)
            raw_model = raw_model.model
        elif isinstance(raw_model, Mapping):
            provider = raw_model.get("provider", provider)
            base_url = raw_model.get("base_url", base_url)
            api_key_env = raw_model.get("api_key_env", api_key_env)
            params = raw_model.get("params", params)
            if not isinstance(params, Mapping):
                params = {}
            raw_model = raw_model.get("model", raw_model.get("value", raw_model.get("name")))

        if "model" in overrides:
            raw_model = overrides.get("model")
        if "provider" in overrides:
            provider = overrides.get("provider")
        if "base_url" in overrides:
            base_url = overrides.get("base_url")
        if "api_key_env" in overrides:
            api_key_env = overrides.get("api_key_env")
        override_params = overrides.get("params")
        if isinstance(override_params, Mapping):
            params = _deep_merge(dict(params), override_params)

        return {
            "provider": provider,
            "model": raw_model,
            "base_url": base_url,
            "api_key_env": api_key_env,
            "params": params or {},
        }

    def _merge_policies(self, raw: Any, overrides: Any) -> dict[str, Any]:
        raw_dict = self._policies_to_dict(raw)
        overrides_dict = self._policies_to_dict(overrides)
        return _deep_merge(raw_dict, overrides_dict) if overrides_dict else raw_dict

    def _policies_to_dict(self, policies: Any) -> dict[str, Any]:
        if policies is None:
            return {}
        if isinstance(policies, RunPolicies):
            return policies.to_dict()
        if isinstance(policies, Mapping):
            return dict(policies)
        return {}

    def _normalize(self, merged: dict[str, Any]) -> ResolvedProfile:
        policies = self._normalize_policies(merged.get("policies") or {})
        tools = self._normalize_tools(merged.get("tools") or [], policies.on_tool_name_conflict)
        model = self._normalize_model(merged.get("model") or {})

        return ResolvedProfile(
            name=merged.get("name"),
            instructions=str(merged.get("instructions") or ""),
            runtime_template=str(merged.get("runtime_template") or ""),
            tools=tools,
            model=model,
            output_schema=merged.get("output_schema"),
            policies=policies,
            context_policy=merged.get("context_policy") or {},
            description=merged.get("description"),
            metadata=merged.get("metadata") or {},
        )

    def _normalize_policies(self, policies: dict[str, Any]) -> RunPolicies:
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

    def _normalize_tools(
        self,
        tools: list[Any],
        conflict_policy: ToolConflictPolicy,
    ) -> list[ToolSpec]:
        normalized = [self._normalize_tool(tool) for tool in tools]
        return self._apply_tool_conflict_policy(normalized, conflict_policy)

    def _normalize_tool(self, tool: Any) -> ToolSpec:
        if isinstance(tool, ToolSpec):
            return tool
        if isinstance(tool, str):
            return ToolSpec(name=tool, type="local", config={}, tool=tool)
        if isinstance(tool, Mapping):
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

    def _apply_tool_conflict_policy(
        self,
        tools: list[ToolSpec],
        conflict_policy: ToolConflictPolicy,
    ) -> list[ToolSpec]:
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

    def _normalize_model(self, model_data: Any) -> ModelSpec:
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

    def _validate(self, profile: ResolvedProfile) -> None:
        if not profile.instructions.strip():
            raise ValueError("Profile instructions are required")
        if profile.model.model is None or (isinstance(profile.model.model, str) and not profile.model.model.strip()):
            raise ValueError("Profile model is required")
