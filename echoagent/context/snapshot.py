from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from echoagent.context.errors import SnapshotError
from echoagent.context.state import BaseIterationRecord, ConversationState


def _serialize_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    return value


def _serialize_iteration(iteration: BaseIterationRecord) -> dict[str, Any]:
    data = iteration.model_dump()
    data["payloads"] = [_serialize_value(payload) for payload in iteration.payloads]
    data["tools"] = [_serialize_value(tool) for tool in iteration.tools]
    return data


def _serialize_state(state: ConversationState) -> dict[str, Any]:
    data = state.model_dump(exclude={"iterations"})
    data["query"] = _serialize_value(state.query)
    return data


def dump_jsonl(state: ConversationState, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "state", "data": _serialize_state(state)}) + "\n")
        for iteration in state.iterations:
            handle.write(json.dumps({"type": "iteration", "data": _serialize_iteration(iteration)}) + "\n")
    return target


def load_jsonl(path: str | Path) -> ConversationState:
    source = Path(path)
    state_data: dict[str, Any] | None = None
    iterations: list[BaseIterationRecord] = []
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = line.strip()
            if not record:
                continue
            try:
                payload = json.loads(record)
            except json.JSONDecodeError as exc:
                raise SnapshotError(f"Invalid JSONL line in {source}") from exc
            record_type = payload.get("type")
            data = payload.get("data")
            if record_type == "state":
                state_data = data or {}
            elif record_type == "iteration":
                if data is None:
                    raise SnapshotError("Snapshot iteration record missing data")
                iterations.append(BaseIterationRecord.model_validate(data))
            else:
                raise SnapshotError(f"Unknown snapshot record type: {record_type!r}")

    state = ConversationState.model_validate(state_data or {})
    state.iterations.extend(iterations)
    return state


def dump_json(state: ConversationState, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state": _serialize_state(state),
        "iterations": [_serialize_iteration(iteration) for iteration in state.iterations],
    }
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def load_json(path: str | Path) -> ConversationState:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SnapshotError(f"Invalid JSON snapshot: {source}") from exc
    if not isinstance(payload, dict):
        raise SnapshotError("Snapshot JSON must be an object")
    state_data = payload.get("state") or {}
    iterations_data = payload.get("iterations") or []
    iterations = [BaseIterationRecord.model_validate(item) for item in iterations_data]
    state = ConversationState.model_validate(state_data)
    state.iterations.extend(iterations)
    return state
