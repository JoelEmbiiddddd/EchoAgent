"""插件注册占位。"""


class PluginRegistry:
    """占位实现。"""

    def __init__(self) -> None:
        self._plugins: list[object] = []
