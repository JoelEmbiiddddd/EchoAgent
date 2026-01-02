from __future__ import annotations

import inspect
import time
import traceback
import uuid
from typing import Any, Optional, Callable

from pydantic import BaseModel

from agents import Agent, RunResult, OpenAIChatCompletionsModel
from agents.run_context import TContext
from echoagent.agent.tracking.events import (
    RunEvent,
    RUN_START,
    USER_MESSAGE,
    MODEL_OUTPUT,
    PARSE_RESULT,
    ERROR,
    RUN_END,
)
from echoagent.agent.prompting.instruction_builder import InstructionBuilder
from echoagent.agent.output_handler import OutputHandler
from echoagent.agent.runner import AgentRunner, ExecutorRunner
from echoagent.agent.runtime_config import RuntimeConfig
from echoagent.agent.tracking.state_recorder import StateRecorder
from echoagent.utils.llm_setup import model_supports_json_and_tool_calls
from echoagent.utils.parsers import create_type_parser
from echoagent.context.state import identity_wrapper
from echoagent.utils.helpers import extract_final_output
from echoagent.profiles.loader import resolve_profile
from echoagent.profiles.runtime import (
    normalize_model,
    normalize_policies,
    normalize_tools,
    runtime_tools,
)
from echoagent.artifacts import record_llm_output, record_parse_failure


