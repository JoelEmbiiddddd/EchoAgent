from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from pydantic import BaseModel

from echoagent.agent.prompting.assembler import ContextAssembler
from echoagent.agent.prompting.budget import ContextBudgeter
from echoagent.agent.prompting.renderer import PromptRenderer
from echoagent.context.policy import normalize_context_policy


class InstructionBuilder:
    """构建执行所需的上下文指令。"""

    @staticmethod
    def _serialize_payload(payload: Any) -> str | None:
        """将支持的 payload 类型规范化为 LLM 可消费的字符串。"""
        if payload is None:
            return None
        if isinstance(payload, str):
            return payload
        if isinstance(payload, BaseModel):
            return payload.model_dump_json(indent=2)
        if isinstance(payload, dict):
            return json.dumps(payload, indent=2)
        return str(payload)

    def build(self, state: Any, profile: Any, *, runtime: Optional[dict[str, Any]] = None) -> str:
        """基于运行时状态自动注入上下文并构建指令。"""
        payload = runtime.get("payload") if runtime else None
        payload_str = self._serialize_payload(payload)

        assembler = ContextAssembler()
        blocks = assembler.assemble(state, profile, payload=payload, payload_str=payload_str)

        context_budget = None
        context_policy = normalize_context_policy(getattr(profile, "context_policy", None))
        if context_policy.total_budget is not None:
            context_budget = context_policy.total_budget
        if profile and hasattr(profile, "policies"):
            policies = profile.policies
            if isinstance(policies, Mapping):
                context_budget = context_budget or policies.get("context_budget")
            else:
                context_budget = context_budget or getattr(policies, "context_budget", None)
        budgeter = ContextBudgeter()
        blocks = budgeter.trim(blocks, context_budget)

        renderer = PromptRenderer()
        return renderer.render(blocks)
