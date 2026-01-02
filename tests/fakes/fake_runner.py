from __future__ import annotations

from typing import Any, Callable, Optional

from pydantic import BaseModel

from echoagent.agent.runner import AgentRunner
from echoagent.agent.tracker import RuntimeTracker


class FakeRunner(AgentRunner):
    def __init__(
        self,
        *,
        run_result: Any = None,
        side_effect: Optional[Callable[[], Any]] = None,
        captured: Optional[dict[str, Any]] = None,
    ) -> None:
        self.run_result = run_result
        self.side_effect = side_effect
        self.captured = captured or {}

    async def open(self, *, runtime_config: Optional[Any] = None) -> None:
        _ = runtime_config

    async def run(
        self,
        *,
        tracker: RuntimeTracker,
        agent: Any,
        instructions: str,
        span_name: Optional[str] = None,
        span_type: str = "agent",
        output_model: Optional[type[BaseModel]] = None,
        sync: bool = False,
        printer_key: Optional[str] = None,
        printer_title: Optional[str] = None,
        printer_border_style: Optional[str] = None,
        span_kwargs: Optional[dict[str, Any]] = None,
        runtime_config: Optional[Any] = None,
    ) -> Any:
        self.captured["instructions"] = instructions
        if self.side_effect:
            return self.side_effect()
        return self.run_result

    async def close(self) -> None:
        return
