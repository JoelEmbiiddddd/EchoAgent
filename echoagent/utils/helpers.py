"""
Miscellaneous helper utilities.
"""

import datetime
import json
from typing import Any, Optional

from pydantic import BaseModel


def get_experiment_timestamp() -> str:
    """Get timestamp for experiment naming."""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def extract_final_output(result: Any) -> Any:
    """Extract final output from agent execution results.

    Handles various result types by checking for final_output attribute.

    Args:
        result: Agent execution result (may have final_output attribute)

    Returns:
        The final output if available, otherwise the result itself
    """
    return getattr(result, "final_output", result)


def serialize_content(value: Any) -> str:
    """Convert any value to a string representation suitable for display.

    Handles various types including BaseModel, dict, and primitives.

    Args:
        value: The value to serialize

    Returns:
        String representation of the value
    """
    if hasattr(value, 'output'):
        return str(value.output)
    elif isinstance(value, BaseModel):
        return value.model_dump_json(indent=2)
    elif isinstance(value, dict):
        return json.dumps(value, indent=2)
    else:
        return str(value)


def parse_to_model(
    raw_output: Any,
    model_class: type[BaseModel],
    span: Optional[Any] = None
) -> BaseModel:
    """Parse raw output into a specified pydantic model.

    Handles various input types: BaseModel, dict, list, str, bytes.
    Optionally sets the output on a tracing span.

    Args:
        raw_output: The raw output to parse
        model_class: The pydantic model class to parse into
        span: Optional tracing span to set output on

    Returns:
        Parsed model instance
    """
    if isinstance(raw_output, model_class):
        output = raw_output
    elif isinstance(raw_output, BaseModel):
        output = model_class.model_validate(raw_output.model_dump())
    elif isinstance(raw_output, (dict, list)):
        output = model_class.model_validate(raw_output)
    elif isinstance(raw_output, (str, bytes, bytearray)):
        text = _normalize_text(raw_output)
        try:
            output = model_class.model_validate_json(text)
        except Exception:
            parsed = _try_parse_json(text)
            if parsed is None:
                fallback = _coerce_output_model(text, model_class)
                if fallback is None:
                    raise
                output = model_class.model_validate(fallback)
            else:
                try:
                    output = model_class.model_validate(parsed)
                except Exception:
                    fallback = _coerce_output_model(parsed, model_class)
                    if fallback is None:
                        raise
                    output = model_class.model_validate(fallback)
    else:
        output = model_class.model_validate(raw_output)

    if span and hasattr(span, "set_output"):
        span.set_output(output.model_dump())

    return output


def _normalize_text(raw_output: Any) -> str:
    if isinstance(raw_output, (bytes, bytearray)):
        return raw_output.decode("utf-8", errors="ignore")
    return str(raw_output)


def _try_parse_json(text: str) -> Optional[Any]:
    if not text:
        return None
    decoder = json.JSONDecoder()
    stripped = text.strip()
    try:
        return decoder.raw_decode(stripped)[0]
    except Exception:
        pass
    candidates = [stripped.find("{"), stripped.find("[")]
    for start in candidates:
        if start == -1:
            continue
        try:
            return decoder.raw_decode(stripped[start:])[0]
        except Exception:
            continue
    return None


def _coerce_output_model(value: Any, model_class: type[BaseModel]) -> Optional[dict[str, Any]]:
    fields = getattr(model_class, "model_fields", None)
    if not isinstance(fields, dict):
        return None
    if "output" not in fields:
        return None
    payload: dict[str, Any] = {"output": _normalize_text(value)}
    if "sources" in fields:
        payload["sources"] = []
    return payload
