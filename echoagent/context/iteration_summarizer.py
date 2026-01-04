from __future__ import annotations

import json
from typing import Any, Optional

from agents import Agent, Runner, RunConfig
from pydantic import BaseModel

from echoagent.context.state import BaseIterationRecord, IterationDigest
from echoagent.observability.runlog.utils import truncate_text
from echoagent.utils.helpers import extract_final_output, serialize_content


_ITERATION_DIGEST_SYSTEM_PROMPT = """
你是一个迭代摘要器。你需要基于本轮迭代数据生成结构化摘要。

硬性规则：
1) 只能使用提供的数据，不可臆测
2) 只输出 JSON
3) JSON 必须包含且仅包含字段：summary, facts, decisions, open_questions, action_items
4) summary 必须是非空字符串
""".strip()


class IterationSummarizer:
    """同步生成单轮 IterationDigest，失败不抛异常。"""

    def __init__(
        self,
        llm: str,
        provider: str | None = None,
        model_override: str | None = None,
    ) -> None:
        self._llm = llm
        self._provider = provider
        self._model_override = model_override

    def summarize_sync(
        self,
        context: Any,
        record: BaseIterationRecord,
        *,
        query: Optional[Any] = None,
        max_tool_chars: int = 2000,
    ) -> IterationDigest:
        try:
            digest = self._summarize_via_model(context, record, query=query, max_tool_chars=max_tool_chars)
            if digest is not None and digest.summary:
                return digest
        except Exception:
            pass
        return self._fallback_digest(record)

    def _summarize_via_model(
        self,
        context: Any,
        record: BaseIterationRecord,
        *,
        query: Optional[Any],
        max_tool_chars: int,
    ) -> Optional[IterationDigest]:
        model_name = self._model_override or self._llm
        if not model_name:
            return None
        prompt = _build_prompt(context, record, query=query, max_tool_chars=max_tool_chars)
        agent = Agent(
            name="iteration_summarizer",
            instructions=_ITERATION_DIGEST_SYSTEM_PROMPT,
            model=model_name,
        )
        run_config = RunConfig(model=model_name, tracing_disabled=True)
        result = Runner.run_sync(agent, prompt, context=None, run_config=run_config)
        output = extract_final_output(result)
        return _parse_digest(output)

    def _fallback_digest(self, record: BaseIterationRecord) -> IterationDigest:
        summary = "Iteration completed; output recorded."
        if record.status != "complete":
            summary = "Iteration failed; output recorded."
        elif record.tools:
            summary = "Iteration completed with tool calls; results recorded."
        if record.observation:
            summary = truncate_text(record.observation, 240)
        if not summary:
            summary = "Iteration completed; output recorded."
        return IterationDigest(summary=summary)


def _build_prompt(
    context: Any,
    record: BaseIterationRecord,
    *,
    query: Optional[Any],
    max_tool_chars: int,
) -> str:
    observation = record.observation or ""
    tool_outputs = []
    for tool in record.tools:
        output = getattr(tool, "output", None)
        if output is None:
            continue
        tool_outputs.append(str(output))
    tools_text = "\n".join(tool_outputs)
    tools_text = truncate_text(tools_text, max_tool_chars)

    payload_texts: list[str] = []
    for payload in record.payloads:
        payload_texts.append(serialize_content(payload))
    payload_text = truncate_text("\n".join(payload_texts), 2000)

    query_text = serialize_content(query) if query is not None else ""

    return "\n".join(
        [
            "[ITERATION]",
            f"index: {record.index}",
            f"status: {record.status}",
            "",
            "[QUERY]",
            query_text,
            "",
            "[OBSERVATION]",
            observation,
            "",
            "[TOOL_OUTPUTS]",
            tools_text,
            "",
            "[PAYLOADS]",
            payload_text,
        ]
    ).strip()


def _parse_digest(output: Any) -> Optional[IterationDigest]:
    if isinstance(output, IterationDigest):
        return output
    if isinstance(output, BaseModel):
        try:
            return IterationDigest.model_validate(output.model_dump())
        except Exception:
            return None
    if isinstance(output, dict):
        try:
            return IterationDigest.model_validate(output)
        except Exception:
            return None
    if isinstance(output, (str, bytes, bytearray)):
        text = output.decode("utf-8", errors="ignore") if isinstance(output, (bytes, bytearray)) else str(output)
        text = text.strip()
        if not text:
            return None
        parsed = _try_parse_json(text)
        if parsed is not None:
            try:
                return IterationDigest.model_validate(parsed)
            except Exception:
                return None
    return None


def _try_parse_json(text: str) -> Optional[dict[str, Any]]:
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    snippet = text[start : end + 1]
    try:
        return json.loads(snippet)
    except Exception:
        return None
