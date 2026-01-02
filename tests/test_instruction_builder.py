from __future__ import annotations

from echoagent.agent.prompting.instruction_builder import InstructionBuilder
from tests.utils import add_iteration, make_profile, make_state, make_tool_output


def test_instruction_builder_includes_summary() -> None:
    profile = make_profile(runtime_template="Summary: {summary}")
    state = make_state(summary="hello", profile=profile)
    builder = InstructionBuilder()

    result = builder.build(state, profile, runtime={"payload": "task"})

    assert "Summary: hello" in result


def test_instruction_builder_history_order() -> None:
    profile = make_profile(runtime_template="")
    state = make_state(query="q1", profile=profile)
    add_iteration(state, observation="first", complete=True)
    add_iteration(state, observation="second", complete=True)
    builder = InstructionBuilder()

    result = builder.build(state, profile, runtime={"payload": None})

    assert result.index("first") < result.index("second")


def test_instruction_builder_includes_tool_results() -> None:
    profile = make_profile(runtime_template="")
    state = make_state(profile=profile)
    add_iteration(state, observation="obs", tool_outputs=[make_tool_output("tool-out")], complete=True)
    builder = InstructionBuilder()

    result = builder.build(state, profile, runtime={"payload": None})

    assert "tool-out" in result
