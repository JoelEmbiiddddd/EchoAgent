from __future__ import annotations

from echoagent.mcp.manager import MCPServerSpec


CHROME_DEVTOOLS_MCP_SPEC = MCPServerSpec(
    type="stdio",
    options={
        "cache_tools_list": True,
        "params": {
            "command": "npx",
            "args": ["-y", "chrome-devtools-mcp@latest"],
        },
    },
)
