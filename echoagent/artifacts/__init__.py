"""Artifact utilities and workflow reporting helpers."""

import re
import uuid
from typing import Any, Mapping, Optional

from echoagent.utils.helpers import serialize_content

from echoagent.artifacts.models import (
    ArtifactKind,
    ArtifactMeta,
    ArtifactRef,
    ArtifactSettings,
)
from echoagent.artifacts.reporter import RunReporter
from echoagent.artifacts.store import (
    ArtifactStore,
    FileSystemArtifactStore,
    resolve_artifacts_root,
    resolve_run_artifacts_root,
)
from echoagent.artifacts.writers import get_writer


def resolve_artifact_settings(
    pipeline_settings: Optional[Mapping[str, Any]] = None,
) -> ArtifactSettings:
    return ArtifactSettings.from_pipeline(pipeline_settings)


def get_default_store(
    *,
    pipeline_settings: Optional[Mapping[str, Any]] = None,
    settings: Optional[ArtifactSettings] = None,
) -> ArtifactStore:
    root_dir = resolve_artifacts_root(pipeline_settings, settings=settings)
    return FileSystemArtifactStore(root_dir)


def save(
    kind: ArtifactKind,
    payload: Any,
    name: str,
    *,
    store: Optional[ArtifactStore] = None,
    meta: Optional[dict[str, Any]] = None,
    settings: Optional[ArtifactSettings] = None,
    pipeline_settings: Optional[Mapping[str, Any]] = None,
) -> ArtifactRef:
    target_store = store or get_default_store(
        pipeline_settings=pipeline_settings,
        settings=settings,
    )
    writer = get_writer(kind)
    return writer.write(target_store, name, payload, meta=meta)


def save_text(
    name: str,
    payload: str,
    *,
    store: Optional[ArtifactStore] = None,
    meta: Optional[dict[str, Any]] = None,
    settings: Optional[ArtifactSettings] = None,
    pipeline_settings: Optional[Mapping[str, Any]] = None,
) -> ArtifactRef:
    return save(
        ArtifactKind.TEXT,
        payload,
        name,
        store=store,
        meta=meta,
        settings=settings,
        pipeline_settings=pipeline_settings,
    )


def save_json(
    name: str,
    payload: Any,
    *,
    store: Optional[ArtifactStore] = None,
    meta: Optional[dict[str, Any]] = None,
    settings: Optional[ArtifactSettings] = None,
    pipeline_settings: Optional[Mapping[str, Any]] = None,
) -> ArtifactRef:
    return save(
        ArtifactKind.JSON,
        payload,
        name,
        store=store,
        meta=meta,
        settings=settings,
        pipeline_settings=pipeline_settings,
    )


def save_file(
    name: str,
    payload: Any,
    *,
    store: Optional[ArtifactStore] = None,
    meta: Optional[dict[str, Any]] = None,
    settings: Optional[ArtifactSettings] = None,
    pipeline_settings: Optional[Mapping[str, Any]] = None,
    ) -> ArtifactRef:
    return save(
        ArtifactKind.FILE,
        payload,
        name,
        store=store,
        meta=meta,
        settings=settings,
        pipeline_settings=pipeline_settings,
    )


def record_llm_output(
    output: Any,
    *,
    store: ArtifactStore,
    run_id: str,
    agent_name: str,
    profile_name: Optional[str],
    meta: Optional[dict[str, Any]] = None,
) -> ArtifactRef:
    effective_run_id = run_id or uuid.uuid4().hex
    safe_agent = _safe_token(agent_name or "agent")
    name_suffix = effective_run_id
    payload = serialize_content(output)
    payload_meta = {
        "content_type": "text/plain; charset=utf-8",
        "run_id": effective_run_id,
        "agent_name": agent_name,
        "profile_name": profile_name,
    }
    if meta:
        payload_meta.update(meta)
    return save_text(
        f"llm_output_{safe_agent}_{name_suffix}.txt",
        payload,
        store=store,
        meta=payload_meta,
    )


def record_parse_failure(
    raw_output: Any,
    *,
    store: ArtifactStore,
    run_id: str,
    agent_name: str,
    profile_name: Optional[str],
    schema_name: Optional[str],
    error_type: Optional[str],
    error_message: Optional[str],
    traceback_text: Optional[str],
    handler_name: str,
    error_detail: Optional[dict[str, Any]] = None,
    meta: Optional[dict[str, Any]] = None,
    path_prefix: Optional[str] = None,
) -> ArtifactRef:
    effective_run_id = run_id or uuid.uuid4().hex
    schema_label = _safe_token(schema_name or "unknown")
    name_suffix = effective_run_id
    prefix = f"{path_prefix.strip().strip('/')}/" if path_prefix else ""
    raw_text = serialize_content(raw_output)
    raw_ref = save_text(
        f"{prefix}parse_failure_raw_{schema_label}_{name_suffix}.txt",
        raw_text,
        store=store,
        meta={
            "content_type": "text/plain; charset=utf-8",
            "run_id": effective_run_id,
            "agent_name": agent_name,
            "profile_name": profile_name,
            "schema_name": schema_name,
        },
    )
    payload = {
        "run_id": effective_run_id,
        "agent_name": agent_name,
        "profile_name": profile_name,
        "schema_name": schema_name,
        "error_type": error_type,
        "error_message": error_message,
        "traceback": traceback_text,
        "raw_text_path": raw_ref.path or raw_ref.uri,
        "meta": {
            "handler": handler_name,
            "raw_model_output": raw_text,
            "raw_text_artifact": raw_ref.to_dict(),
            "error_detail": error_detail,
        },
    }
    if meta:
        payload["meta"].update(meta)
    return save_json(
        f"{prefix}parse_failure_{schema_label}_{name_suffix}.json",
        payload,
        store=store,
        meta={
            "content_type": "application/json",
            "run_id": effective_run_id,
            "agent_name": agent_name,
            "profile_name": profile_name,
            "schema_name": schema_name,
        },
    )


def _safe_token(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", value or "")
    return cleaned or "artifact"


__all__ = [
    "ArtifactKind",
    "ArtifactMeta",
    "ArtifactRef",
    "ArtifactSettings",
    "ArtifactStore",
    "FileSystemArtifactStore",
    "RunReporter",
    "resolve_artifact_settings",
    "resolve_artifacts_root",
    "resolve_run_artifacts_root",
    "get_default_store",
    "save",
    "save_text",
    "save_json",
    "save_file",
    "record_llm_output",
    "record_parse_failure",
]
