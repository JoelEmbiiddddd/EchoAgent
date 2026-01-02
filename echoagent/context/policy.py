from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class BlockPolicy:
    enabled: bool = True
    max_chars: Optional[int] = None


@dataclass(frozen=True)
class ContextPolicy:
    total_budget: Optional[int] = None
    blocks: dict[str, BlockPolicy] = field(default_factory=dict)

    def is_enabled(self, block_name: str) -> bool:
        policy = self.blocks.get(block_name)
        return policy.enabled if policy is not None else True

    def max_chars_for(self, block_name: str) -> Optional[int]:
        policy = self.blocks.get(block_name)
        return policy.max_chars if policy is not None else None


_ALIASES: dict[str, str] = {
    "runtime_template": "RUNTIME_TEMPLATE",
    "system_runtime": "RUNTIME_TEMPLATE",
    "system": "RUNTIME_TEMPLATE",
    "instructions": "RUNTIME_TEMPLATE",
    "runtime": "RUNTIME_TEMPLATE",
    "original_query": "ORIGINAL_QUERY",
    "query": "ORIGINAL_QUERY",
    "prompt": "ORIGINAL_QUERY",
    "previous_iterations": "PREVIOUS_ITERATIONS",
    "iteration_history": "PREVIOUS_ITERATIONS",
    "history": "PREVIOUS_ITERATIONS",
    "current_input": "CURRENT_INPUT",
    "input": "CURRENT_INPUT",
    "payload": "CURRENT_INPUT",
    "runtime_input": "CURRENT_INPUT",
    "message_history": "MESSAGE_HISTORY",
    "conversation_history": "MESSAGE_HISTORY",
    "messages": "MESSAGE_HISTORY",
    "tool_results": "TOOL_RESULTS",
    "tool_output": "TOOL_RESULTS",
    "tools": "TOOL_RESULTS",
    "findings": "TOOL_RESULTS",
}


def normalize_context_policy(raw: Any) -> ContextPolicy:
    if raw is None:
        return ContextPolicy()
    if isinstance(raw, ContextPolicy):
        return raw
    if not isinstance(raw, Mapping):
        return ContextPolicy()

    raw_dict = dict(raw)
    total_budget = raw_dict.get("total_budget")
    if total_budget is None:
        total_budget = raw_dict.get("total_budget_tokens")
    if total_budget is not None:
        try:
            total_budget = int(total_budget)
        except (TypeError, ValueError):
            total_budget = None

    blocks_data: Mapping[str, Any]
    if isinstance(raw_dict.get("blocks"), Mapping):
        blocks_data = raw_dict.get("blocks") or {}
    else:
        blocks_data = {
            key: value
            for key, value in raw_dict.items()
            if key not in {"total_budget", "total_budget_tokens", "blocks"}
        }

    blocks: dict[str, BlockPolicy] = {}
    for name, value in blocks_data.items():
        canonical = _normalize_block_name(str(name))
        if canonical is None:
            continue
        blocks[canonical] = _normalize_block_policy(value)

    return ContextPolicy(total_budget=total_budget, blocks=blocks)


def _normalize_block_name(name: str) -> Optional[str]:
    key = name.strip().lower()
    if not key:
        return None
    return _ALIASES.get(key, key.upper())


def _normalize_block_policy(value: Any) -> BlockPolicy:
    if isinstance(value, BlockPolicy):
        return value
    if isinstance(value, bool):
        return BlockPolicy(enabled=value)
    if isinstance(value, int):
        return BlockPolicy(enabled=True, max_chars=value)
    if not isinstance(value, Mapping):
        return BlockPolicy()
    enabled = value.get("enabled", True)
    max_chars = value.get("max_chars")
    if max_chars is None:
        max_chars = value.get("max_tokens")
    try:
        max_chars = int(max_chars) if max_chars is not None else None
    except (TypeError, ValueError):
        max_chars = None
    return BlockPolicy(enabled=bool(enabled), max_chars=max_chars)


def apply_block_policy(block_name: str, policy: ContextPolicy) -> Optional[BlockPolicy]:
    if not policy.is_enabled(block_name):
        return None
    block_policy = policy.blocks.get(block_name)
    if block_policy is None:
        return BlockPolicy()
    return replace(block_policy)
