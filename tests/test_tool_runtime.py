import asyncio
import json
import warnings

from agents.tool import ToolContext as AgentsToolContext
from echoagent.tools.executor import ToolExecutor
from echoagent.tools.models import ToolCall, ToolContext, ToolSpec
from echoagent.tools.registry import ToolRegistry, reset_default_registry
from echoagent.tools.web_tools import web_search


def test_tool_registry_register_and_get() -> None:
    registry = ToolRegistry()
    spec = ToolSpec(
        name="dummy",
        description="dummy",
        args_schema={"type": "object", "properties": {}},
    )

    def handler(args, ctx):
        _ = args, ctx
        return "ok"

    registry.register(spec, handler)
    got_spec, got_handler = registry.get("dummy")
    assert got_spec.name == "dummy"
    assert got_handler is handler
    assert [item.name for item in registry.list()] == ["dummy"]


def test_tool_executor_success() -> None:
    registry = ToolRegistry()
    spec = ToolSpec(
        name="sum",
        description="sum",
        args_schema={"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}},
    )

    def handler(args, ctx):
        _ = ctx
        return args["a"] + args["b"]

    registry.register(spec, handler)
    executor = ToolExecutor(registry=registry, context=ToolContext())

    async def _run():
        call = ToolCall(name="sum", args={"a": 1, "b": 2}, call_id="call-1")
        return await executor.execute(call)

    result = asyncio.run(_run())
    assert result.ok is True
    assert result.data == 3
    assert "duration_seconds" in result.meta


def test_tool_executor_failure() -> None:
    registry = ToolRegistry()
    spec = ToolSpec(
        name="boom",
        description="boom",
        args_schema={"type": "object", "properties": {}},
    )

    def handler(args, ctx):
        _ = args, ctx
        raise RuntimeError("boom")

    registry.register(spec, handler)
    executor = ToolExecutor(registry=registry, context=ToolContext())

    async def _run():
        call = ToolCall(name="boom", args={}, call_id="call-2")
        return await executor.execute(call)

    result = asyncio.run(_run())
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "TOOL_RUNTIME_ERROR"


def test_tool_executor_tracker_hooks() -> None:
    registry = ToolRegistry()
    spec = ToolSpec(
        name="echo",
        description="echo",
        args_schema={"type": "object", "properties": {"text": {"type": "string"}}},
    )

    def handler(args, ctx):
        _ = ctx
        return args["text"]

    registry.register(spec, handler)

    class FakeTracker:
        def __init__(self) -> None:
            self.events: list[tuple[str, object]] = []

        def on_tool_call(self, state, tool_call) -> None:
            _ = state
            self.events.append(("call", tool_call))

        def on_tool_result(self, state, tool_result) -> None:
            _ = state
            self.events.append(("result", tool_result))

    tracker = FakeTracker()
    executor = ToolExecutor(registry=registry, context=ToolContext(tracker=tracker))

    async def _run():
        call = ToolCall(name="echo", args={"text": "hi"}, call_id="call-3")
        return await executor.execute(call)

    result = asyncio.run(_run())
    assert result.ok is True
    assert [event[0] for event in tracker.events] == ["call", "result"]


def test_legacy_wrapper_forwards_to_executor() -> None:
    registry = ToolRegistry()
    spec = ToolSpec(
        name="web_search",
        description="web",
        args_schema={"type": "object", "properties": {"query": {"type": "string"}}},
    )

    async def handler(args, ctx):
        _ = ctx
        return {"query": args["query"]}

    registry.register(spec, handler)
    reset_default_registry(registry)

    async def _run():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            payload = json.dumps({"query": "banana"})
            ctx = AgentsToolContext(
                context=None,
                tool_name="web_search",
                tool_call_id="call-legacy",
                tool_arguments=payload,
            )
            return await web_search.on_invoke_tool(ctx, payload)

    try:
        result = asyncio.run(_run())
    finally:
        reset_default_registry()

    assert result == {"query": "banana"}
