from __future__ import annotations

from typing import Iterable

from echoagent.agent.prompting.blocks import ContextBlock


class PromptRenderer:
    """按优先级稳定渲染上下文区块。"""

    def render(self, blocks: Iterable[ContextBlock]) -> str:
        block_list = list(blocks)
        if not block_list:
            return ""
        if len(block_list) == 1 and block_list[0].name == "RUNTIME_TEMPLATE":
            return block_list[0].content

        ordered = sorted(
            enumerate(block_list),
            key=lambda item: (-item[1].priority, item[0]),
        )
        contents = [block.content for _, block in ordered if block.content and block.content.strip()]
        return "\n\n".join(contents).strip()
