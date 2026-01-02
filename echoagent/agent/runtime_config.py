from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from echoagent.profiles.base import Profile


@dataclass
class RuntimeConfig:
    mcp_server_names: list[str] = field(default_factory=list)
    mcp_servers: list[Any] = field(default_factory=list)

    @classmethod
    def from_profile_input(
        cls,
        profile: Any,
        *,
        overrides: Optional[dict[str, Any]] = None,
    ) -> "RuntimeConfig":
        overrides = overrides or {}
        server_names: list[str] = []
        servers: list[Any] = []
        if "mcp_server_names" in overrides:
            server_names = list(overrides.get("mcp_server_names") or [])
        if "mcp_servers" in overrides:
            servers = list(overrides.get("mcp_servers") or [])
        if server_names or servers:
            return cls(mcp_server_names=server_names, mcp_servers=servers)
        if isinstance(profile, Profile):
            return cls(mcp_server_names=list(profile.mcp_server_names or []))
        if isinstance(profile, Mapping):
            return cls(mcp_server_names=list(profile.get("mcp_server_names") or []))
        if hasattr(profile, "mcp_server_names"):
            return cls(mcp_server_names=list(getattr(profile, "mcp_server_names") or []))
        return cls()
