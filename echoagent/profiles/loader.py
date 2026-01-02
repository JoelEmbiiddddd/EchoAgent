from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml

from echoagent.context.policy import ContextPolicy, normalize_context_policy
from echoagent.profiles.models import Profile
from echoagent.profiles.profile_types import ModelSpec
from echoagent.profiles.registry import get_profile_data


def resolve_profile(
    profile_id: Optional[str] = None,
    overrides: Optional[dict[str, Any]] = None,
    path: Optional[str] = None,
    *,
    profile_data: Any = None,
) -> Profile:
    overrides = dict(overrides or {})

    base_data = get_profile_data("base") or {}
    selected_data: dict[str, Any] = {}

    resolved_id = profile_id
    if profile_data is not None:
        selected_data = _coerce_profile_data(profile_data)
        if resolved_id is None:
            resolved_id = selected_data.get("id") or selected_data.get("name")
    elif profile_id:
        selected_data = get_profile_data(profile_id) or _load_legacy_profile_data(profile_id) or {}
        if not selected_data:
            raise ValueError(f"Unknown profile_id: {profile_id}")

    file_overrides = load_from_path(path) if path else {}

    merged = _merge_dicts(base_data, selected_data, file_overrides, overrides)
    merged = _apply_model_fields(merged)
    merged["context_policy"] = _context_policy_to_dict(
        normalize_context_policy(merged.get("context_policy"))
    )
    merged["id"] = merged.get("id") or resolved_id or "base"

    if "system_prompt" in merged:
        if not merged.get("instructions"):
            raise ValueError("Profile instructions are required")
        merged.pop("system_prompt", None)

    profile = _validate_profile(merged)
    return profile


def load_from_path(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Profile config not found: {path}")

    with config_path.open("r", encoding="utf-8") as handle:
        if config_path.suffix in {".yaml", ".yml"}:
            data = yaml.safe_load(handle)
        elif config_path.suffix == ".json":
            data = json.load(handle)
        else:
            raise ValueError(f"Unsupported profile format: {config_path.suffix}")

    if data is None:
        return {}
    if not isinstance(data, Mapping):
        raise ValueError("Profile config must be a mapping")
    return dict(data)


def _merge_dicts(*layers: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for layer in layers:
        if not layer:
            continue
        merged = _merge_mapping(merged, layer)
    return merged


def _merge_mapping(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        out[key] = _merge_value(base.get(key), value)
    return out


def _merge_value(base_value: Any, override_value: Any) -> Any:
    if override_value is None:
        return None
    if isinstance(override_value, list):
        return list(override_value)
    if isinstance(override_value, Mapping) and isinstance(base_value, Mapping):
        merged = dict(base_value)
        merged.update(override_value)
        return merged
    if isinstance(override_value, Mapping):
        return dict(override_value)
    return override_value


# 原: echoagent/profiles/resolver.py:55-118 → 新: echoagent/profiles/loader.py
def _apply_model_fields(data: dict[str, Any]) -> dict[str, Any]:
    raw_model = data.get("model")
    provider = data.get("provider")
    base_url = data.get("base_url")
    api_key_env = data.get("api_key_env")

    params_value = data.get("params") or {}
    params: dict[str, Any] = dict(params_value) if isinstance(params_value, Mapping) else {}

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
        nested_params = raw_model.get("params")
        if isinstance(nested_params, Mapping):
            params = _merge_mapping(params, nested_params)
        raw_model = raw_model.get("model", raw_model.get("value", raw_model.get("name")))

    if provider or base_url or api_key_env or params:
        data["model"] = {
            "provider": provider,
            "model": raw_model,
            "base_url": base_url,
            "api_key_env": api_key_env,
            "params": dict(params),
        }
    else:
        data["model"] = raw_model

    for key in ("provider", "base_url", "api_key_env", "params"):
        data.pop(key, None)
    return data


def _coerce_profile_data(profile_data: Any) -> dict[str, Any]:
    if isinstance(profile_data, Profile):
        return dict(profile_data.to_raw_dict())
    if isinstance(profile_data, Mapping):
        return dict(profile_data)
    if hasattr(profile_data, "model_dump"):
        return dict(profile_data.model_dump())  # type: ignore[call-arg]
    if hasattr(profile_data, "dict"):
        return dict(profile_data.dict())  # type: ignore[call-arg]
    if hasattr(profile_data, "__dict__"):
        return dict(getattr(profile_data, "__dict__"))
    raise TypeError(f"Unsupported profile data type: {type(profile_data).__name__}")


def _candidate_profile_ids(profile_id: str) -> list[str]:
    if profile_id.endswith("_agent"):
        return [profile_id, profile_id[:-6]]
    return [profile_id]


def _load_legacy_profile_data(profile_id: str) -> Optional[dict[str, Any]]:
    for candidate in _candidate_profile_ids(profile_id):
        module = _import_legacy_module(candidate)
        if module is None:
            continue
        data = _extract_profile_data(module, candidate)
        if data is None:
            continue
        if not data.get("id"):
            data["id"] = candidate
        return data
    return None


def _import_legacy_module(profile_id: str) -> Optional[Any]:
    for package in ("manager", "web", "data", "debug", "mcp"):
        module_name = f"echoagent.profiles.{package}.{profile_id}"
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            parent_name = module_name.rsplit(".", 1)[0]
            if exc.name in {module_name, parent_name}:
                continue
            raise
    return None


def _extract_profile_data(module: Any, profile_id: str) -> Optional[dict[str, Any]]:
    attr_name = f"{profile_id}_profile"
    if hasattr(module, attr_name):
        return _coerce_profile_data(getattr(module, attr_name))

    for name, value in vars(module).items():
        if name.startswith("_") or not name.endswith("_profile"):
            continue
        if isinstance(value, Profile) or isinstance(value, Mapping):
            return _coerce_profile_data(value)
    return None


def _validate_profile(data: dict[str, Any]) -> Profile:
    if hasattr(Profile, "model_validate"):
        profile = Profile.model_validate(data)
    else:
        profile = Profile.parse_obj(data)

    if not profile.instructions or not profile.instructions.strip():
        raise ValueError("Profile instructions are required")
    if not isinstance(profile.mcp_server_names, list):
        raise ValueError("Profile mcp_server_names must be a list")
    if any(not isinstance(name, str) for name in profile.mcp_server_names):
        raise ValueError("Profile mcp_server_names must be list[str]")
    return profile


def _context_policy_to_dict(policy: ContextPolicy) -> dict[str, Any]:
    if not isinstance(policy, ContextPolicy):
        return {}
    blocks: dict[str, Any] = {}
    for name, block_policy in (policy.blocks or {}).items():
        payload: dict[str, Any] = {}
        if block_policy.enabled is not True:
            payload["enabled"] = block_policy.enabled
        if block_policy.max_chars is not None:
            payload["max_chars"] = block_policy.max_chars
        blocks[name] = payload or {"enabled": True}
    data: dict[str, Any] = {}
    if policy.total_budget is not None:
        data["total_budget"] = policy.total_budget
    if blocks:
        data["blocks"] = blocks
    return data
