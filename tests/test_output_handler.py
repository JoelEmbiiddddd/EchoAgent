from __future__ import annotations

import pytest
from pydantic import BaseModel

from echoagent.agent.output_handler import OutputHandler
from echoagent.profiles.base import ToolAgentOutput


class SampleSchema(BaseModel):
    a: int


def test_output_handler_schema_none() -> None:
    handler = OutputHandler()

    parsed = handler.parse("raw", schema=None)

    assert parsed.ok is True
    assert parsed.value == "raw"
    assert parsed.model_name is None


def test_output_handler_schema_success() -> None:
    handler = OutputHandler()

    parsed = handler.parse({"a": 1}, schema=SampleSchema)

    assert parsed.ok is True
    assert isinstance(parsed.value, SampleSchema)
    assert parsed.value.a == 1
    assert parsed.model_name == "SampleSchema"


def test_output_handler_lenient_failure() -> None:
    handler = OutputHandler()

    parsed = handler.parse("bad", schema=SampleSchema, mode="lenient")

    assert parsed.ok is False
    assert parsed.value == "bad"
    assert parsed.error
    assert parsed.model_name == "SampleSchema"
    assert parsed.error_detail is not None
    assert parsed.error_detail.schema_name == "SampleSchema"
    assert parsed.error_detail.message == parsed.error
    assert parsed.error_detail.raw == "bad"


def test_output_handler_strict_failure() -> None:
    handler = OutputHandler()

    with pytest.raises(Exception):
        handler.parse("bad", schema=SampleSchema, mode="strict")


def test_output_handler_strict_json_with_prefix() -> None:
    handler = OutputHandler()

    raw = "<think>preface</think>\n{\"a\": 3}\n"
    parsed = handler.parse(raw, schema=SampleSchema, mode="strict")

    assert parsed.ok is True
    assert parsed.value.a == 3


def test_output_handler_strict_tool_output_fallback() -> None:
    handler = OutputHandler()

    raw = "<think>preface</think>\n[1]\n"
    parsed = handler.parse(raw, schema=ToolAgentOutput, mode="strict")

    assert parsed.ok is True
    assert parsed.value.output == "[1]"
