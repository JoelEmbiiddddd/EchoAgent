from __future__ import annotations

from echoagent.agent.prompting.blocks import ContextBlock
from echoagent.agent.prompting.budget import ContextBudgeter


def test_context_budgeter_trims_in_order() -> None:
    blocks = [
        ContextBlock("ORIGINAL_QUERY", "[ORIGINAL QUERY]\n" + ("Q" * 20), priority=100),
        ContextBlock("PREVIOUS_ITERATIONS", "[PREVIOUS ITERATIONS]\n" + ("H" * 40), priority=90),
        ContextBlock("CURRENT_INPUT", "[CURRENT INPUT]\n" + ("I" * 20), priority=80),
    ]
    budgeter = ContextBudgeter()

    total = sum(len(block.content) for block in blocks)
    budget = total - 10
    trimmed = budgeter.trim(blocks, budget)

    trimmed_map = {block.name: block for block in trimmed}

    assert sum(len(block.content) for block in trimmed) <= budget
    assert len(trimmed_map["ORIGINAL_QUERY"].content) == len(blocks[0].content)
    assert len(trimmed_map["CURRENT_INPUT"].content) == len(blocks[2].content)
    assert len(trimmed_map["PREVIOUS_ITERATIONS"].content) == len(blocks[1].content) - 10


def test_context_budgeter_prefers_history_over_tools() -> None:
    blocks = [
        ContextBlock("RUNTIME_TEMPLATE", "R" * 10, priority=110),
        ContextBlock("ORIGINAL_QUERY", "Q" * 10, priority=100),
        ContextBlock("MESSAGE_HISTORY", "H" * 30, priority=95),
        ContextBlock("TOOL_RESULTS", "T" * 20, priority=85),
    ]
    budgeter = ContextBudgeter()

    total = sum(len(block.content) for block in blocks)
    budget = total - 10
    trimmed = budgeter.trim(blocks, budget)

    trimmed_map = {block.name: block for block in trimmed}

    assert len(trimmed_map["RUNTIME_TEMPLATE"].content) == len(blocks[0].content)
    assert len(trimmed_map["ORIGINAL_QUERY"].content) == len(blocks[1].content)
    assert len(trimmed_map["TOOL_RESULTS"].content) == len(blocks[3].content)
    assert len(trimmed_map["MESSAGE_HISTORY"].content) == len(blocks[2].content) - 10
