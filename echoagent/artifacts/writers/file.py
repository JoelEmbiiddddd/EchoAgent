from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from echoagent.artifacts.models import ArtifactKind, ArtifactRef
from echoagent.artifacts.store import ArtifactStore


class FileWriter:
    kind = ArtifactKind.FILE

    def write(
        self,
        store: ArtifactStore,
        name: str,
        payload: Any,
        meta: dict[str, Any] | None = None,
    ) -> ArtifactRef:
        data = _resolve_bytes(payload)
        meta_payload = dict(meta or {})
        if "content_type" not in meta_payload:
            guessed_type, _ = mimetypes.guess_type(name)
            if guessed_type:
                meta_payload["content_type"] = guessed_type
        ref = store.put_bytes(name, data, meta=meta_payload)
        ref.kind = ArtifactKind.FILE
        return ref


def _resolve_bytes(payload: Any) -> bytes:
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, bytearray):
        return bytes(payload)
    if isinstance(payload, Path):
        return payload.read_bytes()
    raise TypeError("FileWriter payload must be bytes or Path")
