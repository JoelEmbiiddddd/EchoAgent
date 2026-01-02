from __future__ import annotations

import asyncio

from echoagent.mcp import manager as mcp_manager
from echoagent.mcp.manager import MCPManagerSession, MCPRegistry, MCPServerSpec
from echoagent.mcp.servers import register_default_servers


def test_registry_ensure_server_respects_existing() -> None:
    existing = MCPServerSpec(type="stdio", options={"params": {"command": "echo"}})
    registry = MCPRegistry({"browser": existing})

    register_default_servers(registry)

    assert registry.get("browser") is existing


def test_session_cache_and_patch_hook(monkeypatch) -> None:
    events: list[str] = []

    def fake_patch() -> None:
        events.append("patch")

    class DummyServer:
        def __init__(self, **kwargs):
            events.append("init")
            self.kwargs = kwargs

        async def __aenter__(self):
            events.append("enter")
            return self

        async def __aexit__(self, exc_type, exc, tb):
            events.append("exit")

    monkeypatch.setattr(mcp_manager, "apply_browsermcp_close_patch", fake_patch)
    monkeypatch.setitem(mcp_manager.SERVER_TYPE_MAP, "stdio", DummyServer)

    registry = MCPRegistry(
        {
            "browser": MCPServerSpec(type="stdio", options={"params": {"command": "noop"}}),
        }
    )
    session = MCPManagerSession(registry)

    async def run_session() -> None:
        async with session:
            first = await session.get_server("browser")
            second = await session.get_server("browser")
            assert first is second

    asyncio.run(run_session())

    assert events.count("patch") == 1
    assert events[0] == "patch"
