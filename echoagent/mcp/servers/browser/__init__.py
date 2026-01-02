from __future__ import annotations

import os

from echoagent.mcp.manager import MCPServerSpec


ENV_BROWSERMCP_VERSION = "ECHOAGENT_BROWSERMCP_VERSION"
DEFAULT_BROWSERMCP_PACKAGE = "@browsermcp/mcp"


def _browsermcp_package() -> str:
    override = os.getenv(ENV_BROWSERMCP_VERSION)
    if override:
        override = override.strip()
    if override:
        if override.startswith(DEFAULT_BROWSERMCP_PACKAGE) or override.startswith("@"):
            return override
        return f"{DEFAULT_BROWSERMCP_PACKAGE}@{override}"
    return f"{DEFAULT_BROWSERMCP_PACKAGE}@latest"


BROWSER_MCP_SPEC = MCPServerSpec(
    type="stdio",
    options={
        "cache_tools_list": True,
        "params": {
            "command": "npx",
            "args": ["-y", _browsermcp_package()],
        },
    },
)
