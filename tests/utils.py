from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Iterable, Optional

from agents import Agent, RunResult
from agents.run_context import RunContextWrapper
from pydantic import BaseModel

from echoagent.context.state import create_conversation_state
from echoagent.profiles.base import Profile, ToolAgentOutput


def make_profile(
    *,
    instructions: str = "You are a test agent.",
    runtime_template: str = "",
    output_schema: Optional[type[BaseModel]] = None,
    tools: Optional[list[Any]] = None,
) -> Profile:
    return Profile(
        instructions=instructions,
        runtime_template=runtime_template,
        output_schema=output_schema,
        tools=tools,
    )


def make_state(
    *,
    summary: Optional[str] = None,
    query: Optional[str] = None,
    profile: Optional[Profile] = None,
) -> Any:
    state = create_conversation_state()
    if summary is not None:
        state.summary = summary
    if query is not None:
        state.query = query
    return state


def add_iteration(
    state: Any,
    *,
    observation: Optional[str] = None,
    tool_outputs: Optional[Iterable[ToolAgentOutput]] = None,
    payloads: Optional[Iterable[BaseModel]] = None,
    complete: bool = True,
) -> Any:
    iteration = state.begin_iteration()
    if observation is not None:
        iteration.observation = observation
    if payloads:
        for payload in payloads:
            state.record_payload(payload)
    if tool_outputs:
        iteration.tools.extend(tool_outputs)
    if complete:
        iteration.mark_complete()
    return iteration


def make_context(*, profile: Profile, state: Any) -> Any:
    return SimpleNamespace(profiles={"test": profile}, state=state)


def make_run_result(final_output: Any) -> RunResult:
    agent = Agent(name="fake", instructions="")
    wrapper = RunContextWrapper(context=None)
    return RunResult(
        input="",
        new_items=[],
        raw_responses=[],
        final_output=final_output,
        input_guardrail_results=[],
        output_guardrail_results=[],
        tool_input_guardrail_results=[],
        tool_output_guardrail_results=[],
        context_wrapper=wrapper,
        _last_agent=agent,
    )


def make_tool_output(text: str) -> ToolAgentOutput:
    return ToolAgentOutput(output=text)
