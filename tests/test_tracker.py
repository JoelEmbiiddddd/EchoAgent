from __future__ import annotations

from echoagent.agent.tracker import RuntimeTracker
from echoagent.artifacts.models import ArtifactSettings
from tests.utils import make_state, make_tool_output


def test_tracker_does_not_mutate_state() -> None:
    tracker = RuntimeTracker(
        console=None,
        artifact_settings=ArtifactSettings(enabled=False),
    )
    state = make_state()
    output = make_tool_output("result")

    tracker.on_model_output(state, output, record_payload=True, record_tool_output=True)

    assert len(state.iterations) == 0
