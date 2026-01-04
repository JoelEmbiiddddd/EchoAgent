from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from echoagent.observability.runlog.index import RunIndexBuilder
from echoagent.observability.runlog.utils import atomic_write_json
from echoagent.observability.runlog.writer import RunEventWriter


class RunLog:
    """RunLog 门面，负责事件写入与索引落盘。"""

    def __init__(self, writer: RunEventWriter, index: RunIndexBuilder, index_path: Path) -> None:
        self._writer = writer
        self._index = index
        self._index_path = Path(index_path)
        self._run_id = writer.run_id

    def emit(self, type: str, payload: dict) -> int:
        try:
            if not type:
                return -1
            event = {
                "schema_version": 1,
                "run_id": self._run_id,
                "seq": None,
                "ts": _utc_timestamp(),
                "type": type,
                "payload": payload,
            }
            seq = self._writer.write(event)
            if seq == -1:
                return -1
            event["seq"] = seq
            self._index.on_event(event, seq)
            return seq
        except Exception:
            return -1

    def close(self) -> None:
        try:
            payload = self._index.finalize()
            atomic_write_json(self._index_path, payload)
        except Exception:
            pass
        try:
            self._writer.close()
        except Exception:
            pass


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
