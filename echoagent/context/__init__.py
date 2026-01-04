"""Context engine for managing conversation state and agent I/O."""

from .context import Context
from .errors import ContextError, SnapshotError
from .snapshot import dump_json, dump_jsonl, load_json, load_jsonl
from .state import BaseIterationRecord, ConversationState, IterationDigest, create_conversation_state

__all__ = [
    "Context",
    "ContextError",
    "SnapshotError",
    "dump_json",
    "dump_jsonl",
    "load_json",
    "load_jsonl",
    "BaseIterationRecord",
    "ConversationState",
    "IterationDigest",
    "create_conversation_state",
]
