from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from echoagent.context.state import (
    BaseIterationRecord,
    ConversationState,
    identity_wrapper,
)

class Context:
    """Central coordinator for conversation state and iteration management."""

    def __init__(self, state: Optional[ConversationState] = None) -> None:
        """Initialize context with conversation state."""
        if state is not None and not isinstance(state, ConversationState):
            raise TypeError(f"state must be ConversationState or None, got {type(state)}")
        self._state = state or ConversationState()
        self.modules: Dict[str, Any] = {}
        self.context_modules = self.modules

    @property
    def state(self) -> ConversationState:
        return self._state

    @property
    def profiles(self) -> Optional[Dict[str, Any]]:
        profiles = self.modules.get("profiles")
        if profiles is None:
            return None
        return profiles

    @profiles.setter
    def profiles(self, value: Optional[Dict[str, Any]]) -> None:
        if value is None:
            self.modules.pop("profiles", None)
        else:
            self.modules["profiles"] = value

    def register_context_module(self, name: str, module: Any) -> None:
        self.modules[name] = module

    def get_context_module(self, name: str) -> Any:
        if name not in self.modules:
            raise ValueError(f"Context module {name} not found")
        return self.modules[name]

    def get_with_wrapper(self, key: str, wrapper: Callable[[Any], Any] = identity_wrapper) -> Any:
        return self._state.get_with_wrapper(key, wrapper)

    def begin_iteration(self) -> BaseIterationRecord:
        """Start a new iteration and return its record.

        Automatically starts the conversation state timer on first iteration.

        Returns:
            The iteration record
        """
        # Lazy timer start: start on first iteration if not already started
        if self._state.started_at is None:
            self._state.start_timer()

        iteration = self._state.begin_iteration()
        return iteration

    def mark_iteration_complete(self) -> None:
        """Mark the current iteration as complete."""
        self._state.mark_iteration_complete()
