from __future__ import annotations

from echoagent.profiles.base import Profile

# Profile instance for browser agent
browser_profile = Profile(
    instructions=(
        "You are a browser agent connected to the Browser MCP server. "
        "Use the available MCP tools to open pages, navigate, click, type, "
        "query content, and return results per the user instructions."
    ),
    runtime_template="{instructions}",
    output_schema=None,
    tools=None,
    mcp_server_names=["browser"],
    model=None,
)
