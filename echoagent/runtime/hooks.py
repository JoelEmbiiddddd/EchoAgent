from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple


class HookBus:
    """轻量 HookBus，支持优先级注册与触发。"""

    def __init__(self) -> None:
        self._handlers: Dict[str, List[Tuple[int, Callable[..., Any]]]] = {}

    def register(self, name: str, handler: Callable[..., Any], *, priority: int = 0) -> None:
        handlers = self._handlers.setdefault(name, [])
        handlers.append((priority, handler))
        handlers.sort(key=lambda item: item[0], reverse=True)

    def emit(self, name: str, *args: Any, **kwargs: Any) -> list[Any]:
        results: list[Any] = []
        for _, handler in self._handlers.get(name, []):
            try:
                results.append(handler(*args, **kwargs))
            except Exception:
                continue
        return results
