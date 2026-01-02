from __future__ import annotations

from typing import Any

from echoagent.context.context import Context
from echoagent.skills.spec import SkillAsset


def activate_skill(context: Context, asset: SkillAsset) -> None:
    state = context.state
    execution = state.execution
    execution.active_skill_id = asset.index.skill_id
    execution.allowed_tools = list(asset.index.allowed_tools)
    execution.model_override = asset.index.model_override
    execution.disable_model_invocation = asset.index.disable_model_invocation

    state.active_skill = _model_dump(asset.index)
    state.active_skill_markdown = asset.markdown
    state.active_skill_text = asset.markdown

    state.record_event(
        "SKILL_ACTIVATE",
        f"Activated skill: {asset.index.skill_id}",
        meta={
            "skill_id": asset.index.skill_id,
            "allowed_tools": list(asset.index.allowed_tools),
            "model_override": asset.index.model_override,
            "disable_model_invocation": asset.index.disable_model_invocation,
        },
    )


def _model_dump(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump()  # type: ignore[call-arg]
    if hasattr(item, "dict"):
        return item.dict()  # type: ignore[call-arg]
    if isinstance(item, dict):
        return dict(item)
    return {"value": str(item)}
