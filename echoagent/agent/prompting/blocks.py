from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ContextBlock:
    name: str
    content: str
    priority: int = 0
    max_chars: Optional[int] = None
