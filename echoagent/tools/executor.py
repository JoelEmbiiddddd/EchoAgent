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
        allowlist, active_skill_id = _resolve_allowlist(ctx)
        if allowlist is not None and call.name not in allowlist:
            tool_result = ToolResult(
                ok=False,
                error=ToolError(
                    code="TOOL_NOT_ALLOWED",
                    message=f"Tool '{call.name}' is not allowed",
                ),
            )
            tool_result.meta.setdefault("tool_name", call.name)
            tool_result.meta.setdefault("call_id", call.call_id)
            tool_result.meta.setdefault("allowed_tools", list(allowlist))
            if active_skill_id:
                tool_result.meta.setdefault("active_skill_id", active_skill_id)
            _record_tool_denied(ctx, call, tool_result)
            return tool_result
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


def _resolve_allowlist(ctx: ToolContext) -> tuple[Optional[list[str]], Optional[str]]:
    env_allowed = _normalize_allowlist(ctx.env.get("allowed_tools") if ctx.env else None)
    state_allowed = None
    active_skill_id = None
    tracker = ctx.tracker
    if tracker is not None:
        tracker_context = getattr(tracker, "context", None)
        state = getattr(tracker_context, "state", None)
        execution = getattr(state, "execution", None)
        state_allowed = _normalize_allowlist(getattr(execution, "allowed_tools", None))
        active_skill_id = getattr(execution, "active_skill_id", None)
    return (env_allowed if env_allowed is not None else state_allowed), active_skill_id


def _normalize_allowlist(value: Any) -> Optional[list[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",") if item.strip()]
        return items
    if isinstance(value, (list, tuple, set)):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items
    return None


def _record_tool_denied(ctx: ToolContext, call: ToolCall, tool_result: ToolResult) -> None:
    tracker = ctx.tracker
    message = f"Tool '{call.name}' denied by allowlist"
    if tracker is not None:
        tracker.log_panel("Tool Denied", message)
    tracker_context = getattr(tracker, "context", None) if tracker is not None else None
    state = getattr(tracker_context, "state", None)
    if state is not None:
        state.record_event("TOOL_DENIED", message, meta=dict(tool_result.meta))
