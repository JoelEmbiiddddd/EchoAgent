from __future__ import annotations

import hashlib
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Mapping, Optional, Protocol

from echoagent.artifacts.models import ArtifactKind, ArtifactRef, ArtifactSettings


ENV_ARTIFACTS_DIR = "ECHOAGENT_ARTIFACTS_DIR"
DEFAULT_ARTIFACTS_DIR = Path.cwd() / ".echoagent" / "artifacts"


class ArtifactStore(Protocol):
    def put_bytes(
        self,
        name: str,
        data: bytes,
        meta: Optional[dict[str, Any]] = None,
    ) -> ArtifactRef:
        ...

    def put_text(
        self,
        name: str,
        text: str,
        meta: Optional[dict[str, Any]] = None,
        encoding: str = "utf-8",
    ) -> ArtifactRef:
        ...

    def open(self, ref: ArtifactRef) -> BinaryIO:
        ...

    def resolve(self, ref: ArtifactRef) -> Path:
        ...


def resolve_artifacts_root(
    pipeline_settings: Optional[Mapping[str, Any]] = None,
    *,
    settings: Optional[ArtifactSettings] = None,
) -> Path:
    root_dir = None
    if settings and settings.root_dir:
        root_dir = settings.root_dir
    if not root_dir and pipeline_settings:
        artifacts_settings = pipeline_settings.get("artifacts") or {}
        root_dir = artifacts_settings.get("root_dir")
    if not root_dir:
        root_dir = os.getenv(ENV_ARTIFACTS_DIR)
    if not root_dir:
        return DEFAULT_ARTIFACTS_DIR
    return Path(root_dir)


def resolve_run_artifacts_root(
    run_id: str,
    pipeline_settings: Optional[Mapping[str, Any]] = None,
    *,
    settings: Optional[ArtifactSettings] = None,
) -> Path:
    if not run_id:
        raise ValueError("run_id is required to resolve run artifacts root")
    base_dir = resolve_artifacts_root(pipeline_settings, settings=settings)
    return base_dir / "runs" / str(run_id)


class FileSystemArtifactStore:
    def __init__(self, root_dir: Path | str) -> None:
        self.root_dir = Path(root_dir)

    def put_bytes(
        self,
        name: str,
        data: bytes,
        meta: Optional[dict[str, Any]] = None,
    ) -> ArtifactRef:
        artifact_id = str(uuid.uuid4())
        safe_name = _safe_name(name)
        path = self._artifact_path(artifact_id, safe_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

        meta_payload = _merge_meta(meta, data)
        return ArtifactRef(
            id=artifact_id,
            kind=ArtifactKind.FILE,
            uri=str(path),
            meta=meta_payload,
        )

    def put_text(
        self,
        name: str,
        text: str,
        meta: Optional[dict[str, Any]] = None,
        encoding: str = "utf-8",
    ) -> ArtifactRef:
        data = text.encode(encoding)
        meta_payload = dict(meta or {})
        meta_payload.setdefault("encoding", encoding)
        ref = self.put_bytes(name, data, meta=meta_payload)
        ref.kind = ArtifactKind.TEXT
        return ref

    def open(self, ref: ArtifactRef) -> BinaryIO:
        return self.resolve(ref).open("rb")

    def resolve(self, ref: ArtifactRef) -> Path:
        return Path(ref.uri)

    def _artifact_path(self, artifact_id: str, safe_name: str) -> Path:
        return self.root_dir / artifact_id / safe_name


def _safe_name(name: str) -> str:
    cleaned = Path(name).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", cleaned)
    if not cleaned:
        cleaned = "artifact"
    return cleaned


def _merge_meta(meta: Optional[dict[str, Any]], data: bytes) -> dict[str, Any]:
    payload = dict(meta or {})
    payload.setdefault("size", len(data))
    payload.setdefault("sha256", hashlib.sha256(data).hexdigest())
    payload.setdefault("created_at", _utc_timestamp())
    return payload


def _utc_timestamp() -> str:
    return datetime.utcnow().replace(tzinfo=None).isoformat(timespec="seconds") + "Z"
