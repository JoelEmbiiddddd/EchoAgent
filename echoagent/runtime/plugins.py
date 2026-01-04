from __future__ import annotations

from echoagent.runtime.hooks import HookBus


class Plugin:
    """插件基类。"""

    def setup(self, bus: HookBus) -> None:
        _ = bus
        return None
