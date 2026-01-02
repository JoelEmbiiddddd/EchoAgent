from __future__ import annotations


def base_profile_data() -> dict[str, object]:
    return {
        "id": "base",
        "instructions": "You are a helpful assistant.",
        "runtime_template": "{instructions}",
        "model": None,
        "tools": None,
        "mcp_server_names": [],
        "description": "Base profile defaults.",
        "policies": {},
        "budget": {},
        "output": {},
        "runtime": {},
        "metadata": {},
    }
