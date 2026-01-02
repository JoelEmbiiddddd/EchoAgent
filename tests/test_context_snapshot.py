from __future__ import annotations

from echoagent.context import create_conversation_state
from echoagent.context.snapshot import dump_json, dump_jsonl, load_json, load_jsonl
from echoagent.profiles.base import ToolAgentOutput


def test_snapshot_jsonl_roundtrip(tmp_path) -> None:
    state = create_conversation_state()
    state.summary = "sum"
    state.query = {"prompt": "hi"}

    iteration = state.begin_iteration()
    iteration.observation = "obs"
    state.record_payload({"k": "v"})
    iteration.tools.append(ToolAgentOutput(output="tool"))
    iteration.mark_complete()

    path = tmp_path / "snapshot.jsonl"
    dump_jsonl(state, path)
    loaded = load_jsonl(path)

    assert loaded.summary == "sum"
    assert loaded.query == {"prompt": "hi"}
    assert len(loaded.iterations) == 1
    loaded_iteration = loaded.iterations[0]
    assert loaded_iteration.observation == "obs"
    assert loaded_iteration.payloads == [{"k": "v"}]
    assert loaded_iteration.tools[0].output == "tool"


def test_snapshot_json_roundtrip(tmp_path) -> None:
    state = create_conversation_state()
    iteration = state.begin_iteration()
    state.record_payload("payload")
    iteration.mark_complete()

    path = tmp_path / "snapshot.json"
    dump_json(state, path)
    loaded = load_json(path)

    assert len(loaded.iterations) == 1
    assert loaded.iterations[0].payloads == ["payload"]
