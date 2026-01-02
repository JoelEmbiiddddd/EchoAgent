from __future__ import annotations


def mcp_browser_profile_data() -> dict[str, object]:
    return {
        "id": "mcp_browser",
        "instructions": (
            "You are a browser agent connected to the Browser MCP server. "
            "Use the available MCP tools to open pages, navigate, click, type, "
            "query content, and return results per the user instructions."
        ),
        "runtime_template": "{instructions}",
        "model": None,
        "tools": None,
        "mcp_server_names": ["browser"],
        "description": "Browser MCP profile defaults.",
        "policies": {},
        "budget": {},
        "output": {},
        "runtime": {},
        "metadata": {},
    }
