from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel

from echoagent.agent.prompting.blocks import ContextBlock
from echoagent.agent.prompting.history_renderer import render_iteration_history
from echoagent.context.policy import apply_block_policy, normalize_context_policy


class ContextAssembler:
    """将上下文拆分为可渲染的区块集合。"""

    def assemble(
        self,
        state: Any,
        profile: Any,
        *,
        payload: Any = None,
        payload_str: Optional[str] = None,
    ) -> list[ContextBlock]:
        policy = normalize_context_policy(getattr(profile, "context_policy", None))
        if profile and hasattr(profile, "runtime_template") and profile.runtime_template:
            block = self._build_runtime_template_block(state, profile, payload, payload_str, policy)
            if block is not None:
                return [block]
        return self._build_fallback_blocks(state, payload_str, policy)

    def _build_runtime_template_block(
        self,
        state: Any,
        profile: Any,
        payload: Any,
        payload_str: Optional[str],
        policy: Any,
    ) -> Optional[ContextBlock]:
        block_policy = apply_block_policy("RUNTIME_TEMPLATE", policy)
        if block_policy is None:
            return None
        template = profile.runtime_template
        placeholders = set(re.findall(r"\{([a-z_]+)\}", template))

        context_dict: dict[str, str] = {}

        if "runtime_input" in placeholders and payload is not None:
            context_dict["runtime_input"] = payload_str or ""

        for placeholder in placeholders:
            if placeholder in context_dict:
                continue
            value = getattr(state, placeholder, None)
            if value is not None:
                context_dict[placeholder] = str(value)
                continue
            context_dict[placeholder] = ""

        if payload is not None and isinstance(payload, BaseModel):
            try:
                payload_dict = payload.model_dump()
                for field_name, field_value in payload_dict.items():
                    lowercased_key = field_name.lower()
                    if lowercased_key in placeholders:
                        context_dict[lowercased_key] = str(field_value) if field_value is not None else ""
            except Exception:
                pass

        if payload_str is not None:
            for key in ("task", "payload", "input"):
                if key in placeholders and key not in context_dict:
                    context_dict[key] = payload_str

        rendered_text = profile.render(**context_dict)
        return ContextBlock(
            name="RUNTIME_TEMPLATE",
            content=rendered_text,
            priority=100,
            max_chars=block_policy.max_chars,
        )

    def _build_fallback_blocks(
        self,
        state: Any,
        payload_str: Optional[str],
        policy: Any,
    ) -> list[ContextBlock]:
        blocks: list[ContextBlock] = []

        query = getattr(state, "query", None)
        block_policy = apply_block_policy("ORIGINAL_QUERY", policy)
        if query and block_policy is not None:
            blocks.append(
                ContextBlock(
                    name="ORIGINAL_QUERY",
                    content=f"[ORIGINAL QUERY]\n{query}",
                    priority=100,
                    max_chars=block_policy.max_chars,
                )
            )

        skill_index = getattr(state, "available_skills_text", "") or getattr(state, "skills_index_text", "")
        block_policy = apply_block_policy("SKILL_INDEX", policy)
        if skill_index and block_policy is not None:
            blocks.append(
                ContextBlock(
                    name="SKILL_INDEX",
                    content=f"[SKILL INDEX]\n{skill_index}",
                    priority=97,
                    max_chars=block_policy.max_chars,
                )
            )

        active_skill = getattr(state, "active_skill_text", "") or getattr(state, "active_skill_markdown", "")
        block_policy = apply_block_policy("ACTIVE_SKILL", policy)
        if active_skill and block_policy is not None:
            blocks.append(
                ContextBlock(
                    name="ACTIVE_SKILL",
                    content=f"[ACTIVE SKILL]\n{active_skill}",
                    priority=98,
                    max_chars=block_policy.max_chars,
                )
            )

        event_history = self._render_message_history(getattr(state, "events", []) or [])
        block_policy = apply_block_policy("MESSAGE_HISTORY", policy)
        if event_history and block_policy is not None:
            blocks.append(
                ContextBlock(
                    name="MESSAGE_HISTORY",
                    content=f"[MESSAGE HISTORY]\n{event_history}",
                    priority=95,
                    max_chars=block_policy.max_chars,
                )
            )

        iterations = getattr(state, "iterations", []) or []
        current_iteration = iterations[-1] if iterations else None
        history = render_iteration_history(
            iterations,
            include_current=False,
            current_iteration=current_iteration,
        )
        block_policy = apply_block_policy("PREVIOUS_ITERATIONS", policy)
        if history and block_policy is not None:
            blocks.append(
                ContextBlock(
                    name="PREVIOUS_ITERATIONS",
                    content=f"[PREVIOUS ITERATIONS]\n{history}",
                    priority=90,
                    max_chars=block_policy.max_chars,
                )
            )

        tool_results = self._render_tool_results(getattr(state, "events", []) or [])
        block_policy = apply_block_policy("TOOL_RESULTS", policy)
        if tool_results and block_policy is not None:
            blocks.append(
                ContextBlock(
                    name="TOOL_RESULTS",
                    content=f"[TOOL RESULTS]\n{tool_results}",
                    priority=85,
                    max_chars=block_policy.max_chars,
                )
            )

        block_policy = apply_block_policy("CURRENT_INPUT", policy)
        if payload_str and block_policy is not None:
            blocks.append(
                ContextBlock(
                    name="CURRENT_INPUT",
                    content=f"[CURRENT INPUT]\n{payload_str}",
                    priority=80,
                    max_chars=block_policy.max_chars,
                )
            )

        return blocks

    def _render_message_history(self, events: list[Any]) -> str:
        lines: list[str] = []
        for event in events:
            event_type = getattr(event, "type", None) or getattr(event, "get", lambda *_: None)("type")
            if event_type not in {"USER_MESSAGE", "ASSISTANT_MESSAGE"}:
                continue
            content = getattr(event, "content", None)
            if content is None and isinstance(event, dict):
                content = event.get("content")
            if not content:
                continue
            label = "USER" if event_type == "USER_MESSAGE" else "ASSISTANT"
            lines.append(f"[{label}]\n{content}")
        return "\n\n".join(lines).strip()

    def _render_tool_results(self, events: list[Any]) -> str:
        latest: dict[str, Any] = {}
        for event in events:
            event_type = getattr(event, "type", None) or getattr(event, "get", lambda *_: None)("type")
            if event_type != "TOOL_RESULT":
                continue
            meta = getattr(event, "meta", None)
            if meta is None and isinstance(event, dict):
                meta = event.get("meta")
            if not isinstance(meta, dict):
                meta = {}
            tool_name = meta.get("tool_name") or meta.get("name") or "tool"
            if tool_name in latest:
                latest.pop(tool_name, None)
            latest[tool_name] = event

        lines: list[str] = []
        for tool_name, event in latest.items():
            content = getattr(event, "content", None)
            if content is None and isinstance(event, dict):
                content = event.get("content")
            if not content:
                continue
            lines.append(f"[TOOL {tool_name}]\n{content}")
            meta = getattr(event, "meta", None)
            if meta is None and isinstance(event, dict):
                meta = event.get("meta")
            if isinstance(meta, dict):
                refs = meta.get("sources") or meta.get("artifacts")
                if refs:
                    lines.append(f"<refs>\n{refs}\n</refs>")

        return "\n\n".join(lines).strip()
