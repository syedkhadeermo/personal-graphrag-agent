import os
from collections.abc import Mapping

from app.generation.cloud_generators import (
    AnthropicGenerator,
    GeminiGenerator,
    OpenAIGenerator,
)
from app.generation.ollama_generator import OllamaGenerator
from app.generation.provider import GenerationProvider


def create_generation_provider(
    provider: str | None = None,
    model: str | None = None,
    host: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> GenerationProvider:
    """Create a generator from explicit arguments or environment settings."""

    env = environ if environ is not None else os.environ
    selected = (provider or env.get("GENERATION_PROVIDER", "ollama")).lower().strip()
    selected = {"claude": "anthropic", "google": "gemini"}.get(selected, selected)
    shared_model = model or env.get("GENERATION_MODEL")

    if selected == "ollama":
        return OllamaGenerator(
            model=shared_model or env.get("OLLAMA_GENERATION_MODEL", "deepseek-coder:6.7b"),
            host=host or env.get("OLLAMA_HOST", "http://localhost:11434"),
        )

    settings = {
        "openai": (OpenAIGenerator, "OPENAI_API_KEY", "OPENAI_MODEL"),
        "anthropic": (AnthropicGenerator, "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"),
        "gemini": (GeminiGenerator, "GEMINI_API_KEY", "GEMINI_MODEL"),
    }
    if selected not in settings:
        supported = ", ".join(["ollama", *settings])
        raise ValueError(f"Unsupported generation provider '{selected}'. Use: {supported}.")

    generator_type, key_name, model_name = settings[selected]
    api_key = env.get(key_name, "")
    selected_model = shared_model or env.get(model_name, "")
    if not api_key:
        raise ValueError(f"{key_name} is required for the {selected} provider.")
    if not selected_model:
        raise ValueError(
            f"GENERATION_MODEL or {model_name} is required for the {selected} provider."
        )
    return generator_type(api_key=api_key, model=selected_model)
