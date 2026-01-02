from __future__ import annotations

import json
from typing import Any

from echoagent.artifacts.models import ArtifactKind, ArtifactRef
from echoagent.artifacts.store import ArtifactStore


class JsonWriter:
    kind = ArtifactKind.JSON

    def write(
        self,
        store: ArtifactStore,
        name: str,
        payload: Any,
        meta: dict[str, Any] | None = None,
    ) -> ArtifactRef:
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump()
        meta_payload = dict(meta or {})
        meta_payload.setdefault("content_type", "application/json")
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        ref = store.put_text(name, text, meta=meta_payload)
        ref.kind = ArtifactKind.JSON
        return ref
