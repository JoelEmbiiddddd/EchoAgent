from __future__ import annotations

from typing import Any, Iterable, Optional

from pydantic import BaseModel

from echoagent.context.state import BaseIterationRecord


def _render_payload(payload: Any) -> str:
    if isinstance(payload, BaseModel):
        return payload.model_dump_json(indent=2)
    return str(payload)


def render_iteration_block(iteration: BaseIterationRecord) -> str:
    lines: list[str] = [f"[ITERATION {iteration.index}]"]

    if iteration.observation:
        lines.append(f"<thought>\n{iteration.observation}\n</thought>")

    if iteration.payloads:
        payload_lines = [_render_payload(payload) for payload in iteration.payloads]
        if payload_lines:
            lines.append(f"<payloads>\n{chr(10).join(payload_lines)}\n</payloads>")

    if iteration.tools:
        tool_lines = [tool.output for tool in iteration.tools]
        lines.append(f"<findings>\n{chr(10).join(tool_lines)}\n</findings>")

    return "\n\n".join(lines).strip()


def render_iteration_history(
    iterations: Iterable[BaseIterationRecord],
    *,
    include_current: bool,
    only_unsummarized: bool = False,
    current_iteration: Optional[BaseIterationRecord] = None,
) -> str:
    blocks: list[str] = []
    for iteration in iterations:
        is_current = current_iteration is not None and iteration is current_iteration
        if iteration.is_complete() or (include_current and is_current):
            if only_unsummarized and iteration.summarized:
                continue
            block = render_iteration_block(iteration)
            if block:
                blocks.append(block)
    return "\n\n".join(blocks).strip()


def render_context_prompt(state: Any, *, current_input: Optional[str] = None) -> str:
    sections: list[str] = []

    query = getattr(state, "query", None)
    if query:
        sections.append(f"[ORIGINAL QUERY]\n{query}")

    iterations = getattr(state, "iterations", []) or []
    current_iteration = iterations[-1] if iterations else None
    history = render_iteration_history(
        iterations,
        include_current=False,
        current_iteration=current_iteration,
    )
    if history:
        sections.append(f"[PREVIOUS ITERATIONS]\n{history}")

    if current_input:
        sections.append(f"[CURRENT INPUT]\n{current_input}")

    return "\n\n".join(sections).strip()
