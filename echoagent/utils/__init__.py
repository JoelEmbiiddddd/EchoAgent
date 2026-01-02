"""
Utility helpers for the multi-agent data science system.

This package provides utilities for:
- Configuration management (config.py)
- Logging setup (logging.py)
- Rich terminal output (printer.py)
- JSON/output parsing (parsers.py)
- Miscellaneous helpers (helpers.py)
"""

# Configuration utilities
from echoagent.utils.config import (
    load_json_config,
    save_json_config,
    merge_configs,
    get_env_with_prefix,
    load_config,
    get_agent_instructions,
    get_pipeline_settings,
    BaseConfig,
    load_mapping_from_path,
    get_api_key_from_env,
    resolve_config,
    load_pipeline_config,
    normalize_agents,
    get_agent_spec,
)

# Printer utilities
from echoagent.utils.printer import Printer

# Parser utilities
from echoagent.utils.parsers import (
    OutputParserError,
    parse_json_output,
    find_json_in_string,
    create_type_parser,
)

# Helper utilities
from echoagent.utils.helpers import (
    get_experiment_timestamp,
    extract_final_output,
    serialize_content,
    parse_to_model,
)

# LLM utilities
from echoagent.utils.llm_setup import (
    LLMConfig,
    model_supports_json_and_tool_calls,
)

__all__ = [
    # Config
    "load_json_config",
    "save_json_config",
    "merge_configs",
    "get_env_with_prefix",
    "load_config",
    "get_agent_instructions",
    "get_pipeline_settings",
    "BaseConfig",
    "load_mapping_from_path",
    "get_api_key_from_env",
    "resolve_config",
    "load_pipeline_config",
    "normalize_agents",
    "get_agent_spec",
    # Printer
    "Printer",
    # Parsers
    "OutputParserError",
    "parse_json_output",
    "find_json_in_string",
    "create_type_parser",
    # Helpers
    "get_experiment_timestamp",
    "extract_final_output",
    "serialize_content",
    "parse_to_model",
    # LLM
    "LLMConfig",
    "model_supports_json_and_tool_calls",
]
