import asyncio
import functools
import hashlib
import time
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Union

from loguru import logger
from rich.console import Console

from echoagent.utils.config import BaseConfig, resolve_config
from echoagent.agent import (
    RuntimeTracker,
)
from echoagent.artifacts import RunReporter
from echoagent.context.iteration_summarizer import IterationSummarizer
from echoagent.context.snapshot import dump_json
from echoagent.observability.runlog.utils import truncate_text
from echoagent.utils import Printer, get_experiment_timestamp


class BaseWorkflow:
    """Base class for all workflows with common configuration and setup."""

    def __init__(self, config: Union[str, Path, Mapping[str, Any], BaseConfig]):
        """Initialize the workflow using a single configuration input.

        Args:
            spec: Configuration specification:
                - str/Path: Load YAML/JSON file
                - dict with 'config_path': Load file, then deep-merge dict on top (dict wins)
                - dict without 'config_path': Use as-is
                - BaseConfig: Use as-is
            strict: Whether to strictly validate configuration (default: True).

        Examples:
            # Load from file
            BaseWorkflow("workflows/configs/data_science.yaml")

            # Dict without config_path
            BaseWorkflow({"provider": "openai", "data": {"path": "data.csv"}})

            # Dict that patches a file (use 'config_path')
            BaseWorkflow({
                "config_path": "workflows/configs/data_science.yaml",
                "data": {"path": "data/banana_quality.csv"},
                "user_prompt": "Custom prompt..."
            })

            # BaseConfig object
            BaseWorkflow(BaseConfig(provider="openai", data={"path": "data.csv"}))
        """
        self.console = Console()

        # Resolve configuration using the new unified API
        self.config = resolve_config(config)

        # Generic workflow settings
        self.experiment_id = get_experiment_timestamp()

        workflow_settings = self.config.pipeline
        default_slug = self.__class__.__name__.replace("Workflow", "").lower()
        self.pipeline_slug = (
            workflow_settings.get("slug")
            or workflow_settings.get("name")
            or default_slug
        )
        self.workflow_name = (
            workflow_settings.get("workflow_name")
            or workflow_settings.get("name")
        )
        if not self.workflow_name:
            # Default pattern: use class name + experiment_id
            workflow_name = self.__class__.__name__.replace("Workflow", "").lower()
            self.workflow_name = f"{workflow_name}_{self.experiment_id}"

        self.verbose = workflow_settings.get("verbose", True)
        self.max_iterations = workflow_settings.get("max_iterations", 5)
        self.max_time_minutes = workflow_settings.get("max_time_minutes", 10)

        # Research workflow name (optional, for workflows with research components)
        self.research_workflow_name = workflow_settings.get(
            "research_workflow_name",
            f"researcher_{self.experiment_id}",
        )

        # Iterative workflow state
        self.iteration = 0
        self.start_time: Optional[float] = None
        self.should_continue = True
        self.constraint_reason = ""

        # Setup tracing configuration and logging
        self._setup_tracing()

        # Create runtime tracker immediately (owns all runtime infrastructure)
        # Context will be set by subclasses after they create it
        self._runtime_tracker = RuntimeTracker(
            console=self.console,
            context=None,  # Set later via _set_tracker_context()
            enable_tracing=self.enable_tracing,
            trace_sensitive=self.trace_sensitive,
            experiment_id=self.experiment_id,
        )
        self._iteration_summarizer: Optional[IterationSummarizer] = None

    def __setattr__(self, name: str, value: Any) -> None:
        """Auto-setup context when assigned to enable transparent integration."""
        super().__setattr__(name, value)
        # Auto-setup context when it's assigned (if tracker is ready)
        if name == "context" and hasattr(self, "_runtime_tracker"):
            value.state.max_time_minutes = self.max_time_minutes
            self._set_tracker_context(value)

    # ============================================
    # Core Properties
    # ============================================

    @property
    def enable_tracing(self) -> bool:
        """Get tracing enabled flag from config."""
        return self.config.pipeline.get("enable_tracing", True)

    @property
    def trace_sensitive(self) -> bool:
        """Get trace sensitive data flag from config."""
        return self.config.pipeline.get("trace_include_sensitive_data", False)

    @property
    def state(self) -> Optional[Any]:
        """Get workflow state if available."""
        if hasattr(self, 'context') and hasattr(self.context, 'state'):
            return self.context.state
        return None

    @property
    def printer(self) -> Optional[Printer]:
        """Delegate to tracker."""
        return self._runtime_tracker.printer

    @property
    def reporter(self) -> Optional[RunReporter]:
        """Delegate to tracker."""
        return self._runtime_tracker.reporter

    @property
    def runtime_tracker(self) -> RuntimeTracker:
        """Get the runtime tracker (created in __init__)."""
        return self._runtime_tracker

    def _set_tracker_context(self, context: Any) -> None:
        """Set the context reference on the runtime tracker.

        Should be called by subclasses after creating their context.

        Args:
            context: The context object to set
        """
        self._runtime_tracker.context = context

    def _setup_context(self, context: Any) -> None:
        """Setup context with state and tracker integration.

        Call this after creating context in subclass __init__.
        Initializes max_time_minutes and connects tracker to context.

        Args:
            context: The context object to setup
        """
        context.state.max_time_minutes = self.max_time_minutes
        self._set_tracker_context(context)

    # ============================================
    # Printer & Reporter Management
    # ============================================

    def start_printer(self) -> Printer:
        """Delegate to tracker."""
        return self._runtime_tracker.start_printer()

    def stop_printer(self) -> None:
        """Delegate to tracker."""
        self._runtime_tracker.stop_printer()

    def start_group(
        self,
        group_id: str,
        *,
        title: Optional[str] = None,
        border_style: Optional[str] = None,
        iteration: Optional[int] = None,
    ) -> None:
        """Delegate to tracker."""
        self._runtime_tracker.start_group(
            group_id,
            title=title,
            border_style=border_style,
            iteration=iteration,
        )

    def end_group(
        self,
        group_id: str,
        *,
        is_done: bool = True,
        title: Optional[str] = None,
        iteration: Optional[int] = None,
        snapshot: Optional[dict[str, Any]] = None,
    ) -> None:
        """Delegate to tracker."""
        self._runtime_tracker.end_group(
            group_id,
            is_done=is_done,
            title=title,
            iteration=iteration,
            snapshot=snapshot,
        )

    # ============================================
    # Initialization & Setup
    # ============================================

    def _initialize_run(
        self,
        additional_logging: Optional[Callable] = None,
        enable_reporter: bool = True,
        outputs_dir: Optional[Union[str, Path]] = None,
        enable_printer: bool = True,
        workflow_name: Optional[str] = None,
        trace_metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a workflow run with logging, printer, and tracing.

        Args:
            additional_logging: Optional callable for workflow-specific logging
            enable_reporter: Whether to create/start the RunReporter
            outputs_dir: Override outputs directory (None uses config value)
            enable_printer: Whether to start the Printer
            workflow_name: Override workflow name (None uses self.workflow_name)
            trace_metadata: Additional metadata to merge into trace context

        Returns:
            Trace context manager for the workflow
        """
        # Basic logging
        logger.info(
            f"Running {self.__class__.__name__} with experiment_id: {self.experiment_id}"
        )

        # Workflow-specific logging
        if additional_logging:
            additional_logging()

        # Use workflow_name override if provided, otherwise use instance workflow_name
        effective_workflow_name = workflow_name or self.workflow_name

        # Conditionally create and start reporter
        if enable_reporter:
            # Use outputs_dir override if provided, otherwise use config value
            effective_outputs_dir = Path(outputs_dir) if outputs_dir else Path(self.config.pipeline.get("outputs_dir", "outputs"))

            self._runtime_tracker.initialize_reporter(
                base_dir=effective_outputs_dir,
                pipeline_slug=self.pipeline_slug,
                workflow_name=effective_workflow_name,
                experiment_id=self.experiment_id,
                config=self.config,
            )

        # Conditionally start printer and update workflow
        if enable_printer:
            self.start_printer()
            if self.printer:
                self.printer.update_item(
                    "workflow",
                    f"Workflow: {effective_workflow_name}",
                    is_done=True,
                    hide_checkmark=True,
                )

        # Create trace context with merged metadata
        base_trace_metadata = {
            "experiment_id": self.experiment_id,
            "includes_sensitive_data": "true" if self.trace_sensitive else "false",
        }

        # Merge custom trace_metadata if provided
        if trace_metadata:
            base_trace_metadata.update(trace_metadata)

        return self.trace_context(effective_workflow_name, metadata=base_trace_metadata)

    def _setup_tracing(self) -> None:
        """Setup tracing configuration with user-friendly output.

        Subclasses can override this method to add workflow-specific information.
        """
        if self.enable_tracing:
            workflow_name = self.__class__.__name__.replace("Workflow", "")
            self.console.print(f"🍌 Starting {workflow_name} Workflow with Tracing")
            self.console.print(f"🔧 Provider: {self.config.provider}")
            self.console.print(f"🤖 Model: {self.config.llm.model_name}")
            self.console.print("🔍 Tracing: Enabled")
            self.console.print(
                f"🔒 Sensitive Data in Traces: {'Yes' if self.trace_sensitive else 'No'}"
            )
            self.console.print(f"🏷️ Workflow: {self.workflow_name}")
        else:
            workflow_name = self.__class__.__name__.replace("Workflow", "")
            self.console.print(f"🍌 Starting {workflow_name} Workflow")
            self.console.print(f"🔧 Provider: {self.config.provider}")
            self.console.print(f"🤖 Model: {self.config.llm.model_name}")

    def trace_context(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """Create a trace context - delegates to RuntimeTracker."""
        return self.runtime_tracker.trace_context(name, metadata=metadata)

    def span_context(self, span_factory, **kwargs):
        """Create a span context - delegates to RuntimeTracker."""
        return self.runtime_tracker.span_context(span_factory, **kwargs)

    def update_printer(self, *args, **kwargs) -> None:
        """Update printer status if printer is active.

        Delegates to RuntimeTracker.update_printer(). See RuntimeTracker.update_printer() for full documentation.
        """
        self.runtime_tracker.update_printer(*args, **kwargs)

    # ============================================
    # Context Managers & Utilities
    # ============================================

    @contextmanager
    def run_context(
        self,
        additional_logging: Optional[Callable] = None,
        # Timer control
        start_timer: bool = True,
        # Reporter control
        enable_reporter: bool = True,
        outputs_dir: Optional[Union[str, Path]] = None,
        # Printer control
        enable_printer: bool = True,
        # Tracing control
        workflow_name: Optional[str] = None,
        trace_metadata: Optional[Dict[str, Any]] = None,
    ):
        """Context manager for run lifecycle handling.

        Manages trace context initialization, printer lifecycle, and cleanup.
        Provides fine-grained control over workflow components.

        Args:
            additional_logging: Optional callable for workflow-specific logging
            start_timer: Whether to start the constraint checking timer (default: True)
            enable_reporter: Whether to create/start the RunReporter (default: True)
            outputs_dir: Override outputs directory (default: None, uses config value)
            enable_printer: Whether to start the live status Printer (default: True)
            workflow_name: Override workflow name for this run (default: None, uses self.workflow_name)
            trace_metadata: Additional metadata to merge into trace context (default: None)

        Yields:
            Trace context for the workflow
        """
        # Track which resources existed before initialization
        had_reporter = self.reporter is not None
        had_printer = self.printer is not None

        # Conditionally start workflow timer for constraint checking
        if start_timer:
            self.start_time = time.time()

        effective_outputs_dir = Path(outputs_dir) if outputs_dir else Path(self.config.pipeline.get("outputs_dir", "outputs"))
        effective_workflow_name = workflow_name or self.workflow_name

        trace_ctx = self._initialize_run(
            additional_logging=additional_logging,
            enable_reporter=enable_reporter,
            outputs_dir=effective_outputs_dir,
            enable_printer=enable_printer,
            workflow_name=effective_workflow_name,
            trace_metadata=trace_metadata,
        )

        # Track what was actually created (not pre-existing)
        created_reporter = enable_reporter and not had_reporter and self.reporter is not None
        created_printer = enable_printer and not had_printer and self.printer is not None
        self.runtime_tracker.start_runlog(outputs_dir=effective_outputs_dir)
        run_dir_value = self.runtime_tracker.run_dir_relative or None
        self.runtime_tracker.emit_event(
            "RUN_START",
            {
                "pipeline_slug": self.pipeline_slug,
                "workflow_name": effective_workflow_name,
                "experiment_id": self.experiment_id,
                "provider": getattr(self.config, "provider", None),
                "model": getattr(getattr(self.config, "llm", None), "model_name", None),
                "run_dir": run_dir_value,
            },
        )

        status = "success"
        error_message: Optional[str] = None
        try:
            with trace_ctx:
                # Activate tracker so agents can access it automatically via get_current_tracker()
                with self.runtime_tracker.activate():
                    yield trace_ctx
        except Exception as exc:
            status = "error"
            error_message = str(exc)
            raise
        finally:
            # Only cleanup resources that were created by this context
            # Note: stop_printer() handles both printer and reporter cleanup
            if created_printer or created_reporter:
                self.stop_printer()
            self.runtime_tracker.emit_event(
                "RUN_END",
                {
                    "status": status,
                    "error": error_message,
                },
            )
            self.runtime_tracker.end_runlog()

    # ============================================
    # Iteration & Group Management
    # ============================================

    def begin_iteration(
        self,
        title: Optional[str] = None,
        border_style: str = "white"
    ) -> Any:
        """Begin a new iteration with its associated group.

        Combines context.begin_iteration() + start_group() into a single call.
        Automatically manages the group_id internally.

        Args:
            title: Optional custom title (default: "Iteration {index}")
            border_style: Border style for the group (default: "white")

        Returns:
            The iteration record
        """
        iteration = self.context.begin_iteration()
        self.iteration = iteration.index

        # Derive group_id from iteration index
        group_id = f"iter-{iteration.index}"
        display_title = title or f"Iteration {iteration.index}"
        self.start_group(
            group_id,
            title=display_title,
            border_style=border_style,
            iteration=iteration.index,
        )

        return iteration

    def end_iteration(self, is_done: bool = True) -> None:
        """End the current iteration and its associated group.

        Combines context.mark_iteration_complete() + end_group() into a single call.
        Automatically derives group_id from current iteration.

        Args:
            is_done: Whether the iteration completed successfully (default: True)
        """
        self.context.mark_iteration_complete()
        record = self.context.state.current_iteration
        if record.is_complete() and not record.summarized:
            digest = self._get_iteration_summarizer().summarize_sync(
                self.context,
                record,
                query=getattr(self.context.state, "query", None),
            )
            record.set_digest(digest)

        snapshot_payload: Optional[dict[str, Any]] = None
        run_dir = self.runtime_tracker.run_dir
        if run_dir is not None:
            try:
                snapshot_path = Path(run_dir) / "snapshots" / f"iter_{record.index}.json"
                dump_json(self.context.state, snapshot_path)
                snapshot_hash = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
                snapshot_payload = {
                    "path": f"snapshots/iter_{record.index}.json",
                    "hash": snapshot_hash,
                }
            except Exception as exc:
                traceback_text = "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                )
                self.runtime_tracker.emit_event(
                    "ERROR",
                    {
                        "where": "snapshot",
                        "exception_type": exc.__class__.__name__,
                        "message": str(exc),
                        "traceback": truncate_text(traceback_text, 4000),
                        "iteration": record.index,
                    },
                )
        group_id = f"iter-{self.iteration}"
        self.end_group(
            group_id,
            is_done=is_done,
            iteration=record.index,
            snapshot=snapshot_payload,
        )

    def _get_iteration_summarizer(self) -> IterationSummarizer:
        if self._iteration_summarizer is None:
            llm_name = getattr(getattr(self.config, "llm", None), "model_name", None)
            provider = getattr(self.config, "provider", None)
            self._iteration_summarizer = IterationSummarizer(
                llm=str(llm_name) if llm_name else "",
                provider=provider,
            )
        return self._iteration_summarizer

    def iterate(
        self,
        start_index: int = 1,
        title: Optional[str] = None,
        border_style: str = "white"
    ) -> Any:
        """Smart iteration management - auto-creates and advances iterations.

        Single-command iteration handling that automatically:
        - Creates first iteration on first call
        - Ends previous iteration and starts next on subsequent calls
        - Supports custom starting index

        Args:
            start_index: Starting iteration number (default: 1)
            title: Optional custom title (default: "Iteration {index}")
            border_style: Border style for the group (default: "white")

        Returns:
            The iteration record

        Example:
            while self.iteration < self.max_iterations:
                self.iterate()  # Single command!
                # ... do work ...
        """
        # If no iterations exist, create first one
        if not self.context.state.iterations:
            iteration_record = self.begin_iteration(title=title, border_style=border_style)
            # Override iteration index if custom start requested
            if start_index != 1:
                self.iteration = start_index
                iteration_record.index = start_index
            return iteration_record

        # Close previous iteration if still open, start new one
        if not self.context.state.current_iteration.is_complete():
            self.end_iteration()

        return self.begin_iteration(title=title, border_style=border_style)

    # ============================================
    # Execution Entry Points
    # ============================================

    def run_sync(self, *args, **kwargs):
        """Synchronous wrapper for the async run method."""
        return asyncio.run(self.run(*args, **kwargs))

    async def run(self, query: Any = None) -> Any:
        """Execute the workflow - must be implemented by subclasses.

        Each workflow implements its own complete execution logic.
        Use the utility methods and context managers provided by BaseWorkflow.

        Args:
            query: Optional query input (can be None for workflows without input)

        Returns:
            Final result (workflow-specific)

        Raises:
            NotImplementedError: If subclass doesn't implement this method
        """
        raise NotImplementedError("Subclasses must implement run()")


    # ============================================
    # Integration with Runner Module
    # ============================================

def autotracing(
    additional_logging: Optional[Callable] = None,
    start_timer: bool = True,
    enable_reporter: bool = True,
    outputs_dir: Optional[Union[str, Path]] = None,
    enable_printer: bool = True,
    workflow_name: Optional[str] = None,
    trace_metadata: Optional[Dict[str, Any]] = None,
):
    """Decorator factory that wraps async methods with run_context lifecycle management.

    This decorator provides automatic initialization and cleanup of workflow resources
    (reporter, printer, tracing) without requiring explicit `with self.run_context():` usage.

    Args:
        additional_logging: Optional callable for workflow-specific logging
        start_timer: Whether to start the constraint checking timer (default: True)
        enable_reporter: Whether to create/start the RunReporter (default: True)
        outputs_dir: Override outputs directory (default: None, uses config value)
        enable_printer: Whether to start the live status Printer (default: True)
        workflow_name: Override workflow name for this run (default: None, uses self.workflow_name)
        trace_metadata: Additional metadata to merge into trace context (default: None)

    Returns:
        Decorator that wraps the method with run_context lifecycle

    Usage:
        @autotracing()
        async def run(self, query: Any = None) -> Any:
            # Workflow logic here - no 'with' statement needed
            pass

        @autotracing(enable_printer=False, start_timer=False)
        async def run_silent(self, query: Any = None) -> Any:
            # Runs without printer or timer
            pass

    Note:
        The existing `run_context()` context manager remains available for advanced use cases
        where explicit control over the context lifecycle is needed.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            with self.run_context(
                additional_logging=additional_logging,
                start_timer=start_timer,
                enable_reporter=enable_reporter,
                outputs_dir=outputs_dir,
                enable_printer=enable_printer,
                workflow_name=workflow_name,
                trace_metadata=trace_metadata,
            ):
                return await func(self, *args, **kwargs)
        return wrapper
    return decorator
