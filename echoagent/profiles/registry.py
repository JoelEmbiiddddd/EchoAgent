from __future__ import annotations

from typing import Any, Callable, Optional

from echoagent.profiles.defaults.base import base_profile_data
from echoagent.profiles.defaults.mcp_browser import mcp_browser_profile_data


_REGISTRY: dict[str, Callable[[], dict[str, Any]]] = {
    "base": base_profile_data,
    "mcp_browser": mcp_browser_profile_data,
}


def get_profile_data(profile_id: str) -> Optional[dict[str, Any]]:
    factory = _REGISTRY.get(profile_id)
    if not factory:
        return None
    return dict(factory())
