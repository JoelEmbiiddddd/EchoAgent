from __future__ import annotations

from echoagent.context import create_conversation_state
from echoagent.context.snapshot import dump_json, load_json
from echoagent.context.state import IterationDigest


def test_snapshot_path_roundtrip(tmp_path) -> None:
    state = create_conversation_state()
    iteration = state.begin_iteration()
    iteration.observation = "obs"
    iteration.set_digest(IterationDigest(summary="summary"))
    iteration.mark_complete()

    snapshot_path = tmp_path / "snapshots" / "iter_1.json"
    dump_json(state, snapshot_path)
    restored = load_json(snapshot_path)

    assert restored.iterations
    assert restored.iterations[0].digest is not None
    assert restored.iterations[0].digest.summary == "summary"
