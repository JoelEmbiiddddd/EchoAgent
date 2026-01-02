from __future__ import annotations

from echoagent.artifacts.models import ArtifactKind
from echoagent.artifacts.writers.base import ArtifactWriter
from echoagent.artifacts.writers.file import FileWriter
from echoagent.artifacts.writers.json import JsonWriter
from echoagent.artifacts.writers.text import TextWriter

_WRITERS: dict[ArtifactKind, ArtifactWriter] = {}


def register_writer(writer: ArtifactWriter) -> None:
    _WRITERS[writer.kind] = writer


def get_writer(kind: ArtifactKind) -> ArtifactWriter:
    if kind not in _WRITERS:
        raise KeyError(f"Writer not registered for {kind}")
    return _WRITERS[kind]


def _register_defaults() -> None:
    register_writer(TextWriter())
    register_writer(JsonWriter())
    register_writer(FileWriter())


_register_defaults()

__all__ = [
    "ArtifactWriter",
    "register_writer",
    "get_writer",
    "TextWriter",
    "JsonWriter",
    "FileWriter",
]
