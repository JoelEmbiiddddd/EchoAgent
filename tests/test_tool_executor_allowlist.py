from __future__ import annotations

from typing import Any

import asyncio

from echoagent.context import Context
from echoagent.tools.executor import ToolExecutor
from echoagent.tools.models import ToolCall, ToolContext
from echoagent.tools.registry import ToolRegistry
from echoagent.tools.models import ToolSpec


class DummyTracker:
    def __init__(self, context: Context) -> None:
        self.context = context
        self.panels: list[tuple[str, str]] = []

    def log_panel(self, title: str, content: str, **_: Any) -> None:
        self.panels.append((title, content))

    def on_tool_call(self, *_: Any) -> None:
        return None

    def on_tool_result(self, *_: Any) -> None:
        return None


async def _handler(args: dict[str, Any], ctx: ToolContext) -> str:
    _ = args, ctx
    return "ok"


def test_tool_executor_allowlist_env() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(name="dummy", description="dummy", args_schema={}, result_schema=None, tags=[]),
        _handler,
    )
    executor = ToolExecutor(registry=registry)
    call = ToolCall(name="dummy", args={}, call_id="c1")

    ctx = ToolContext(env={"allowed_tools": ["dummy"]})
    result = asyncio.run(executor.execute(call, context=ctx))
    assert result.ok is True


def test_tool_executor_allowlist_state() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(name="dummy", description="dummy", args_schema={}, result_schema=None, tags=[]),
        _handler,
    )
    executor = ToolExecutor(registry=registry)
    call = ToolCall(name="dummy", args={}, call_id="c2")

    context = Context()
    context.state.execution.allowed_tools = ["other"]
    tracker = DummyTracker(context)
    ctx = ToolContext(env={}, tracker=tracker)

    result = asyncio.run(executor.execute(call, context=ctx))
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "TOOL_NOT_ALLOWED"
    assert context.state.events
    assert context.state.events[-1].type == "TOOL_DENIED"
