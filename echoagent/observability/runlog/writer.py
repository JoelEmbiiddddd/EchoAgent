from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Optional

from echoagent.observability.runlog.utils import safe_json


class RunEventWriter:
    """事件流写入器，失败时不抛异常。"""

    def __init__(self, path: Path, run_id: str) -> None:
        self.path = Path(path)
        self.run_id = str(run_id)
        self._seq = 0
        self._lock = threading.Lock()
        self._handle: Optional[Any] = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = self.path.open("a", encoding="utf-8")
        except Exception:
            self._handle = None

    def write(self, event: dict) -> int:
        if self._handle is None:
            return -1
        with self._lock:
            try:
                payload = dict(event)
                seq = payload.get("seq")
                if not isinstance(seq, int):
                    self._seq += 1
                    seq = self._seq
                    payload["seq"] = seq
                else:
                    self._seq = max(self._seq, seq)
                payload.setdefault("run_id", self.run_id)
                line = json.dumps(safe_json(payload), ensure_ascii=False, separators=(",", ":"))
                self._handle.write(line + "\n")
                self._handle.flush()
                return int(seq)
            except Exception:
                return -1

    def close(self) -> None:
        try:
            if self._handle is not None:
                self._handle.close()
        except Exception:
            pass
        self._handle = None
