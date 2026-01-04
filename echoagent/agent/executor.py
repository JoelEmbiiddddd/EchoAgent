"""Core agent execution primitives."""

import traceback
from typing import Any, Optional

from agents import RunConfig, Runner
from agents.tracing.create import agent_span, function_span
from pydantic import BaseModel

from echoagent.agent.output_handler import OutputHandler
from echoagent.agent.tracker import RuntimeTracker
from echoagent.artifacts import record_parse_failure
from echoagent.utils.helpers import extract_final_output, serialize_content


class Executor:
    """仅负责调用底层 SDK 执行。"""

    async def run(
        self,
        agent: Any,
        instructions: str,
        *,
        context: Any,
        sync: bool = False,
        run_config: Optional[RunConfig] = None,
    ) -> Any:
        if sync:
            return Runner.run_sync(agent, instructions, context=context, run_config=run_config)
        return await Runner.run(agent, instructions, context=context, run_config=run_config)


async def agent_step(
    tracker: RuntimeTracker,
    agent,
    instructions: str,
    span_name: Optional[str] = None,
    span_type: str = "agent",
    output_model: Optional[type[BaseModel]] = None,
    sync: bool = False,
    printer_key: Optional[str] = None,
    printer_title: Optional[str] = None,
    printer_border_style: Optional[str] = None,
    **span_kwargs
) -> Any:
    """Run an agent with span tracking and optional output parsing.

    Args:
        tracker: RuntimeTracker for tracing, printing, etc.
        agent: The agent to run
        instructions: Instructions/prompt for the agent
        span_name: Name for the span (auto-detected from agent name if not provided)
        span_type: Type of span - "agent" or "function"
        output_model: Optional pydantic model to parse output
        sync: Whether to run synchronously
        printer_key: Optional key for printer updates (auto-detected from agent name if not provided)
        printer_title: Optional title for printer display (auto-detected from agent name if not provided)
        printer_border_style: Optional border color
        **span_kwargs: Additional kwargs for span (e.g., tools, input)

    Returns:
        Parsed output if output_model provided, otherwise Runner result
    """
    span_factory = agent_span if span_type == "agent" else function_span
    output_handler = OutputHandler()
    executor = Executor()

    handle = tracker.start_agent_step(
        agent=agent,
        span_name=span_name,
        span_factory=span_factory,
        span_kwargs=span_kwargs,
        printer_key=printer_key,
        printer_title=printer_title,
        printer_border_style=printer_border_style,
    )

    status = "success"
    error_message: Optional[str] = None

    try:
        with tracker.span_scope(handle) as span:
            # Activate context so tools can access it
            with tracker.activate():
                run_config = RunConfig(
                    tracing_disabled=not tracker.enable_tracing,
                    trace_include_sensitive_data=tracker.trace_sensitive,
                )
                result = await executor.run(
                    agent,
                    instructions,
                    context=tracker.data_store,
                    sync=sync,
                    run_config=run_config,
                )

                # if agent.name == "web_searcher_agent":
                #     import ipdb; ipdb.set_trace()

                # Handle EchoAgent parse_output (for legacy string parsers)
                from echoagent.agent.agent import EchoAgent
                if isinstance(agent, EchoAgent):
                    result = await agent.parse_output(result)

            raw_output = extract_final_output(result)
            panel_content = serialize_content(raw_output)

            tracker.log_agent_panel(handle, panel_content)

            if output_model:
                try:
                    parsed = output_handler.parse(raw_output, schema=output_model, mode="strict")
                except Exception as exc:  # noqa: BLE001 - re-raise after observability
                    schema_name = output_handler._schema_name(output_model)
                    error_detail = output_handler._build_error_detail(raw_output, schema_name, exc)
                    content = f"schema: {error_detail.schema_name}\nerror: {error_detail.message}"
                    tracker.log_panel(
                        "Parse Error",
                        content,
                        border_style=handle.printer_border_style,
                        iteration=handle.iteration_idx,
                    )
                    if span and hasattr(span, "set_output"):
                        span.set_output({"parse_error": error_detail.to_dict()})
                    _save_parse_failure_snapshot(tracker, raw_output, error_detail, exc, agent=agent)
                    raise
                if span and hasattr(span, "set_output") and isinstance(parsed.value, BaseModel):
                    span.set_output(parsed.value.model_dump())
                return parsed.value
            tracker.preview_output(handle, panel_content[:200])
            return result
    except Exception as exc:  # noqa: BLE001 - propagate after logging
        status = "error"
        error_message = str(exc)
        raise
    finally:
        tracker.finish_agent_step(
            handle,
            status=status,
            error=error_message,
        )


def _save_parse_failure_snapshot(
    tracker: RuntimeTracker,
    raw_output: Any,
    error_detail: Any,
    exception: BaseException,
    *,
    agent: Any,
) -> None:
    settings = getattr(tracker, "artifact_settings", None)
    if not settings or not getattr(settings, "enabled", False):
        return
    if not getattr(settings, "debug_enabled", False):
        return
    if not getattr(settings, "save_parse_failures", False):
        return
    store_getter = getattr(tracker, "get_run_artifact_store", None)
    if not callable(store_getter):
        return
    store = store_getter()
    if store is None:
        return
    error_payload: Optional[dict[str, Any]] = None
    if error_detail is not None:
        to_dict = getattr(error_detail, "to_dict", None)
        if callable(to_dict):
            error_payload = to_dict()
        else:
            error_payload = {"message": str(error_detail)}
    traceback_text = "".join(
        traceback.format_exception(type(exception), exception, exception.__traceback__)
    )
    schema_name = getattr(error_detail, "schema_name", None) if error_detail else None
    error_type = None
    error_message = None
    if error_payload:
        error_type = error_payload.get("exception_type") or error_payload.get("type")
        error_message = error_payload.get("message")
    if error_type is None:
        error_type = exception.__class__.__name__
    if error_message is None:
        error_message = str(exception)
    run_id = getattr(tracker, "run_id", None) or getattr(tracker, "experiment_id", None) or ""
    profile_name = getattr(agent, "_identifier", None)
    ref = record_parse_failure(
        raw_output,
        store=store,
        run_id=run_id,
        agent_name=getattr(agent, "name", ""),
        profile_name=profile_name,
        schema_name=schema_name,
        error_type=error_type,
        error_message=error_message,
        traceback_text=traceback_text,
        handler_name="OutputHandler",
        error_detail=error_payload,
        path_prefix="debug",
    )
    record = getattr(tracker, "record_artifact", None)
    if callable(record):
        record(ref, event_type="parse_failure")
