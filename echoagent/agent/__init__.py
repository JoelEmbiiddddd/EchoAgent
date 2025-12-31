"""Agent and runtime execution module.

This module provides the complete agent infrastructure:

Agents:
- EchoAgent: Context-aware agent with profile-based behavior

Runtime Infrastructure:
- RuntimeTracker: Manages runtime state (tracing, printing, reporting, iteration tracking, data store)
- agent_step: Core execution primitive with span/printer integration

Runtime Access:
- get_current_tracker: Access the current RuntimeTracker from anywhere
- get_current_data_store: Convenience for accessing the data store

"""

from echoagent.agent.agent import EchoAgent
from echoagent.agent.tracker import (
    RuntimeTracker,
    get_current_tracker,
    get_current_data_store,
)
from echoagent.agent.executor import agent_step
__all__ = [
    # Agents
    "EchoAgent",
    # Runtime infrastructure
    "RuntimeTracker",
    # Execution primitives
    "agent_step",
    # Runtime access
    "get_current_tracker",
    "get_current_data_store",
]
