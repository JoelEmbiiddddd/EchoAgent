from typing import Dict, Any, Optional, Union

from agents import OpenAIChatCompletionsModel, OpenAIResponsesModel, ModelSettings
from openai import AsyncOpenAI

# OpenAI provider configuration
PROVIDER_CONFIGS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
    }
}


class LLMConfig:
    """OpenAI-only configuration using .env-derived values."""

    def __init__(self, config: Dict[str, Any], full_config: Optional[Dict[str, Any]] = None):
        """
        Initialize LLM configuration from direct config.

        Args:
            config: Dictionary containing:
                - provider: str ("openai")
                - api_key: str
                - model: str (optional, will use defaults)
                - base_url: str (required)
                - model_settings: dict (optional, for temperature etc.)
            full_config: Optional full configuration including agent prompts, pipeline settings
        """
        self.provider = config["provider"]
        self.api_key = config["api_key"]
        self.model_name = config.get("model", self._get_default_model())
        self.config = config
        self.full_config = full_config

        # Validate provider
        if self.provider != "openai":
            raise ValueError("Only OpenAI provider is supported.")

        # Create main model (used for all purposes - reasoning, main, fast)
        self.main_model = self._create_model()
        self.reasoning_model = self.main_model
        self.fast_model = self.main_model

        # Model settings from config or defaults
        model_settings_config = self.config.get("model_settings", {})
        self.default_model_settings = ModelSettings(
            temperature=model_settings_config.get("temperature", 0.1)
        )

        # 非 OpenAI 官方端点时禁用 tracing key，避免外部 trace 请求失败
        base_url = self.config.get("base_url", PROVIDER_CONFIGS["openai"]["base_url"])
        if self.provider == "openai" and self.api_key and _is_openai_base_url(base_url):
            from agents import set_tracing_export_api_key
            set_tracing_export_api_key(self.api_key)

    def _get_default_model(self) -> str:
        """Get default model for provider."""
        return "gpt-4.1"

    def _create_model(self):
        """Create model instance using direct configuration."""
        provider_config = PROVIDER_CONFIGS[self.provider]
        base_url = self.config.get("base_url", provider_config["base_url"])
        if not base_url:
            raise ValueError("OPENAI_URL/openai_url is required for OpenAI client initialization.")

        model_class = OpenAIResponsesModel if _is_openai_base_url(base_url) else OpenAIChatCompletionsModel

        client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=base_url,
        )
        return model_class(model=self.model_name, openai_client=client)

def get_base_url(model: Union[OpenAIChatCompletionsModel, OpenAIResponsesModel]) -> str:
    """Utility function to get the base URL for a given model"""
    return str(model._client._base_url)

def model_supports_json_and_tool_calls(
    model: Union[OpenAIChatCompletionsModel, OpenAIResponsesModel],
) -> bool:
    """Utility function to check if a model supports structured output"""
    structured_output_providers = ["openai.com"]
    return any(
        provider in get_base_url(model) for provider in structured_output_providers
    )


def _is_openai_base_url(base_url: Optional[str]) -> bool:
    if not base_url:
        return False
    return "openai.com" in base_url.lower()
