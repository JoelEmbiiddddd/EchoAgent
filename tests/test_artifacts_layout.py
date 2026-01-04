from __future__ import annotations

from echoagent.artifacts.artifact_writer import ArtifactWriter
from echoagent.artifacts.models import ArtifactSettings


def test_artifacts_layout_default(tmp_path) -> None:
    base_dir = tmp_path / "outputs"
    writer = ArtifactWriter(
        base_dir=base_dir,
        pipeline_slug="demo",
        workflow_name="demo",
        experiment_id="exp-1",
        run_id="run-1",
        artifact_settings=ArtifactSettings(),
    )
    writer.start(config=None)
    writer.set_final_result("ok")
    refs = writer.finalize()

    run_dir = base_dir / "runs" / "run-1"
    assert (run_dir / "reports" / "final_report.md").exists()
    assert (run_dir / "reports" / "final_report.html").exists()
    assert "ok" in (run_dir / "reports" / "final_report.md").read_text(encoding="utf-8")
    assert not (run_dir / "debug" / "terminal_log.md").exists()
    assert not (run_dir / "debug" / "terminal_log.html").exists()
    assert len(refs) == 2
