from __future__ import annotations

import json
from pathlib import Path

from echoagent.agent.tracker import RuntimeTracker
from echoagent.artifacts import (
    record_llm_output,
    record_parse_failure,
    resolve_run_artifacts_root,
    save_file,
    save_json,
    save_text,
)
from echoagent.artifacts.models import ArtifactKind, ArtifactRef, ArtifactSettings
from echoagent.artifacts.store import FileSystemArtifactStore


def test_filesystem_store_put_text(tmp_path: Path) -> None:
    store = FileSystemArtifactStore(tmp_path)
    ref = store.put_text("note.txt", "hello", meta={"content_type": "text/plain"})

    assert ref.kind == ArtifactKind.TEXT
    path = store.resolve(ref)
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "hello"
    assert ref.meta.get("size") == len("hello".encode("utf-8"))
    assert "created_at" in ref.meta
    assert "sha256" in ref.meta


def test_store_open_returns_bytes(tmp_path: Path) -> None:
    store = FileSystemArtifactStore(tmp_path)
    ref = store.put_bytes("blob.bin", b"data")
    with store.open(ref) as handle:
        assert handle.read() == b"data"


def test_writers_save_payloads(tmp_path: Path) -> None:
    store = FileSystemArtifactStore(tmp_path)

    text_ref = save_text("hello.txt", "hello", store=store)
    assert text_ref.kind == ArtifactKind.TEXT
    assert store.resolve(text_ref).read_text(encoding="utf-8") == "hello"

    json_ref = save_json("payload.json", {"a": 1}, store=store)
    assert json_ref.kind == ArtifactKind.JSON
    assert "\"a\": 1" in store.resolve(json_ref).read_text(encoding="utf-8")

    file_ref = save_file("bytes.bin", b"bin", store=store)
    assert file_ref.kind == ArtifactKind.FILE
    assert store.resolve(file_ref).read_bytes() == b"bin"


def test_tracker_records_artifact() -> None:
    tracker = RuntimeTracker(
        console=None,
        artifact_settings=ArtifactSettings(enabled=False),
    )
    ref = ArtifactRef(id="1", kind=ArtifactKind.TEXT, uri="/tmp/file.txt", meta={})

    tracker.record_artifact(ref, event_type="report")

    records = tracker.artifact_records
    assert records
    assert records[0]["artifact"]["id"] == "1"
    assert records[0]["type"] == "report"


def test_resolve_run_artifacts_root(tmp_path: Path) -> None:
    settings = ArtifactSettings(root_dir=str(tmp_path))
    run_root = resolve_run_artifacts_root("run-1", settings=settings)
    assert run_root == tmp_path / "runs" / "run-1"


def test_record_parse_failure_snapshot(tmp_path: Path) -> None:
    run_id = "run-parse"
    settings = ArtifactSettings(root_dir=str(tmp_path))
    run_root = resolve_run_artifacts_root(run_id, settings=settings)
    store = FileSystemArtifactStore(run_root)

    ref = record_parse_failure(
        "bad output",
        store=store,
        run_id=run_id,
        agent_name="tester",
        profile_name="profile",
        schema_name="Schema",
        error_type="ValueError",
        error_message="boom",
        traceback_text="traceback",
        handler_name="OutputHandler",
        error_detail={"message": "boom"},
    )

    payload = json.loads(Path(ref.uri).read_text(encoding="utf-8"))
    assert payload["run_id"] == run_id
    assert payload["agent_name"] == "tester"
    assert payload["profile_name"] == "profile"
    assert payload["schema_name"] == "Schema"
    assert payload["error_type"] == "ValueError"
    assert payload["error_message"] == "boom"
    assert "raw_text_path" in payload
    assert Path(payload["raw_text_path"]).exists()


def test_record_llm_output(tmp_path: Path) -> None:
    run_id = "run-llm"
    settings = ArtifactSettings(root_dir=str(tmp_path))
    run_root = resolve_run_artifacts_root(run_id, settings=settings)
    store = FileSystemArtifactStore(run_root)

    ref = record_llm_output(
        "hello",
        store=store,
        run_id=run_id,
        agent_name="tester",
        profile_name="profile",
    )

    assert Path(ref.uri).read_text(encoding="utf-8") == "hello"
