from __future__ import annotations

from echoagent.mcp.manager import MCPRegistry
from echoagent.mcp.servers.browser import BROWSER_MCP_SPEC
from echoagent.mcp.servers.chrome_devtools import CHROME_DEVTOOLS_MCP_SPEC


def register_default_servers(registry: MCPRegistry) -> None:
    registry.ensure_server("browser", BROWSER_MCP_SPEC)


__all__ = [
    "BROWSER_MCP_SPEC",
    "CHROME_DEVTOOLS_MCP_SPEC",
    "register_default_servers",
]
