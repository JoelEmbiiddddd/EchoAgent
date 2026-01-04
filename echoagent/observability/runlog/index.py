from __future__ import annotations

from typing import Any, Dict, Optional

from echoagent.observability.runlog.utils import safe_json


class RunIndexBuilder:
    """根据事件流构建索引结构。"""

    def __init__(self, run_id: str) -> None:
        self.run_id = str(run_id)
        self._started_at: Optional[Any] = None
        self._ended_at: Optional[Any] = None
        self._status: Optional[str] = None
        self._last_seq: Optional[int] = None
        self._counts: Dict[str, int] = {
            "events": 0,
            "errors": 0,
            "iterations": 0,
            "artifacts": 0,
            "snapshots": 0,
            "steps": 0,
        }
        self._iterations: Dict[int, Dict[str, Any]] = {}
        self._errors: list[dict[str, Any]] = []
        self._artifacts: list[dict[str, Any]] = []
        self._snapshots: list[dict[str, Any]] = []
        self._steps: Dict[str, Dict[str, Any]] = {}

    def _get_iteration(self, iteration: Optional[int]) -> Optional[Dict[str, Any]]:
        if iteration is None:
            return None
        if iteration not in self._iterations:
            self._iterations[iteration] = {
                "iteration": iteration,
                "start_seq": None,
                "end_seq": None,
                "errors": [],
                "snapshots": [],
            }
            self._counts["iterations"] = len(self._iterations)
        return self._iterations[iteration]

    def on_event(self, event: dict, seq: int) -> None:
        try:
            self._counts["events"] += 1
            if self._last_seq is None or seq > self._last_seq:
                self._last_seq = seq
            event_type = event.get("type")
            ts = event.get("ts")
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}

            if event_type == "RUN_START":
                self._started_at = ts
            elif event_type == "RUN_END":
                self._ended_at = ts
                status = payload.get("status")
                if isinstance(status, str):
                    self._status = status

            if event_type == "ITERATION_START":
                iteration = payload.get("iteration")
                iter_meta = self._get_iteration(_to_int(iteration))
                if iter_meta is not None and iter_meta.get("start_seq") is None:
                    iter_meta["start_seq"] = seq

            if event_type == "ITERATION_END":
                iteration = payload.get("iteration")
                iter_meta = self._get_iteration(_to_int(iteration))
                if iter_meta is not None:
                    iter_meta["end_seq"] = seq
                snapshot = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else None
                if snapshot:
                    snapshot_entry = {
                        "seq": seq,
                        "iteration": _to_int(iteration),
                        "path": snapshot.get("path"),
                        "hash": snapshot.get("hash"),
                    }
                    self._snapshots.append(snapshot_entry)
                    self._counts["snapshots"] += 1
                    if iter_meta is not None:
                        iter_meta["snapshots"].append(snapshot_entry)

            if event_type == "ERROR":
                error_entry = {
                    "seq": seq,
                    "ts": ts,
                    "where": payload.get("where"),
                    "exception_type": payload.get("exception_type"),
                    "message": payload.get("message"),
                    "iteration": _to_int(payload.get("iteration")),
                }
                self._errors.append(error_entry)
                self._counts["errors"] += 1
                iter_meta = self._get_iteration(_to_int(payload.get("iteration")))
                if iter_meta is not None:
                    iter_meta["errors"].append(error_entry)

            if event_type == "ARTIFACT_WRITTEN":
                artifact = payload.get("artifact")
                path_value = payload.get("path")
                if isinstance(artifact, dict) and path_value and "path" not in artifact:
                    artifact = dict(artifact)
                    artifact["path"] = path_value
                artifact_entry = {
                    "seq": seq,
                    "ts": ts,
                    "type": payload.get("type"),
                    "artifact": artifact,
                }
                if path_value:
                    artifact_entry["path"] = path_value
                self._artifacts.append(artifact_entry)
                self._counts["artifacts"] += 1

            if event_type == "AGENT_STEP_START":
                step_id = payload.get("step_id")
                if step_id:
                    step_key = str(step_id)
                    step_meta = self._steps.setdefault(
                        step_key,
                        {
                            "step_id": step_key,
                            "start_seq": None,
                            "end_seq": None,
                            "iteration": _to_int(payload.get("iteration")),
                            "agent_name": payload.get("agent_name"),
                            "span_name": payload.get("span_name"),
                            "status": "running",
                        },
                    )
                    if step_meta.get("start_seq") is None:
                        step_meta["start_seq"] = seq
                    self._counts["steps"] = len(self._steps)

            if event_type == "AGENT_STEP_END":
                step_id = payload.get("step_id")
                if step_id:
                    step_key = str(step_id)
                    step_meta = self._steps.setdefault(
                        step_key,
                        {
                            "step_id": step_key,
                            "start_seq": None,
                            "end_seq": None,
                            "iteration": _to_int(payload.get("iteration")),
                            "agent_name": payload.get("agent_name"),
                            "span_name": payload.get("span_name"),
                            "status": None,
                        },
                    )
                    step_meta["end_seq"] = seq
                    status = payload.get("status")
                    if status:
                        step_meta["status"] = status
                    self._counts["steps"] = len(self._steps)
        except Exception:
            return

    def finalize(self) -> dict:
        iterations = [self._iterations[key] for key in sorted(self._iterations.keys())]
        last_seq = self._last_seq
        if last_seq is not None:
            for iteration in iterations:
                if iteration.get("start_seq") is not None and iteration.get("end_seq") is None:
                    iteration["end_seq"] = last_seq
                    iteration["incomplete"] = True
            for step in self._steps.values():
                if step.get("start_seq") is not None and step.get("end_seq") is None:
                    step["end_seq"] = last_seq
                    step["incomplete"] = True
        agent_steps = [
            self._steps[key] for key in sorted(self._steps.keys())
        ]
        payload = {
            "schema_version": 1,
            "run_id": self.run_id,
            "started_at": self._started_at,
            "ended_at": self._ended_at,
            "status": self._status,
            "counts": dict(self._counts),
            "iterations": iterations,
            "errors": list(self._errors),
            "artifacts": list(self._artifacts),
            "snapshots": list(self._snapshots),
            "agent_steps": agent_steps,
        }
        return safe_json(payload)


def _to_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None
