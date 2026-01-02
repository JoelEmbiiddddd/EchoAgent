from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from echoagent.profiles.profile_types import _serialize_config_value


class Profile(BaseModel):
    """Profile 配置模型（纯声明，不含运行期副作用）。"""

    # 原: echoagent/profiles/base.py:8-68 → 新: echoagent/profiles/models.py
    id: Optional[str] = Field(default=None, description="Profile identifier")
    instructions: str = Field(default="", description="The agent's system prompt/instructions that define its behavior")
    runtime_template: str = Field(default="", description="The runtime template for the agent's behavior")
    model: Optional[Any] = Field(default=None, description="Model override for this profile")
    output_schema: Optional[Any] = Field(default=None, description="Structured output schema for parsing")
    tools: Optional[list[Any]] = Field(default=None, description="List of tool objects to use for this profile")
    mcp_server_names: list[str] = Field(default_factory=list, description="List of MCP server names to resolve at runtime")
    description: Optional[str] = Field(default=None, description="Optional one-sentence description for agent capabilities")
    policies: dict[str, Any] = Field(default_factory=dict, description="Runtime policies for parsing and tool conflict")
    context_policy: dict[str, Any] = Field(
        default_factory=dict,
        description="Context policy for assembling canonical prompt blocks",
    )
    budget: dict[str, Any] = Field(default_factory=dict, description="Context or token budget settings")
    output: dict[str, Any] = Field(default_factory=dict, description="Output configuration")
    runtime: dict[str, Any] = Field(default_factory=dict, description="Runtime configuration")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional profile metadata")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def name(self) -> Optional[str]:
        return self.id

    @name.setter
    def name(self, value: Optional[str]) -> None:
        self.id = value

    def get_description(self) -> str:
        """获取 profile 描述文本。"""
        if self.description:
            return self.description

        first_line = self.instructions.split("\n")[0].strip()
        if first_line.startswith("You are a "):
            desc = first_line[10:].strip()
        elif first_line.startswith("You are an "):
            desc = first_line[11:].strip()
        else:
            desc = first_line
        return desc[:-1] if desc.endswith(".") else desc

    def render(self, **kwargs: Any) -> str:
        """渲染运行期模板。"""
        kwargs_lower = {k.lower(): str(v) for k, v in kwargs.items()}
        return self.runtime_template.format(**kwargs_lower)

    def to_raw_dict(self) -> dict[str, Any]:
        """保留原始对象的 dict 形式（用于运行期合并）。"""
        if hasattr(BaseModel, "model_dump"):
            return BaseModel.model_dump(self, mode="python")  # type: ignore[call-arg]
        return self.dict()

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if hasattr(BaseModel, "model_dump"):
            raw = BaseModel.model_dump(self, *args, **kwargs)  # type: ignore[call-arg]
        else:
            raw = self.dict(*args, **kwargs)
        return _serialize_config_value(raw)

    def to_debug_dict(self) -> dict[str, Any]:
        """输出稳定的 profile 调试信息。"""
        from echoagent.profiles.runtime import profile_debug_dict

        return profile_debug_dict(self)
