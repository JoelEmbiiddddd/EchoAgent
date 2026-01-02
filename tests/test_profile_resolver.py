from __future__ import annotations

import sys
from pathlib import Path

import pytest

from echoagent.profiles.loader import resolve_profile


def test_resolve_profile_list_override() -> None:
    profile_data = {
        "instructions": "base",
        "runtime_template": "",
        "model": "gpt-4",
        "tools": ["tool_a"],
    }

    resolved = resolve_profile(
        "test",
        {"tools": ["tool_b"]},
        profile_data=profile_data,
    )

    assert resolved.tools == ["tool_b"]


def test_resolve_profile_dict_shallow_merge() -> None:
    profile_data = {
        "instructions": "base",
        "runtime_template": "",
        "model": "gpt-4",
        "runtime": {"a": 1, "b": 2},
    }

    resolved = resolve_profile(
        "test",
        {"runtime": {"b": 3}},
        profile_data=profile_data,
    )

    assert resolved.runtime == {"a": 1, "b": 3}


def test_resolve_profile_file_overrides(tmp_path: Path) -> None:
    profile_data = {
        "instructions": "base",
        "runtime_template": "",
        "model": "gpt-4",
    }
    config_path = tmp_path / "profile.yaml"
    config_path.write_text(
        "instructions: file\n"
        "runtime_template: X\n"
        "model: gpt-4\n"
        "tools:\n"
        "  - tool_a\n",
        encoding="utf-8",
    )

    resolved = resolve_profile(
        "test",
        {"instructions": "override"},
        path=str(config_path),
        profile_data=profile_data,
    )

    assert resolved.instructions == "override"
    assert resolved.tools == ["tool_a"]


def test_resolve_profile_legacy_observe() -> None:
    resolved = resolve_profile("observe")

    assert "research observation" in resolved.instructions


def test_resolve_profile_registry_mcp_browser() -> None:
    resolved = resolve_profile("mcp_browser")

    assert resolved.mcp_server_names == ["browser"]


def test_resolve_profile_system_prompt_rejected() -> None:
    profile_data = {
        "instructions": "",
        "runtime_template": "",
        "model": "gpt-4",
    }

    with pytest.raises(ValueError):
        resolve_profile(
            "test",
            {"system_prompt": "legacy", "instructions": None},
            profile_data=profile_data,
        )


def test_profiles_import_no_side_effects() -> None:
    for name in list(sys.modules):
        if name == "echoagent.profiles" or name.startswith("echoagent.profiles."):
            sys.modules.pop(name)

    import echoagent.profiles  # noqa: F401

    assert "echoagent.profiles.manager.observe" not in sys.modules
    assert "echoagent.profiles.web.web_searcher" not in sys.modules


def test_resolve_profile_context_policy_aliases() -> None:
    profile_data = {
        "instructions": "base",
        "runtime_template": "",
        "model": "gpt-4",
        "context_policy": {
            "blocks": {
                "history": {"enabled": False},
                "tool_results": {"max_chars": 120},
            }
        },
    }

    resolved = resolve_profile("test", profile_data=profile_data)

    blocks = resolved.context_policy.get("blocks", {})
    assert blocks["PREVIOUS_ITERATIONS"]["enabled"] is False
    assert blocks["TOOL_RESULTS"]["max_chars"] == 120
