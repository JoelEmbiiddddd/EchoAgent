from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel

from echoagent.utils.helpers import parse_to_model, serialize_content


@dataclass
class ParseErrorInfo:
    message: str
    exception_type: str
    schema_name: Optional[str]
    raw: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "exception_type": self.exception_type,
            "schema_name": self.schema_name,
            "raw": serialize_content(self.raw),
        }


@dataclass
class ParsedOutput:
    ok: bool
    value: Any
    raw: Any
    error: Optional[str] = None
    model_name: Optional[str] = None
    error_detail: Optional[ParseErrorInfo] = None


class OutputHandler:
    """将模型原始输出解析为结构化结果。"""

    @staticmethod
    def _schema_name(schema: Optional[Any]) -> Optional[str]:
        if schema is None:
            return None
        if isinstance(schema, type):
            return schema.__name__
        return getattr(schema, "__name__", schema.__class__.__name__)

    def parse(self, raw_output: Any, *, schema: Optional[Any] = None, mode: str = "lenient") -> ParsedOutput:
        schema_name = self._schema_name(schema)
        if schema is None:
            return ParsedOutput(ok=True, value=raw_output, raw=raw_output, error=None, model_name=schema_name)

        try:
            if isinstance(schema, type) and issubclass(schema, BaseModel):
                value = parse_to_model(raw_output, schema)
            elif callable(schema):
                value = schema(raw_output)
            else:
                value = raw_output
            return ParsedOutput(ok=True, value=value, raw=raw_output, error=None, model_name=schema_name)
        except Exception as exc:  # noqa: BLE001 - preserve lenient behavior
            if mode == "strict":
                raise
            error_detail = self._build_error_detail(raw_output, schema_name, exc)
            return ParsedOutput(
                ok=False,
                value=raw_output,
                raw=raw_output,
                error=error_detail.message,
                model_name=schema_name,
                error_detail=error_detail,
            )

    @staticmethod
    def _build_error_detail(raw_output: Any, schema_name: Optional[str], exc: Exception) -> ParseErrorInfo:
        return ParseErrorInfo(
            message=str(exc),
            exception_type=exc.__class__.__name__,
            schema_name=schema_name,
            raw=raw_output,
        )
