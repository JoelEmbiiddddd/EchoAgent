from __future__ import annotations

import asyncio

from typing import Any
from pydantic import BaseModel

from echoagent.agent import EchoAgent
from echoagent.context import Context
from echoagent.profiles.manager.routing import AgentSelectionPlan
from echoagent.observability.runlog.utils import truncate_text
from echoagent.utils.parsers import OutputParserError, parse_json_output
from workflows.base import BaseWorkflow, autotracing


class DataScienceQuery(BaseModel):
    """Query model for data science tasks."""
    prompt: str
    data_path: str

    def format(self) -> str:
        """Format data science query."""
        return (
            f"Task: {self.prompt}\n"
            f"Dataset path: {self.data_path}\n"
            "Provide a comprehensive data science workflow"
        )

class DataScientistWorkflow(BaseWorkflow):
    """Data science workflow using manager-tool pattern.

    This workflow demonstrates the minimal implementation needed:
    - __init__: Setup agents and context
    - run(): Complete workflow implementation with query formatting, iteration, and finalization
    """

    def __init__(self, config):
        """Initialize workflow with explicit manager agents and tool agent dictionary."""
        super().__init__(config)

        # Initialize context and profiles
        self.context = Context(["profiles", "states"])
        llm = self.config.llm.main_model

        # Create manager agents with explicit dependencies
        self.observe_agent = EchoAgent(self.context, profile="observe", llm=llm)
        self.evaluate_agent = EchoAgent(self.context, profile="evaluate", llm=llm)
        self.routing_agent = EchoAgent(self.context, profile="routing", llm=llm)
        self.writer_agent = EchoAgent(self.context, profile="writer", llm=llm)

        # Create tool agents as dictionary
        tool_agent_names = [
            "data_loader_agent",
            "data_analysis_agent",
            "preprocessing_agent",
            "model_training_agent",
            "evaluation_agent",
            "visualization_agent",
        ]
        self.tool_agents = {
            name: EchoAgent(self.context, profile=name.removesuffix("_agent"), llm=llm, name=name)
            for name in tool_agent_names
        }

        # Register tool agents - automatically populates available_agents with descriptions from profiles
        self.context.state.register_tool_agents(self.tool_agents)

    def _coerce_routing_plan(self, output: Any) -> AgentSelectionPlan:
        if isinstance(output, AgentSelectionPlan):
            return output
        try:
            if isinstance(output, str):
                return AgentSelectionPlan.model_validate(parse_json_output(output))
            return AgentSelectionPlan.model_validate(output)
        except Exception as exc:
            message = "Routing agent output must be valid JSON with tasks."
            preview = truncate_text(str(output), 2000)
            self.runtime_tracker.log_panel("Plan Parse Error", f"{message}\n{preview}")
            if isinstance(exc, OutputParserError):
                return AgentSelectionPlan(tasks=[], reasoning="parse_failed")
            return AgentSelectionPlan(tasks=[], reasoning="parse_failed")


    @autotracing()
    async def run(self, query: DataScienceQuery) -> Any:
        # Phase 1: Initialize query in state
        self.context.state.set_query(query)

        self.update_printer("initialization", "Workflow initialized", is_done=True)
        self.update_printer("research", "Executing research workflow...")

        # Phase 2: Iterative loop - observe → evaluate → route → tools
        while self.iteration < self.max_iterations and not self.context.state.complete:
            # Smart iteration management - single command!
            self.iterate()

            # Observe → Evaluate → Route → Tools
            # No need for group_id - tracker auto-derives from context!
            observe_output = await self.observe_agent(query)
            evaluate_output = await self.evaluate_agent(observe_output)

            if not self.context.state.complete:
                routing_output = await self.routing_agent(evaluate_output)
                routing_plan = self._coerce_routing_plan(routing_output)
                plan_tasks = routing_plan.tasks

                if plan_tasks:
                    self.context.state.current_iteration.tools.clear()
                    coroutines = [self.tool_agents[task.agent](task.query) for task in plan_tasks]
                    for coroutine in asyncio.as_completed(coroutines):
                        await coroutine

        # Phase 3: Final report generation
        self.update_printer("research", "Research workflow complete", is_done=True)
        final_report = await self.writer_agent(self.context.state.findings_text())

        # Phase 4: Finalization
        final_result = final_report

        if self.reporter is not None:
            self.reporter.set_final_result(final_result)

        return final_result
