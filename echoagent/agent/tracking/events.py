from __future__ import annotations

from dataclasses import dataclass
from typing import Any


RUN_START = "RUN_START"
USER_MESSAGE = "USER_MESSAGE"
ASSISTANT_MESSAGE = "ASSISTANT_MESSAGE"
MODEL_OUTPUT = "MODEL_OUTPUT"
PARSE_RESULT = "PARSE_RESULT"
ERROR = "ERROR"
RUN_END = "RUN_END"
TOOL_OUTPUT = "TOOL_OUTPUT"
TOOL_RESULT = "TOOL_RESULT"


@dataclass
class RunEvent:
    type: str
    payload: dict[str, Any]
    ts: float
    run_id: str
