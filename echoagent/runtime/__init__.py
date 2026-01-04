"""运行时扩展入口。"""

from echoagent.runtime.hooks import HookBus
from echoagent.runtime.plugins import Plugin

__all__ = ["HookBus", "Plugin"]
