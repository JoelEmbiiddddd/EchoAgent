from __future__ import annotations

from typing import Any, Iterable

from echoagent.agent.tracking.events import (
    ASSISTANT_MESSAGE,
    ERROR,
    MODEL_OUTPUT,
    TOOL_OUTPUT,
    TOOL_RESULT,
    USER_MESSAGE,
    RunEvent,
)
from echoagent.utils.helpers import serialize_content


class StateRecorder:
    """统一处理运行事件并写入状态。"""

    def consume(self, context: Any, events: Iterable[RunEvent]) -> None:
        state = getattr(context, "state", None)
        if state is None:
            return

        for event in events:
            if event.type in (MODEL_OUTPUT, TOOL_OUTPUT):
                self._record_output(state, event)
            elif event.type == TOOL_RESULT:
                self._record_tool_result(state, event)
            elif event.type == USER_MESSAGE:
                self._record_user_message(state, event)
            elif event.type == ASSISTANT_MESSAGE:
                self._record_assistant_message(state, event)
            elif event.type == ERROR:
                self._record_error(state, event)

    def _record_output(self, state: Any, event: RunEvent) -> None:
        payload = event.payload
        output = payload.get("output")
        record_payload = payload.get("record_payload", False)
        record_tool_output = payload.get("record_tool_output", False)

        if record_payload:
            try:
                state.record_payload(output)
            except Exception:
                pass

        if record_tool_output:
            try:
                iteration = state.current_iteration
            except Exception:
                iteration = None
            if iteration is not None:
                try:
                    iteration.tools.append(output)
                except Exception:
                    pass

        if output is None:
            return
        record_event = getattr(state, "record_event", None)
        if not callable(record_event):
            return

        content = serialize_content(output)
        if content:
            record_event(
                "ASSISTANT_MESSAGE",
                content,
                meta={
                    "agent_name": payload.get("agent_name"),
                    "profile_name": payload.get("profile_name"),
                },
            )
        if record_tool_output and content:
            record_event(
                "TOOL_RESULT",
                content,
                meta={
                    "tool_name": payload.get("tool_name") or payload.get("agent_name"),
                    "agent_name": payload.get("agent_name"),
                    "profile_name": payload.get("profile_name"),
                },
            )

    def _record_user_message(self, state: Any, event: RunEvent) -> None:
        payload = event.payload
        content = payload.get("content")
        record_event = getattr(state, "record_event", None)
        if not callable(record_event) or not content:
            return
        record_event(
            "USER_MESSAGE",
            content,
            meta=payload.get("meta") or {},
        )

    def _record_assistant_message(self, state: Any, event: RunEvent) -> None:
        payload = event.payload
        content = payload.get("content")
        record_event = getattr(state, "record_event", None)
        if not callable(record_event) or not content:
            return
        record_event(
            "ASSISTANT_MESSAGE",
            content,
            meta=payload.get("meta") or {},
        )

    def _record_tool_result(self, state: Any, event: RunEvent) -> None:
        payload = event.payload
        content = payload.get("content")
        record_event = getattr(state, "record_event", None)
        if not callable(record_event) or not content:
            return
        record_event(
            "TOOL_RESULT",
            content,
            meta=payload.get("meta") or {},
        )

    def _record_error(self, state: Any, event: RunEvent) -> None:
        record_error = getattr(state, "record_error", None)
        if not callable(record_error):
            return
        try:
            record_error(event.payload.get("error"))
        except Exception:
            pass
