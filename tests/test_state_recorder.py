from __future__ import annotations

import time

from types import SimpleNamespace

from echoagent.agent.tracking.events import ERROR, MODEL_OUTPUT, USER_MESSAGE, RunEvent
from echoagent.agent.tracking.state_recorder import StateRecorder
from tests.utils import make_context, make_profile, make_state, make_tool_output


class ErrorState:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def record_error(self, error: Exception) -> None:
        self.errors.append(str(error))


def test_state_recorder_records_payload_and_tool_output() -> None:
    profile = make_profile()
    state = make_state(profile=profile)
    context = make_context(profile=profile, state=state)
    recorder = StateRecorder()
    output = make_tool_output("result")
    event = RunEvent(
        type=MODEL_OUTPUT,
        payload={
            "output": output,
            "record_payload": True,
            "record_tool_output": True,
        },
        ts=time.time(),
        run_id="run-1",
    )

    recorder.consume(context, [event])

    assert len(state.iterations) == 1
    iteration = state.iterations[-1]
    assert iteration.payloads
    assert iteration.tools


def test_state_recorder_records_error() -> None:
    state = ErrorState()
    context = SimpleNamespace(state=state)
    recorder = StateRecorder()
    event = RunEvent(
        type=ERROR,
        payload={"error": ValueError("boom")},
        ts=time.time(),
        run_id="run-2",
    )

    recorder.consume(context, [event])

    assert state.errors == ["boom"]


def test_state_recorder_records_user_message_event() -> None:
    profile = make_profile()
    state = make_state(profile=profile)
    context = make_context(profile=profile, state=state)
    recorder = StateRecorder()
    event = RunEvent(
        type=USER_MESSAGE,
        payload={"content": "hi"},
        ts=time.time(),
        run_id="run-3",
    )

    recorder.consume(context, [event])

    assert state.events
    assert state.events[0].type == "USER_MESSAGE"
