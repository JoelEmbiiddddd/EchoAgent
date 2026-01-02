from __future__ import annotations

from typing import Any, Protocol

from echoagent.artifacts.models import ArtifactKind, ArtifactRef
from echoagent.artifacts.store import ArtifactStore


class ArtifactWriter(Protocol):
    kind: ArtifactKind

    def write(
        self,
        store: ArtifactStore,
        name: str,
        payload: Any,
        meta: dict[str, Any] | None = None,
    ) -> ArtifactRef:
        ...
