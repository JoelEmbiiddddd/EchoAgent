from __future__ import annotations

import json

from echoagent.observability.runlog import RunEventWriter, RunIndexBuilder, RunLog


def test_runlog_writes_index_and_jsonl(tmp_path) -> None:
    run_id = "run-1"
    run_dir = tmp_path / "runs" / run_id
    runlog_path = run_dir / "runlog" / "runlog.jsonl"
    index_path = run_dir / "runlog" / "run_index.json"

    writer = RunEventWriter(runlog_path, run_id)
    index = RunIndexBuilder(run_id)
    runlog = RunLog(writer, index, index_path)

    runlog.emit(
        "RUN_START",
        {
            "pipeline_slug": "demo",
            "workflow_name": "demo",
            "experiment_id": run_id,
            "provider": "openai",
            "model": "test",
        },
    )
    runlog.emit("ITERATION_START", {"iteration": 1, "group_id": "iter-1"})
    runlog.emit(
        "ERROR",
        {
            "where": "snapshot",
            "exception_type": "ValueError",
            "message": "boom",
            "traceback": "trace",
            "iteration": 1,
        },
    )
    runlog.emit(
        "ARTIFACT_WRITTEN",
        {
            "type": "run_report",
            "path": "reports/final_report.md",
            "artifact": {
                "id": "a",
                "kind": "TEXT",
                "uri": "reports/final_report.md",
                "path": "reports/final_report.md",
                "meta": {},
            },
        },
    )
    runlog.emit(
        "ITERATION_END",
        {
            "iteration": 1,
            "group_id": "iter-1",
            "snapshot": {"path": "snapshots/iter_1.json", "hash": "abc"},
        },
    )
    runlog.emit("RUN_END", {"status": "success"})
    runlog.close()

    lines = runlog_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 6
    events = [json.loads(line) for line in lines]

    index_data = json.loads(index_path.read_text(encoding="utf-8"))
    assert index_data["run_id"] == run_id
    assert index_data["counts"]["iterations"] == 1
    assert index_data["counts"]["errors"] == 1
    assert index_data["counts"]["snapshots"] == 1
    assert index_data["counts"]["artifacts"] == 1
    assert len(index_data["iterations"]) == 1
    assert index_data["iterations"][0]["start_seq"] is not None
    assert index_data["iterations"][0]["end_seq"] is not None
    assert index_data["snapshots"][0]["path"] == "snapshots/iter_1.json"
    assert index_data["errors"][0]["where"] == "snapshot"
    assert index_data["artifacts"][0]["artifact"]["path"] == "reports/final_report.md"

    run_end_seq = next(event["seq"] for event in events if event["type"] == "RUN_END")
    run_report_seq = next(
        event["seq"]
        for event in events
        if event["type"] == "ARTIFACT_WRITTEN" and event["payload"].get("type") == "run_report"
    )
    assert run_report_seq < run_end_seq
