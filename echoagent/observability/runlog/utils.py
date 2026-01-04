from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel


_TRUNCATION_MARK = "\n...<truncated>...\n"


def safe_json(value: Any, *, max_depth: int = 6) -> Any:
    """尽量将对象转换为可 JSON 序列化的结构。"""
    return _safe_json(value, max_depth=max_depth, seen=set())


def _safe_json(value: Any, *, max_depth: int, seen: set[int]) -> Any:
    if max_depth < 0:
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    value_id = id(value)
    if value_id in seen:
        return "<circular>"
    seen.add(value_id)
    try:
        if isinstance(value, BaseModel):
            return _safe_json(value.model_dump(), max_depth=max_depth - 1, seen=seen)
        if is_dataclass(value):
            return _safe_json(asdict(value), max_depth=max_depth - 1, seen=seen)
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore")
        if isinstance(value, dict):
            return {
                str(key): _safe_json(item, max_depth=max_depth - 1, seen=seen)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [
                _safe_json(item, max_depth=max_depth - 1, seen=seen)
                for item in value
            ]
        if hasattr(value, "to_dict"):
            to_dict = getattr(value, "to_dict")
            if callable(to_dict):
                return _safe_json(to_dict(), max_depth=max_depth - 1, seen=seen)
        if hasattr(value, "__dict__"):
            payload = {
                key: item
                for key, item in vars(value).items()
                if not key.startswith("_")
            }
            if payload:
                return _safe_json(payload, max_depth=max_depth - 1, seen=seen)
        return str(value)
    finally:
        seen.discard(value_id)


def truncate_text(text: Any, max_chars: int) -> str:
    """按最大长度截断文本，保留首尾内容。"""
    if text is None:
        return ""
    text_value = str(text)
    if max_chars <= 0:
        return ""
    if len(text_value) <= max_chars:
        return text_value
    mark_len = len(_TRUNCATION_MARK)
    head = max_chars // 2
    tail = max_chars - head - mark_len
    if tail < 0:
        return text_value[:max_chars]
    return text_value[:head] + _TRUNCATION_MARK + text_value[-tail:]


def atomic_write_json(path: Path, data: Any) -> None:
    """原子写入 JSON 文件，避免部分写入。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(safe_json(data), ensure_ascii=False, indent=2)
    temp_path = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(path.parent))
        temp_path = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temp_path), str(path))
    finally:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
