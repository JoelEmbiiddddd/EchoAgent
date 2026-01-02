from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Optional, Protocol

from echoagent.agent.prompting.blocks import ContextBlock


class BudgetPolicy(Protocol):
    def trim(self, blocks: Iterable[ContextBlock], max_chars: Optional[int]) -> list[ContextBlock]:
        ...


class CharBudgetPolicy:
    """按字符预算裁剪上下文区块。"""

    def trim(self, blocks: Iterable[ContextBlock], max_chars: Optional[int]) -> list[ContextBlock]:
        block_list = list(blocks)
        if max_chars is None:
            return list(block_list)
        if max_chars <= 0:
            return []

        trimmed = [self._apply_block_limit(block) for block in block_list]
        total = sum(len(block.content) for block in trimmed)
        if total <= max_chars:
            return self._drop_empty(trimmed)

        for name in (
            "PREVIOUS_ITERATIONS",
            "MESSAGE_HISTORY",
            "TOOL_RESULTS",
            "CURRENT_INPUT",
        ):
            if total <= max_chars:
                break
            for idx, block in enumerate(trimmed):
                if block.name != name:
                    continue
                total, trimmed[idx] = self._trim_block_to_fit(block, total, max_chars)
                break

        return self._drop_empty(trimmed)

    def _apply_block_limit(self, block: ContextBlock) -> ContextBlock:
        if block.max_chars is None:
            return replace(block)
        if len(block.content) <= block.max_chars:
            return replace(block)
        keep_tail = block.name in (
            "PREVIOUS_ITERATIONS",
            "MESSAGE_HISTORY",
            "TOOL_RESULTS",
            "CURRENT_INPUT",
        )
        content = self._slice_content(block.content, block.max_chars, keep_tail=keep_tail)
        return replace(block, content=content)

    def _trim_block_to_fit(self, block: ContextBlock, total: int, max_chars: int) -> tuple[int, ContextBlock]:
        excess = total - max_chars
        if excess <= 0:
            return total, replace(block)

        current_len = len(block.content)
        allowed = current_len - excess
        if allowed <= 0:
            return total - current_len, replace(block, content="")

        keep_tail = block.name in (
            "PREVIOUS_ITERATIONS",
            "MESSAGE_HISTORY",
            "TOOL_RESULTS",
            "CURRENT_INPUT",
        )
        content = self._slice_content(block.content, allowed, keep_tail=keep_tail)
        new_total = total - current_len + len(content)
        return new_total, replace(block, content=content)

    def _slice_content(self, content: str, limit: int, *, keep_tail: bool) -> str:
        if limit <= 0:
            return ""
        if len(content) <= limit:
            return content

        if "\n" not in content:
            return content[-limit:] if keep_tail else content[:limit]

        header, body = content.split("\n", 1)
        header_len = len(header)
        if header_len >= limit:
            return header[:limit]

        remaining = limit - header_len - 1
        if remaining <= 0:
            return header[:limit]

        body_slice = body[-remaining:] if keep_tail else body[:remaining]
        return f"{header}\n{body_slice}"

    def _drop_empty(self, blocks: list[ContextBlock]) -> list[ContextBlock]:
        return [block for block in blocks if block.content and block.content.strip()]


class ContextBudgeter:
    """基于策略裁剪上下文区块。"""

    def __init__(self, policy: Optional[BudgetPolicy] = None) -> None:
        self.policy = policy or CharBudgetPolicy()

    def trim(self, blocks: Iterable[ContextBlock], max_chars: Optional[int]) -> list[ContextBlock]:
        return self.policy.trim(blocks, max_chars)
