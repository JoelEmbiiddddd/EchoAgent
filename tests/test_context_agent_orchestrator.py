from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from echoagent.agent.agent import EchoAgent
from echoagent.agent.prompting.instruction_builder import InstructionBuilder
from echoagent.agent.output_handler import OutputHandler
from echoagent.agent.tracker import RuntimeTracker
from echoagent.artifacts.models import ArtifactSettings
from tests.fakes.fake_runner import FakeRunner
from tests.utils import make_context, make_profile, make_run_result, make_state


class SampleSchema(BaseModel):
    a: int


class ErrorState:
    def __init__(self, summary: str) -> None:
        self.summary = summary
        self.errors: list[str] = []

    def record_error(self, error: Exception) -> None:
        self.errors.append(str(error))


def test_context_agent_orchestrator_normal_path(tmp_path) -> None:
    profile = make_profile(runtime_template="Summary: {summary}\nInput: {runtime_input}")
    state = make_state(summary="sum", profile=profile)
    context = make_context(profile=profile, state=state)
    fake_runner = FakeRunner(run_result=make_run_result("ok"))
    tracker = RuntimeTracker(
        console=None,
        artifact_settings=ArtifactSettings(root_dir=str(tmp_path)),
    )
    agent = EchoAgent(
        context=context,
        profile="test",
        llm="dummy",
        runner=fake_runner,
        instruction_builder=InstructionBuilder(),
        output_handler=OutputHandler(),
    )

    result = asyncio.run(agent("payload", tracker=tracker, record_payload=True))

    assert result == "ok"
    assert "Summary: sum" in fake_runner.captured["instructions"]
    assert "payload" in fake_runner.captured["instructions"]
    assert len(state.iterations) == 1


def test_context_agent_orchestrator_lenient_parse(tmp_path) -> None:
    profile = make_profile(runtime_template="Summary: {summary}")
    state = make_state(summary="sum", profile=profile)
    context = make_context(profile=profile, state=state)
    fake_runner = FakeRunner(run_result=make_run_result("bad"))
    tracker = RuntimeTracker(
        console=None,
        artifact_settings=ArtifactSettings(root_dir=str(tmp_path)),
    )
    agent = EchoAgent(
        context=context,
        profile="test",
        llm="dummy",
        runner=fake_runner,
        instruction_builder=InstructionBuilder(),
        output_handler=OutputHandler(),
    )

    result = asyncio.run(agent("payload", tracker=tracker, output_model=SampleSchema))

    assert result == "bad"


def test_context_agent_orchestrator_runner_error(tmp_path) -> None:
    def raise_error() -> None:
        raise RuntimeError("boom")

    profile = make_profile(runtime_template="Summary: {summary}")
    state = ErrorState(summary="sum")
    context = make_context(profile=profile, state=state)
    fake_runner = FakeRunner(side_effect=raise_error)
    tracker = RuntimeTracker(
        console=None,
        artifact_settings=ArtifactSettings(root_dir=str(tmp_path)),
    )
    agent = EchoAgent(
        context=context,
        profile="test",
        llm="dummy",
        runner=fake_runner,
        instruction_builder=InstructionBuilder(),
        output_handler=OutputHandler(),
    )

    with pytest.raises(RuntimeError):
        asyncio.run(agent("payload", tracker=tracker))

    assert state.errors == ["boom"]
