from typing import Dict, Any, Optional

from agents import ModelSettings

from echoagent.llm import get_provider, resolve_model_capabilities


class LLMConfig:
    """基于 .env 的 OpenAI 协议配置。"""

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
        if self.provider not in ("openai", "openai_compatible"):
            raise ValueError(f"Unsupported provider: {self.provider}")

        # Create main model (used for all purposes - reasoning, main, fast)
        self.main_model, self.reasoning_model, self.fast_model = self._create_models()

        # Model settings from config or defaults
        model_settings_config = self.config.get("model_settings", {})
        self.default_model_settings = ModelSettings(
            temperature=model_settings_config.get("temperature", 0.1)
        )

        if self.provider == "openai" and self.api_key:
            from agents import set_tracing_export_api_key
            set_tracing_export_api_key(self.api_key)

    def _get_default_model(self) -> str:
        """Get default model for provider."""
        return "gpt-4.1"

    def _create_models(self):
        """Create model instances using provider plugin."""
        provider = get_provider(self.provider)
        return provider.create_models(self.config)

def model_supports_json_and_tool_calls(model_spec: Any) -> bool:
    """Utility function to check if a model supports structured output."""
    try:
        capabilities = resolve_model_capabilities(model_spec)
    except Exception:
        return False
    return capabilities.supports_structured_output()
