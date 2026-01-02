from __future__ import annotations

from typing import Any, Optional, Protocol

from pydantic import BaseModel

from echoagent.agent.executor import agent_step
from echoagent.agent.tracker import RuntimeTracker
from echoagent.agent.runtime_config import RuntimeConfig


class AgentRunner(Protocol):
    async def open(self, *, runtime_config: Optional[RuntimeConfig] = None) -> None:
        ...

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
        runtime_config: Optional[RuntimeConfig] = None,
    ) -> Any:
        ...

    async def close(self) -> None:
        ...


class ExecutorRunner(AgentRunner):
    def __init__(self) -> None:
        self._connected_servers: list[Any] = []

    async def open(self, *, runtime_config: Optional[RuntimeConfig] = None) -> None:
        if runtime_config and runtime_config.mcp_servers:
            self._connected_servers = list(runtime_config.mcp_servers)

    async def close(self) -> None:
        self._connected_servers = []

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
        runtime_config: Optional[RuntimeConfig] = None,
    ) -> Any:
        opened_here = False
        if runtime_config and not self._connected_servers:
            await self.open(runtime_config=runtime_config)
            opened_here = True
        try:
            return await agent_step(
                tracker=tracker,
                agent=agent,
                instructions=instructions,
                span_name=span_name,
                span_type=span_type,
                output_model=output_model,
                sync=sync,
                printer_key=printer_key,
                printer_title=printer_title,
                printer_border_style=printer_border_style,
                **(span_kwargs or {}),
            )
        finally:
            if opened_here:
                await self.close()
