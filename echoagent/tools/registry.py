from __future__ import annotations

from echoagent.tools.models import ToolHandler, ToolSpec


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolSpec, ToolHandler]] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = (spec, handler)

    def has(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> tuple[ToolSpec, ToolHandler]:
        if name not in self._tools:
            raise KeyError(f"Tool not registered: {name}")
        return self._tools[name]

    def list(self) -> list[ToolSpec]:
        return [entry[0] for entry in self._tools.values()]

    def clear(self) -> None:
        self._tools.clear()


def _new_registry() -> ToolRegistry:
    return ToolRegistry()


_DEFAULT_REGISTRY: ToolRegistry = _new_registry()


def get_default_registry() -> ToolRegistry:
    return _DEFAULT_REGISTRY


def reset_default_registry(registry: ToolRegistry | None = None) -> ToolRegistry:
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = registry or _new_registry()
    return _DEFAULT_REGISTRY