class EchoAgent(Agent[TContext]):
    """Augmented Agent class with context-aware capabilities.

    EchoAgent extends the base Agent class with:
    - Automatic context injection into instructions
    - Profile-based configuration (tools, instructions, output schema)
    - Automatic iteration tracking and state management
    - Runtime template rendering with state placeholders

    Usage:
        agent = EchoAgent(
            context=context,
            profile="observe",
            llm="gpt-4"
        )

    All Agent parameters can be passed via **agent_kwargs to override profile defaults:
        agent = EchoAgent(
            context=context,
            profile="observe",
            llm="gpt-4",
            tools=[custom_tool],  # Overrides profile tools
            model="gpt-4-turbo"   # Overrides llm parameter
        )
    """

    def __init__(
        self,
        context: Any,
        *,
        profile: str,
        llm: str,
        runner: Optional[AgentRunner] = None,
        instruction_builder: Optional[InstructionBuilder] = None,
        output_handler: Optional[OutputHandler] = None,
        tracker: Optional[Any] = None,
        **agent_kwargs: Any,
    ) -> None:
        """Initialize EchoAgent with context and profile identifier.

        Args:
            context: Context object containing profiles and state
            profile: Profile identifier for lookup in context.profiles
            llm: LLM model name (e.g., "gpt-4", "claude-3-5-sonnet")
            runner: Optional runner override for agent execution
            instruction_builder: Optional instruction builder override
            output_handler: Optional output handler override
            tracker: Optional default runtime tracker override
            **agent_kwargs: Additional Agent parameters that override profile defaults
                          (name, tools, instructions, output_type, model, etc.)
        """
        # Lookup profile from context
        profile_source = None
        if context and getattr(context, "profiles", None):
            profile_source = context.profiles.get(profile)
        resolved_identifier = profile

        agent_kwargs_copy = dict(agent_kwargs)
        resolution_overrides: dict[str, Any] = {}
        runtime_overrides: dict[str, Any] = {}

        if "instructions" in agent_kwargs_copy:
            resolution_overrides["instructions"] = agent_kwargs_copy.pop("instructions")
        if "tools" in agent_kwargs_copy:
            resolution_overrides["tools"] = agent_kwargs_copy.pop("tools")
        if "output_schema" in agent_kwargs_copy:
            resolution_overrides["output_schema"] = agent_kwargs_copy.pop("output_schema")
        if "policies" in agent_kwargs_copy:
            resolution_overrides["policies"] = agent_kwargs_copy.pop("policies")
        if "provider" in agent_kwargs_copy:
            resolution_overrides["provider"] = agent_kwargs_copy.pop("provider")
        if "base_url" in agent_kwargs_copy:
            resolution_overrides["base_url"] = agent_kwargs_copy.pop("base_url")
        if "api_key_env" in agent_kwargs_copy:
            resolution_overrides["api_key_env"] = agent_kwargs_copy.pop("api_key_env")
        if "params" in agent_kwargs_copy:
            resolution_overrides["params"] = agent_kwargs_copy.pop("params")
        if "mcp_servers" in agent_kwargs_copy:
            runtime_overrides["mcp_servers"] = agent_kwargs_copy.pop("mcp_servers")
        if "mcp_server_names" in agent_kwargs_copy:
            runtime_overrides["mcp_server_names"] = agent_kwargs_copy.pop("mcp_server_names")

        model_override = agent_kwargs_copy.pop("model", llm)
        if "provider" not in resolution_overrides:
            provider_hint = _infer_provider_from_model(model_override)
            if provider_hint:
                resolution_overrides["provider"] = provider_hint
        resolution_overrides["model"] = model_override

        resolved_profile = resolve_profile(
            resolved_identifier,
            resolution_overrides,
            profile_data=profile_source,
        )
        if resolved_profile.id is None:
            resolved_profile.id = resolved_identifier

        runtime_config = RuntimeConfig.from_profile_input(
            resolved_profile,
            overrides=runtime_overrides,
        )

        policies = normalize_policies(resolved_profile.policies)
        tool_specs = normalize_tools(list(resolved_profile.tools or []), policies.on_tool_name_conflict)
        model_spec = normalize_model(resolved_profile.model)
        if model_spec.model is None or (isinstance(model_spec.model, str) and not model_spec.model.strip()):
            raise ValueError("Profile model is required")
        tools = runtime_tools(tool_specs)
        base_agent_kwargs = {
            "instructions": resolved_profile.instructions,
            "tools": tools,
            "model": model_spec.model,
        }

        if runtime_config.mcp_servers:
            base_agent_kwargs["mcp_servers"] = runtime_config.mcp_servers

        # Handle output schema and parser
        output_parser = None
        output_schema = resolved_profile.output_schema

        if output_schema:
            if not model_supports_json_and_tool_calls(model_spec):
                output_parser = create_type_parser(output_schema)
            else:
                base_agent_kwargs["output_type"] = output_schema

        # Determine final agent name
        agent_name = resolved_identifier if resolved_identifier.endswith("_agent") else f"{resolved_identifier}_agent"

        # Extract name override if provided, otherwise use derived name
        final_name = agent_kwargs_copy.pop("name", agent_name)

        # Merge agent_kwargs on top of profile config (agent_kwargs wins)
        base_agent_kwargs.update(agent_kwargs_copy)

        # Initialize parent Agent class
        super().__init__(name=final_name, **base_agent_kwargs)

        # Store EchoAgent-specific attributes
        self.output_parser = output_parser
        self._context = context  # Context reference for state access
        self._identifier = resolved_identifier  # Identifier used for profile lookup/iteration tracking
        self._profile = resolved_profile  # Resolved profile for runtime templates
        self._runtime_config = runtime_config
        self._policies = policies

        self._context_wrappers = {}
        self.instruction_builder = instruction_builder or InstructionBuilder()
        self.output_handler = output_handler or OutputHandler()
        self._runner = runner or ExecutorRunner()
        self._tracker = tracker
    
    def register_context_wrapper(self, field_name: str, wrapper: Callable[[Any], Any] = identity_wrapper) -> None:
        """Register a context wrapper for a context field."""
        self._context_wrappers[field_name] = wrapper

    def get_context_with_wrapper(self, field_name: str) -> Any:
        """Get a context wrapper for a field name."""
        return self._context.get_with_wrapper(field_name, self._context_wrappers.get(field_name, identity_wrapper))

    @property
    def role(self) -> str:
        return self._identifier.removesuffix("_agent")

    def build_contextual_instructions(self, payload: Any = None) -> str:
        """Build instructions with automatic context injection from pipeline state.

        This method compiles instructions that include:
        - Runtime template rendering with placeholders filled from state (if profile has runtime_template)
        - Original query from pipeline.context.state.query
        - Previous iteration history from pipeline.context.state.iteration_history()
        - Current input payload

        Args:
            payload: Current input data for the agent

        Returns:
            Formatted instructions string with full context

        Note:
            This method requires self._context to be set.
        """
        state = self._context.state
        profile = getattr(self, "_profile", None)
        return self.instruction_builder.build(
            state,
            profile,
            runtime={"payload": payload},
        )

    def _get_artifact_store(self, tracker: Optional[Any]) -> Optional[Any]:
        if tracker is None:
            return None
        settings = getattr(tracker, "artifact_settings", None)
        if not settings or not getattr(settings, "enabled", False):
            return None
        get_store = getattr(tracker, "get_run_artifact_store", None)
        if not callable(get_store):
            return None
        return get_store()

    def _save_parse_failure_snapshot(
        self,
        tracker: Optional[Any],
        raw_output: Any,
        *,
        schema_name: Optional[str],
        error_detail: Optional[Any],
        exception: Optional[BaseException],
        run_id: Optional[str],
        handler_name: str,
    ) -> None:
        if tracker is None:
            return
        settings = getattr(tracker, "artifact_settings", None)
        if not settings or not getattr(settings, "save_parse_failures", False):
            return
        store = self._get_artifact_store(tracker)
        if store is None:
            return
        error_payload: Optional[dict[str, Any]] = None
        if error_detail is not None:
            to_dict = getattr(error_detail, "to_dict", None)
            if callable(to_dict):
                error_payload = to_dict()
            else:
                error_payload = {"message": str(error_detail)}
        error_type = None
        error_message = None
        if error_payload:
            error_type = error_payload.get("exception_type") or error_payload.get("type")
            error_message = error_payload.get("message")
        if error_message is None and exception is not None:
            error_message = str(exception)
        if error_type is None and exception is not None:
            error_type = exception.__class__.__name__
        traceback_text = None
        if exception is not None:
            traceback_text = "".join(
                traceback.format_exception(type(exception), exception, exception.__traceback__)
            )
        ref = record_parse_failure(
            raw_output,
            store=store,
            run_id=run_id or "",
            agent_name=getattr(self, "name", ""),
            profile_name=getattr(self, "_identifier", None),
            schema_name=schema_name,
            error_type=error_type,
            error_message=error_message,
            traceback_text=traceback_text,
            handler_name=handler_name,
            error_detail=error_payload,
        )
        record = getattr(tracker, "record_artifact", None)
        if callable(record):
            record(ref, event_type="parse_failure")

    def _save_llm_output_artifact(
        self,
        tracker: Optional[Any],
        output: Any,
        *,
        run_id: Optional[str],
    ) -> None:
        if tracker is None:
            return
        settings = getattr(tracker, "artifact_settings", None)
        if not settings or not getattr(settings, "save_llm_output", False):
            return
        store = self._get_artifact_store(tracker)
        if store is None:
            return
        ref = record_llm_output(
            output,
            store=store,
            run_id=run_id or "",
            agent_name=getattr(self, "name", ""),
            profile_name=getattr(self, "_identifier", None),
        )
        record = getattr(tracker, "record_artifact", None)
        if callable(record):
            record(ref, event_type="llm_output")


    async def __call__(
        self,
        payload: Any = None,
        *,
        tracker: Optional[Any] = None,
        span_name: Optional[str] = None,
        span_type: Optional[str] = None,
        output_model: Optional[type[BaseModel]] = None,
        printer_key: Optional[str] = None,
        printer_title: Optional[str] = None,
        printer_border_style: Optional[str] = None,
        record_payload: Optional[bool] = None,
        sync: bool = False,
        **span_kwargs: Any,
    ) -> Any:
        """Make EchoAgent callable directly.

        This allows usage like: result = await agent(input_data)

        When called with tracker provided (or available from context), uses the agent_step
        function for full tracking/tracing. Otherwise, uses ContextRunner.

        Note: When calling directly without tracker, input validation
        is relaxed to allow string inputs even if agent has a defined input_model.

        Args:
            payload: Input data for the agent
            tracker: Optional RuntimeTracker for execution with tracking.
                    If not provided, will attempt to get from context via get_current_tracker().

        Returns:
            Parsed output if in pipeline context, otherwise RunResult
        """
        state = getattr(self._context, "state", None)
        instructions = self.instruction_builder.build(
            state,
            self._profile,
            runtime={"payload": payload},
        )

        # Auto-detect tracker from context if not explicitly provided
        if tracker is None:
            tracker = self._tracker
        if tracker is None:
            from echoagent.agent.tracker import get_current_tracker
            tracker = get_current_tracker()

        # If tracker is available (explicitly or from context), use agent_step for full tracking
        if tracker:
            async def _call_runner_hook(hook, **kwargs: Any) -> None:
                if not callable(hook):
                    return
                result = hook(**kwargs)
                if inspect.isawaitable(result):
                    await result

            is_tool_agent = bool(self.tools)
            resolved_span_name = span_name or self.name
            resolved_span_type = span_type or ("tool" if is_tool_agent else "agent")

            resolved_printer_key = printer_key or (f"tool:{resolved_span_name}" if is_tool_agent else None)
            resolved_printer_title = printer_title or (f"Tool: {resolved_span_name}" if is_tool_agent else None)

            resolved_output_model = output_model
            if resolved_output_model is None and is_tool_agent:
                from echoagent.profiles.base import ToolAgentOutput

                resolved_output_model = ToolAgentOutput

            resolved_record_payload = record_payload if record_payload is not None else is_tool_agent

            run_meta = {
                "agent_name": self.name,
                "profile_name": self._identifier,
            }
            if self._profile:
                run_meta["resolved_profile"] = self._profile.to_debug_dict()
            tracker.on_run_start(state, run_meta)

            run_id = str(uuid.uuid4())
            workflow_run_id = getattr(tracker, "run_id", None) or getattr(tracker, "experiment_id", None)
            events: list[RunEvent] = []
            state_recorder = StateRecorder()
            events.append(
                RunEvent(
                    type=RUN_START,
                    payload={"agent_name": self.name, "profile_name": self._identifier},
                    ts=time.time(),
                    run_id=run_id,
                )
            )
            payload_text = self.instruction_builder._serialize_payload(payload)
            if payload_text:
                events.append(
                    RunEvent(
                        type=USER_MESSAGE,
                        payload={
                            "content": payload_text,
                            "meta": {
                                "agent_name": self.name,
                                "profile_name": self._identifier,
                            },
                        },
                        ts=time.time(),
                        run_id=run_id,
                    )
                )

            status = "success"
            try:
                await _call_runner_hook(getattr(self._runner, "open", None), runtime_config=self._runtime_config)
                result = await self._runner.run(
                    tracker=tracker,
                    agent=self,
                    instructions=instructions,
                    span_name=resolved_span_name,
                    span_type=resolved_span_type,
                    output_model=resolved_output_model,
                    sync=sync,
                    printer_key=resolved_printer_key,
                    printer_title=resolved_printer_title,
                    printer_border_style=printer_border_style,
                    span_kwargs=span_kwargs,
                    runtime_config=self._runtime_config,
                )
                # if self.name == "web_searcher_agent":
                #     import ipdb; ipdb.set_trace()

                if resolved_output_model and isinstance(result, resolved_output_model):
                    final_output = result
                else:
                    final_output = extract_final_output(result)
                    if (
                        resolved_output_model
                        and not isinstance(final_output, resolved_output_model)
                    ):
                        parse_mode = "lenient"
                        if getattr(self, "_policies", None):
                            parse_mode = self._policies.output_parse_mode
                        try:
                            parsed = self.output_handler.parse(
                                final_output,
                                schema=resolved_output_model,
                                mode=parse_mode,
                            )
                        except Exception as exc:  # noqa: BLE001 - re-raise after observability
                            schema_name = self.output_handler._schema_name(resolved_output_model)
                            error_detail = self.output_handler._build_error_detail(
                                final_output,
                                schema_name,
                                exc,
                            )
                            tracker.log_panel(
                                "Parse Error",
                                f"schema: {error_detail.schema_name}\nerror: {error_detail.message}",
                            )
                            self._save_parse_failure_snapshot(
                                tracker,
                                final_output,
                                schema_name=schema_name,
                                error_detail=error_detail,
                                exception=exc,
                                run_id=workflow_run_id,
                                handler_name="OutputHandler",
                            )
                            events.append(
                                RunEvent(
                                    type=PARSE_RESULT,
                                    payload={
                                        "ok": False,
                                        "error": str(exc),
                                        "model_name": schema_name,
                                        "error_detail": error_detail.to_dict(),
                                    },
                                    ts=time.time(),
                                    run_id=run_id,
                                )
                            )
                            raise
                        events.append(
                            RunEvent(
                                type=PARSE_RESULT,
                                payload={
                                    "ok": parsed.ok,
                                    "error": parsed.error,
                                    "model_name": parsed.model_name,
                                    "error_detail": parsed.error_detail.to_dict() if parsed.error_detail else None,
                                },
                                ts=time.time(),
                                run_id=run_id,
                            )
                        )
                        if not parsed.ok and parsed.error and tracker:
                            error_detail = parsed.error_detail
                            schema_name = error_detail.schema_name if error_detail else (parsed.model_name or "unknown")
                            message = error_detail.message if error_detail else parsed.error
                            tracker.log_panel("Parse Error", f"schema: {schema_name}\nerror: {message}")
                            self._save_parse_failure_snapshot(
                                tracker,
                                final_output,
                                schema_name=schema_name,
                                error_detail=error_detail,
                                exception=None,
                                run_id=workflow_run_id,
                                handler_name="OutputHandler",
                            )
                        final_output = parsed.value

                events.append(
                    RunEvent(
                        type=MODEL_OUTPUT,
                        payload={
                            "output": final_output,
                            "record_payload": resolved_record_payload,
                            "record_tool_output": is_tool_agent,
                            "agent_name": self.name,
                            "profile_name": self._identifier,
                            "tool_name": self.name if is_tool_agent else None,
                        },
                        ts=time.time(),
                        run_id=run_id,
                    )
                )
                tracker.on_model_output(
                    state,
                    final_output,
                    record_payload=resolved_record_payload,
                    record_tool_output=is_tool_agent,
                )
                self._save_llm_output_artifact(tracker, final_output, run_id=workflow_run_id)

                return final_output
            except Exception as exc:
                status = "error"
                events.append(
                    RunEvent(
                        type=ERROR,
                        payload={"error": exc},
                        ts=time.time(),
                        run_id=run_id,
                    )
                )
                tracker.on_error(state, exc)
                raise
            finally:
                events.append(
                    RunEvent(
                        type=RUN_END,
                        payload={"status": status},
                        ts=time.time(),
                        run_id=run_id,
                    )
                )
                state_recorder.consume(self._context, events)
                try:
                    await _call_runner_hook(getattr(self._runner, "close", None))
                except Exception:
                    pass
                tracker.on_run_end(state, run_meta)


    async def parse_output(self, run_result: RunResult) -> RunResult:
        """Apply legacy string parser only when no structured output is configured."""
        if self.output_parser and self.output_type is None:
            parse_mode = "lenient"
            if getattr(self, "_policies", None):
                parse_mode = self._policies.output_parse_mode
            try:
                parsed = self.output_handler.parse(
                    run_result.final_output,
                    schema=self.output_parser,
                    mode=parse_mode,
                )
            except Exception as exc:  # noqa: BLE001 - re-raise after observability
                from echoagent.agent.tracker import get_current_tracker

                tracker = get_current_tracker()
                if tracker:
                    workflow_run_id = getattr(tracker, "run_id", None) or getattr(tracker, "experiment_id", None)
                    schema_name = self.output_handler._schema_name(self.output_parser)
                    error_detail = self.output_handler._build_error_detail(
                        run_result.final_output,
                        schema_name,
                        exc,
                    )
                    tracker.log_panel(
                        "Parse Error",
                        f"schema: {error_detail.schema_name}\nerror: {error_detail.message}",
                    )
                    self._save_parse_failure_snapshot(
                        tracker,
                        run_result.final_output,
                        schema_name=schema_name,
                        error_detail=error_detail,
                        exception=exc,
                        run_id=workflow_run_id,
                        handler_name="OutputHandler",
                    )
                raise
            if not parsed.ok and parsed.error:
                from echoagent.agent.tracker import get_current_tracker

                tracker = get_current_tracker()
                if tracker:
                    workflow_run_id = getattr(tracker, "run_id", None) or getattr(tracker, "experiment_id", None)
                    error_detail = parsed.error_detail
                    schema_name = error_detail.schema_name if error_detail else (parsed.model_name or "unknown")
                    message = error_detail.message if error_detail else parsed.error
                    tracker.log_panel("Parse Error", f"schema: {schema_name}\nerror: {message}")
                    self._save_parse_failure_snapshot(
                        tracker,
                        run_result.final_output,
                        schema_name=schema_name,
                        error_detail=error_detail,
                        exception=None,
                        run_id=workflow_run_id,
                        handler_name="OutputHandler",
                    )
            run_result.final_output = parsed.value
        return run_result


def _infer_provider_from_model(model: Any) -> Optional[str]:
    if model is None or isinstance(model, str):
        return None
    if isinstance(model, OpenAIChatCompletionsModel):
        return "openai_compatible"
    return None
