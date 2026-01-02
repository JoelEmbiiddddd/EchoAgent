from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from echoagent.agent.tracker import get_current_data_store, get_current_tracker
from echoagent.artifacts.models import ArtifactRef
from echoagent.tools.builtins import register_builtin_tools
from echoagent.tools.models import ToolCall, ToolContext, ToolError, ToolResult
from echoagent.tools.registry import ToolRegistry, get_default_registry


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry | None = None,
        context: ToolContext | None = None,
    ) -> None:
        self._registry = registry or get_default_registry()
        self._context = context
        register_builtin_tools(self._registry)

    async def execute(self, call: ToolCall, *, context: ToolContext | None = None) -> ToolResult:
        ctx = _resolve_context(context or self._context)
        spec, handler = self._registry.get(call.name)
        _ = spec
        tracker = ctx.tracker
        if tracker is not None:
            tracker.on_tool_call(None, call)

        start_time = time.perf_counter()
        try:
            result = handler(call.args, ctx)
            if asyncio.iscoroutine(result):
                result = await result
            if isinstance(result, ToolResult):
                tool_result = result
            else:
                artifacts = _extract_artifacts(result)
                tool_result = ToolResult(ok=True, data=result, artifacts=artifacts)
        except Exception as exc:  # noqa: BLE001
            tool_result = ToolResult(
                ok=False,
                error=ToolError(
                    code="TOOL_RUNTIME_ERROR",
                    message=str(exc),
                    details={"type": exc.__class__.__name__},
                ),
            )
        duration = time.perf_counter() - start_time
        tool_result.meta.setdefault("duration_seconds", duration)
        tool_result.meta.setdefault("tool_name", call.name)
        tool_result.meta.setdefault("call_id", call.call_id)
        if tool_result.artifacts:
            tool_result.meta.setdefault(
                "artifacts",
                [artifact.to_dict() for artifact in tool_result.artifacts],
            )
        if tracker is not None:
            tracker.on_tool_result(None, tool_result)
        return tool_result


def _resolve_context(context: ToolContext | None) -> ToolContext:
    if context is None:
        context = ToolContext()
    if context.tracker is None:
        context.tracker = get_current_tracker()
    if context.data_store is None:
        context.data_store = get_current_data_store()
    if context.artifact_store is None and context.tracker is not None:
        store_getter = getattr(context.tracker, "get_run_artifact_store", None)
        if callable(store_getter):
            context.artifact_store = store_getter()
    if context.logger is None:
        context.logger = logging.getLogger("echoagent.tools")
    return context


def _extract_artifacts(result: Any) -> list[ArtifactRef]:
    if isinstance(result, ArtifactRef):
        return [result]
    if isinstance(result, list) and result and all(isinstance(item, ArtifactRef) for item in result):
        return list(result)
    return []
