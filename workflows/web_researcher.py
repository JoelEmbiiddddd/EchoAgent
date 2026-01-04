from __future__ import annotations

import asyncio

from typing import Any

from pydantic import BaseModel

from echoagent.agent import EchoAgent
from echoagent.context import Context
from echoagent.profiles.web.web_planning import AgentSelectionPlan
from echoagent.observability.runlog.utils import truncate_text
from echoagent.utils.parsers import OutputParserError, parse_json_output
from workflows.base import BaseWorkflow, autotracing


class WebSearchQuery(BaseModel):
    """Query model for data science tasks."""
    prompt: str

    def format(self) -> str:
        """Format web search query."""
        return (
            f"Web search query: {self.prompt}\n"
            "Provide a comprehensive web search workflow"
        )


class WebSearcherWorkflow(BaseWorkflow):
    """Web search workflow using manager-tool pattern with multi-task planning.

    This workflow demonstrates web search with parallel query execution:
    - __init__: Setup agents (observe, evaluate, planning, writer) and tool agents (web_searcher)
    - run: Implement the workflow logic (observe → evaluate → plan → execute multiple searches → write)
    - WebSearchQuery.format(): Format query (handled automatically by BaseWorkflow)

    The planning agent generates multiple web search tasks that are executed in parallel.
    All other logic (iteration, tool execution, memory save) is handled by BaseWorkflow.
    """

    def __init__(self, config):
        """Initialize workflow with explicit manager agents and tool agent dictionary."""
        super().__init__(config)

        # Initialize context and profiles
        self.context = Context(["profiles", "states"])
        llm = self.config.llm.main_model

        # Create manager agents with explicit dependencies
        self.observe_agent = EchoAgent(context=self.context, profile="observe", llm=llm)
        self.evaluate_agent = EchoAgent(context=self.context, profile="evaluate", llm=llm)
        self.planning_agent = EchoAgent(context=self.context, profile="web_planning", llm=llm)
        self.writer_agent = EchoAgent(context=self.context, profile="writer", llm=llm)

        # Create tool agents as dictionary
        tool_agent_names = [
            "web_searcher",
            "web_crawler",
        ]
        self.tool_agents = {
            f"{name}_agent": EchoAgent(context=self.context, profile=name, llm=llm, name=f"{name}_agent")
            for name in tool_agent_names
        }

        # Register tool agents - automatically populates available_agents with descriptions from profiles
        self.context.state.register_tool_agents(self.tool_agents)

    def _coerce_plan(self, output: Any) -> AgentSelectionPlan:
        if isinstance(output, AgentSelectionPlan):
            return output
        try:
            if isinstance(output, str):
                return AgentSelectionPlan.model_validate(parse_json_output(output))
            return AgentSelectionPlan.model_validate(output)
        except Exception as exc:
            message = "Planning agent output must be valid JSON with tasks."
            preview = truncate_text(str(output), 2000)
            self.runtime_tracker.log_panel("Plan Parse Error", f"{message}\n{preview}")
            if isinstance(exc, OutputParserError):
                return AgentSelectionPlan(tasks=[], reasoning="parse_failed")
            return AgentSelectionPlan(tasks=[], reasoning="parse_failed")

    @autotracing()
    async def run(self, query: Any = None) -> Any:
        """Execute web search workflow - full implementation in one function.

        Args:
            query: Optional WebSearchQuery input

        Returns:
            Final report from state
        """
        # Phase 1: Initialize query in state
        self.context.state.set_query(query)

        self.update_printer("initialization", "Workflow initialized", is_done=True)
        self.update_printer("research", "Executing web search workflow...")

        # Phase 2: Iterative loop - observe → evaluate → plan → tools
        while self.iteration < self.max_iterations and not self.context.state.complete:
            # Smart iteration management - single command!
            self.iterate()

            # Observe → Evaluate → Plan → Tools
            # No need for group_id - tracker auto-derives from context!
            observe_output = await self.observe_agent(query)
            evaluate_output = await self.evaluate_agent(observe_output)

            if not self.context.state.complete:
                planning_output = await self.planning_agent(evaluate_output)
                plan_tasks = self._coerce_plan(planning_output).tasks

                if plan_tasks:
                    self.context.state.current_iteration.tools.clear()
                    coroutines = [self.tool_agents[task.agent](task.model_dump_json()) for task in plan_tasks]
                    for coroutine in asyncio.as_completed(coroutines):
                        await coroutine

        # Phase 3: Final report generation
        self.update_printer("research", "Web search workflow complete", is_done=True)
        final_report = await self.writer_agent(self.context.state.findings_text())

        # Phase 4: Finalization
        final_result = final_report

        if self.reporter is not None:
            self.reporter.set_final_result(final_result)

        return final_result
