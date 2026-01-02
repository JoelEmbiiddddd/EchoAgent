from __future__ import annotations

from typing import Any

from echoagent.artifacts.models import ArtifactKind, ArtifactRef
from echoagent.artifacts.store import ArtifactStore


class TextWriter:
    kind = ArtifactKind.TEXT

    def write(
        self,
        store: ArtifactStore,
        name: str,
        payload: Any,
        meta: dict[str, Any] | None = None,
    ) -> ArtifactRef:
        if not isinstance(payload, str):
            raise TypeError("TextWriter payload must be str")
        meta_payload = dict(meta or {})
        meta_payload.setdefault("content_type", "text/plain; charset=utf-8")
        ref = store.put_text(name, payload, meta=meta_payload)
        ref.kind = ArtifactKind.TEXT
        return ref
