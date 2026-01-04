"""
Output parsing utilities for JSON and structured data extraction.
"""

import json
from typing import Any, Callable, List, Optional

from pydantic import BaseModel


class OutputParserError(Exception):
    """
    Exception raised when the output parser fails to parse the output.
    """
    def __init__(self, message, output=None):
        self.message = message
        self.output = output
        super().__init__(self.message)

    def __str__(self):
        if self.output:
            return f"{self.message}\nProblematic output: {self.output}"
        return self.message


def _escape_unescaped_quotes(json_text: str) -> str:
    """Escape bare double quotes that appear inside JSON string values."""
    result: List[str] = []
    in_string = False
    escape_next = False
    for index, char in enumerate(json_text):
        if escape_next:
            result.append(char)
            escape_next = False
            continue
        if char == '\\':
            result.append(char)
            escape_next = True
            continue
        if char == '"':
            if in_string:
                lookahead = index + 1
                while lookahead < len(json_text) and json_text[lookahead] in " \t\r\n":
                    lookahead += 1
                if lookahead < len(json_text) and json_text[lookahead] not in ",:}]":
                    result.append('\\"')
                else:
                    result.append('"')
                    in_string = False
            else:
                in_string = True
                result.append('"')
        else:
            result.append(char)
    return "".join(result)


def find_json_in_string(string: str) -> str:
    """
    Method to extract all text in the left-most brace that appears in a string.
    Used to extract JSON from a string (note that this function does not validate the JSON).

    Example:
        string = "bla bla bla {this is {some} text{{}and it's sneaky}} because {it's} confusing"
        output = "{this is {some} text{{}and it's sneaky}}"
    """
    stack = 0
    start_index = None

    for i, c in enumerate(string):
        if c == '{':
            if stack == 0:
                start_index = i  # Start index of the first '{'
            stack += 1  # Push to stack
        elif c == '}':
            stack -= 1  # Pop stack
            if stack == 0:
                # Return the substring from the start of the first '{' to the current '}'
                return string[start_index:i + 1] if start_index is not None else ""

    # If no complete set of braces is found, return an empty string
    return ""


def parse_json_output(output: str) -> Any:
    """Take a string output and parse it as JSON"""
    # First try to load the string as JSON
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        pass

    # If that fails, try to extract from code block if it exists
    if "```" in output:
        parts = output.split("```")
        if len(parts) >= 3:
            # Standard code block: text before ``` | json\n | json content | ```
            parsed_output = parts[1]
            # Handle language specifier (e.g., "json" or "json\n")
            if parsed_output.startswith("json") or parsed_output.startswith("JSON"):
                parsed_output = parsed_output[4:].lstrip()
            else:
                parsed_output = parsed_output.lstrip()
            parsed = _try_decode_json(parsed_output)
            if parsed is not None:
                return parsed
            try:
                return json.loads(_escape_unescaped_quotes(parsed_output))
            except json.JSONDecodeError:
                pass
        elif len(parts) == 2:
            # Edge case: only one code block marker pair
            parsed_output = parts[1].strip()
            if parsed_output.startswith("json") or parsed_output.startswith("JSON"):
                parsed_output = parsed_output[4:].lstrip()
            parsed = _try_decode_json(parsed_output)
            if parsed is not None:
                return parsed
            try:
                return json.loads(_escape_unescaped_quotes(parsed_output))
            except json.JSONDecodeError:
                pass

    # As a last attempt, try to manually find the JSON object in the output and parse it
    parsed = _try_decode_json(output)
    if parsed is not None:
        return parsed
    parsed_output = find_json_in_string(output)
    if parsed_output:
        parsed = _try_decode_json(parsed_output)
        if parsed is not None:
            return parsed

    # If all fails, raise an error
    raise OutputParserError("Failed to parse output as JSON", output)


def create_type_parser(type: BaseModel) -> Callable[[str], BaseModel]:
    """Create a function that takes a string output and parses it as a specified Pydantic model"""

    def convert_json_string_to_type(output: str) -> BaseModel:
        """Take a string output and parse it as a Pydantic model"""
        try:
            output_dict = parse_json_output(output)
        except OutputParserError:
            fallback = _coerce_output_payload(output, type)
            if fallback is None:
                raise
            return type.model_validate(fallback)
        if not isinstance(output_dict, dict):
            fallback = _coerce_output_payload(output_dict, type)
            if fallback is not None:
                return type.model_validate(fallback)
        return type.model_validate(output_dict)

    return convert_json_string_to_type


def _coerce_output_payload(value: Any, model_class: type[BaseModel]) -> Optional[dict[str, Any]]:
    fields = getattr(model_class, "model_fields", None)
    if not isinstance(fields, dict):
        return None
    if "output" not in fields:
        return None
    if isinstance(value, (dict, list)):
        output_text = json.dumps(value, ensure_ascii=False)
    else:
        output_text = str(value)
    payload: dict[str, Any] = {"output": output_text}
    if "sources" in fields:
        payload["sources"] = []
    return payload


def _try_decode_json(text: str) -> Optional[Any]:
    if not text:
        return None
    decoder = json.JSONDecoder()
    cleaned = text.strip()
    try:
        return decoder.raw_decode(cleaned)[0]
    except json.JSONDecodeError:
        pass
    for start in (cleaned.find("{"), cleaned.find("[")):
        if start == -1:
            continue
        try:
            return decoder.raw_decode(cleaned[start:])[0]
        except json.JSONDecodeError:
            continue
    return None
