from __future__ import annotations

from echoagent.agent.prompting.assembler import ContextAssembler
from echoagent.agent.prompting.renderer import PromptRenderer
from tests.utils import add_iteration, make_profile, make_state


def test_context_assembler_runtime_template_block() -> None:
    profile = make_profile(runtime_template="Summary: {summary}")
    state = make_state(summary="hello", profile=profile)
    assembler = ContextAssembler()

    blocks = assembler.assemble(state, profile, payload=None, payload_str=None)

    assert len(blocks) == 1
    assert blocks[0].name == "RUNTIME_TEMPLATE"
    assert "Summary: hello" in blocks[0].content


def test_context_assembler_fallback_blocks_render_match() -> None:
    profile = make_profile(runtime_template="")
    state = make_state(query="q1", profile=profile)
    add_iteration(state, observation="first", complete=True)
    assembler = ContextAssembler()
    renderer = PromptRenderer()

    blocks = assembler.assemble(state, profile, payload=None, payload_str="task")
    rendered = renderer.render(blocks)

    assert [block.name for block in blocks] == [
        "ORIGINAL_QUERY",
        "PREVIOUS_ITERATIONS",
        "CURRENT_INPUT",
    ]
    assert rendered == state.format_context_prompt(current_input="task")


def test_context_assembler_events_and_tool_dedup() -> None:
    profile = make_profile(runtime_template="")
    profile.context_policy = {
        "blocks": {
            "message_history": {"enabled": True},
            "tool_results": {"enabled": True},
            "previous_iterations": {"enabled": False},
        }
    }
    state = make_state(query="q1", profile=profile)
    state.record_event("USER_MESSAGE", "hello")
    state.record_event("ASSISTANT_MESSAGE", "world")
    state.record_event("TOOL_RESULT", "first", meta={"tool_name": "search"})
    state.record_event("TOOL_RESULT", "second", meta={"tool_name": "search"})
    assembler = ContextAssembler()

    blocks = assembler.assemble(state, profile, payload=None, payload_str=None)
    block_map = {block.name: block for block in blocks}

    assert "MESSAGE_HISTORY" in block_map
    assert "hello" in block_map["MESSAGE_HISTORY"].content
    assert "world" in block_map["MESSAGE_HISTORY"].content
    assert "TOOL_RESULTS" in block_map
    assert "second" in block_map["TOOL_RESULTS"].content
    assert "first" not in block_map["TOOL_RESULTS"].content
    assert "PREVIOUS_ITERATIONS" not in block_map
