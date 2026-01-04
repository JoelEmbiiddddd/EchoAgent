from __future__ import annotations

import json

from echoagent.profiles.base import ToolAgentOutput
from echoagent.utils.parsers import create_type_parser


def test_convert_json_string_to_type_allows_preface() -> None:
    parser = create_type_parser(ToolAgentOutput)

    raw = "<think>preface</think>\n{\"output\": \"ok\", \"sources\": []}\n"
    parsed = parser(raw)

    assert isinstance(parsed, ToolAgentOutput)
    assert parsed.output == "ok"
    assert parsed.sources == []


def test_convert_json_string_to_type_allows_list() -> None:
    parser = create_type_parser(ToolAgentOutput)

    raw = "noise\n[1]\n"
    parsed = parser(raw)

    assert isinstance(parsed, ToolAgentOutput)
    assert parsed.output == json.dumps([1], ensure_ascii=False)
