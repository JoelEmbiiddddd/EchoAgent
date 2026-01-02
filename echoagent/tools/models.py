from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from echoagent.artifacts.models import ArtifactRef


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_schema: dict[str, Any]
    result_schema: Optional[dict[str, Any]] = None
    tags: list[str] = field(default_factory=list)


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    call_id: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolError:
    code: str
    message: str
    details: Optional[dict[str, Any]] = None


@dataclass
class ToolResult:
    ok: bool
    data: Any = None
    error: Optional[ToolError] = None
    artifacts: list[ArtifactRef] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolContext:
    tracker: Optional[Any] = None
    data_store: Optional[Any] = None
    artifact_store: Optional[Any] = None
    logger: Optional[Any] = None
    env: dict[str, Any] = field(default_factory=dict)


ToolHandler = Callable[[dict[str, Any], ToolContext], Any]
