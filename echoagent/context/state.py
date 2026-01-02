from __future__ import annotations

import time
import warnings
from typing import Any, Callable, Dict, List, Optional, Type
from typing import Literal

from pydantic import BaseModel, Field, PrivateAttr

from echoagent.profiles.base import ToolAgentOutput


def identity_wrapper(value: Any) -> Any:
    return value


class BaseIterationRecord(BaseModel):
    """State captured for a single iteration of the research loop."""

    index: int
    observation: Optional[str] = None
    tools: List[ToolAgentOutput] = Field(default_factory=list)
    payloads: List[Any] = Field(default_factory=list)
    status: str = Field(default="pending", description="Iteration status: pending or complete")
    summarized: bool = Field(default=False, description="Whether this iteration has been summarised")

    def mark_complete(self) -> None:
        self.status = "complete"

    def is_complete(self) -> bool:
        return self.status == "complete"

    def mark_summarized(self) -> None:
        self.summarized = True

    def add_payload(self, value: Any) -> Any:
        self.payloads.append(value)
        return value


class ContextEvent(BaseModel):
    type: Literal["USER_MESSAGE", "ASSISTANT_MESSAGE", "TOOL_RESULT"]
    content: str
    meta: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class ConversationState(BaseModel):
    iterations: List[BaseIterationRecord] = Field(default_factory=list)
    events: List[ContextEvent] = Field(default_factory=list)
    final_report: Optional[str] = None
    started_at: Optional[float] = None
    complete: bool = False
    summary: Optional[str] = None
    query: Optional[Any] = None
    formatted_query: Optional[str] = None
    max_time_minutes: Optional[float] = None
    available_agents: Dict[str, str] = Field(default_factory=dict)

    _iteration_model: Type[BaseIterationRecord] = PrivateAttr(default=BaseIterationRecord)

    def start_timer(self) -> None:
        self.started_at = time.time()

    def get_with_wrapper(self, key: str, wrapper: Callable[[Any], Any] = identity_wrapper) -> Any:
        return wrapper(getattr(self, key))

    @property
    def iteration(self) -> str:
        try:
            return str(self.current_iteration.index)
        except (ValueError, AttributeError):
            return "1"

    @property
    def history(self) -> str:
        return self.iteration_history(include_current=False) or "No previous iterations."

    @property
    def observation(self) -> str:
        try:
            obs = self.current_iteration.observation
            return obs if obs else ""
        except (ValueError, AttributeError):
            return ""

    @property
    def last_summary(self) -> str:
        return self.summary if self.summary else ""

    @property
    def conversation_history(self) -> str:
        return self.iteration_history(include_current=True)

    @property
    def elapsed_minutes(self) -> str:
        if self.started_at is None:
            return "0"
        return str((time.time() - self.started_at) / 60)

    @property
    def available_agents_text(self) -> str:
        if not self.available_agents:
            return ""
        lines = [f"- {agent_name}: {description}" for agent_name, description in self.available_agents.items()]
        return "\n".join(lines)

    @property
    def findings(self) -> str:
        return self.findings_text()

    def begin_iteration(self) -> BaseIterationRecord:
        iteration = self._iteration_model(index=len(self.iterations) + 1)
        self.iterations.append(iteration)
        return iteration

    @property
    def current_iteration(self) -> BaseIterationRecord:
        if not self.iterations:
            raise ValueError("No iteration has been started yet.")
        return self.iterations[-1]

    def mark_iteration_complete(self) -> None:
        self.current_iteration.mark_complete()

    def mark_research_complete(self) -> None:
        self.complete = True
        self.current_iteration.mark_complete()

    def iteration_history(self, include_current: bool = False) -> str:
        warnings.warn(
            "iteration_history is deprecated; use prompting history renderer instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from echoagent.agent.prompting.history_renderer import render_iteration_history

        current_iteration = self.iterations[-1] if self.iterations else None
        return render_iteration_history(
            self.iterations,
            include_current=include_current,
            only_unsummarized=False,
            current_iteration=current_iteration,
        )

    def unsummarized_history(self, include_current: bool = True) -> str:
        warnings.warn(
            "unsummarized_history is deprecated; use prompting history renderer instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from echoagent.agent.prompting.history_renderer import render_iteration_history

        current_iteration = self.iterations[-1] if self.iterations else None
        return render_iteration_history(
            self.iterations,
            include_current=include_current,
            only_unsummarized=True,
            current_iteration=current_iteration,
        )

    def set_query(self, query: Any) -> None:
        self.query = query

    def register_tool_agents(self, tool_agents: Dict[str, Any]) -> None:
        for agent_name, agent in tool_agents.items():
            if hasattr(agent, "_profile") and agent._profile:
                description = agent._profile.get_description()
                self.available_agents[agent_name] = description

    def record_payload(self, payload: Any) -> Any:
        iteration = self.current_iteration if self.iterations else self.begin_iteration()
        return iteration.add_payload(payload)

    def record_event(self, event_type: str, content: str, meta: Optional[Dict[str, Any]] = None) -> None:
        try:
            event = ContextEvent(type=event_type, content=str(content), meta=meta or {})
        except Exception:
            return
        self.events.append(event)

    def all_findings(self) -> List[str]:
        findings: List[str] = []
        for iteration in self.iterations:
            findings.extend(tool.output for tool in iteration.tools)
        return findings

    def findings_text(self) -> str:
        findings = self.all_findings()
        return "\n\n".join(findings).strip() if findings else ""

    def update_summary(self, summary: str) -> None:
        self.summary = summary
        for iteration in self.iterations:
            iteration.mark_summarized()

    def format_context_prompt(self, current_input: Optional[str] = None) -> str:
        warnings.warn(
            "format_context_prompt is deprecated; use prompting renderer instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from echoagent.agent.prompting.history_renderer import render_context_prompt

        return render_context_prompt(self, current_input=current_input)


def create_conversation_state() -> ConversationState:
    return ConversationState()
