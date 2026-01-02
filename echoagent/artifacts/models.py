from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional


class ArtifactKind(str, Enum):
    TEXT = "TEXT"
    JSON = "JSON"
    FILE = "FILE"
    BUNDLE = "BUNDLE"


@dataclass
class ArtifactMeta:
    content_type: Optional[str] = None
    size: Optional[int] = None
    sha256: Optional[str] = None
    created_at: Optional[str] = None
    tags: Optional[dict[str, Any]] = None
    producer: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "content_type": self.content_type,
            "size": self.size,
            "sha256": self.sha256,
            "created_at": self.created_at,
            "tags": self.tags,
            "producer": self.producer,
        }
        return {key: value for key, value in data.items() if value is not None}


@dataclass
class ArtifactRef:
    id: str
    kind: ArtifactKind
    uri: str
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "uri": self.uri,
            "meta": dict(self.meta or {}),
        }


@dataclass
class ArtifactSettings:
    root_dir: Optional[str] = None
    enabled: bool = True
    save_parse_failures: bool = True
    save_llm_output: bool = False

    @classmethod
    def from_pipeline(cls, pipeline_settings: Optional[Mapping[str, Any]]) -> "ArtifactSettings":
        pipeline_settings = pipeline_settings or {}
        artifacts_settings = pipeline_settings.get("artifacts") or {}
        root_dir = artifacts_settings.get("root_dir")
        return cls(
            root_dir=root_dir or None,
            enabled=bool(artifacts_settings.get("enabled", True)),
            save_parse_failures=bool(artifacts_settings.get("save_parse_failures", True)),
            save_llm_output=bool(artifacts_settings.get("save_llm_output", False)),
        )
