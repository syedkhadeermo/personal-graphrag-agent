import pytest

from app.generation.cloud_generators import (
    AnthropicGenerator,
    GeminiGenerator,
    OpenAIGenerator,
    ProviderRequestError,
)
from app.generation.ollama_generator import OllamaGenerator
from app.generation.provider_factory import create_generation_provider


class RecordingTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, url, headers, payload, timeout):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return self.response


def test_factory_defaults_to_local_ollama() -> None:
    generator = create_generation_provider(environ={})

    assert isinstance(generator, OllamaGenerator)
    assert generator.model == "deepseek-coder:6.7b"


@pytest.mark.parametrize(
    ("alias", "key_name", "model_name", "expected_type"),
    [
        ("openai", "OPENAI_API_KEY", "OPENAI_MODEL", OpenAIGenerator),
        ("claude", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", AnthropicGenerator),
        ("google", "GEMINI_API_KEY", "GEMINI_MODEL", GeminiGenerator),
    ],
)
def test_factory_supports_cloud_providers(
    alias, key_name, model_name, expected_type
) -> None:
    generator = create_generation_provider(
        provider=alias,
        environ={key_name: "secret", model_name: "test-model"},
    )

    assert isinstance(generator, expected_type)
    assert generator.model == "test-model"


def test_factory_requires_cloud_credentials_without_exposing_values() -> None:
    with pytest.raises(ValueError, match="OPENAI_API_KEY") as exc_info:
        create_generation_provider(
            provider="openai",
            environ={"OPENAI_MODEL": "test-model"},
        )

    assert "secret" not in str(exc_info.value)


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported generation provider"):
        create_generation_provider(provider="unknown", environ={})


def test_openai_responses_contract_and_parsing() -> None:
    transport = RecordingTransport(
        {"output": [{"content": [{"type": "output_text", "text": "Answer"}]}]}
    )
    generator = OpenAIGenerator(
        api_key="openai-secret",
        model="openai-test",
        transport=transport,
    )

    answer = generator.chat(
        [
            {"role": "system", "content": "Use evidence."},
            {"role": "user", "content": "Question"},
        ],
        max_tokens=220,
    )

    call = transport.calls[0]
    assert answer == "Answer"
    assert call["headers"]["Authorization"] == "Bearer openai-secret"
    assert call["payload"] == {
        "model": "openai-test",
        "input": [{"role": "user", "content": "Question"}],
        "instructions": "Use evidence.",
        "temperature": 0.0,
        "max_output_tokens": 220,
    }


def test_anthropic_messages_contract_and_parsing() -> None:
    transport = RecordingTransport(
        {"content": [{"type": "text", "text": "Claude answer"}]}
    )
    generator = AnthropicGenerator(
        api_key="anthropic-secret",
        model="claude-test",
        transport=transport,
    )

    answer = generator.chat(
        [
            {"role": "system", "content": "Use evidence."},
            {"role": "user", "content": "Question"},
        ],
        max_tokens=220,
    )

    call = transport.calls[0]
    assert answer == "Claude answer"
    assert call["headers"] == {
        "x-api-key": "anthropic-secret",
        "anthropic-version": "2023-06-01",
    }
    assert call["payload"]["system"] == "Use evidence."
    assert call["payload"]["messages"] == [
        {"role": "user", "content": "Question"}
    ]
    assert call["payload"]["max_tokens"] == 220


def test_gemini_generate_content_contract_and_parsing() -> None:
    transport = RecordingTransport(
        {
            "candidates": [
                {"content": {"parts": [{"text": "Gemini answer"}]}}
            ]
        }
    )
    generator = GeminiGenerator(
        api_key="gemini-secret",
        model="gemini-test",
        transport=transport,
    )

    answer = generator.chat(
        [
            {"role": "system", "content": "Use evidence."},
            {"role": "user", "content": "Question"},
        ],
        max_tokens=220,
    )

    call = transport.calls[0]
    assert answer == "Gemini answer"
    assert call["url"].endswith("/gemini-test:generateContent")
    assert call["headers"] == {"x-goog-api-key": "gemini-secret"}
    assert call["payload"]["systemInstruction"] == {
        "parts": [{"text": "Use evidence."}]
    }
    assert call["payload"]["contents"] == [
        {"role": "user", "parts": [{"text": "Question"}]}
    ]
    assert call["payload"]["generationConfig"]["maxOutputTokens"] == 220


@pytest.mark.parametrize(
    ("generator_type", "response", "provider_name"),
    [
        (OpenAIGenerator, {"output": []}, "OpenAI"),
        (AnthropicGenerator, {"content": []}, "Anthropic"),
        (GeminiGenerator, {"candidates": []}, "Gemini"),
    ],
)
def test_empty_provider_output_has_clear_error(
    generator_type, response, provider_name
) -> None:
    generator = generator_type(
        api_key="do-not-leak",
        model="test-model",
        transport=RecordingTransport(response),
    )

    with pytest.raises(ProviderRequestError, match=provider_name) as exc_info:
        generator.chat([{"role": "user", "content": "Question"}])

    assert "do-not-leak" not in str(exc_info.value)


def test_generate_uses_shared_grounded_prompt() -> None:
    transport = RecordingTransport(
        {"content": [{"type": "text", "text": "Grounded answer"}]}
    )
    generator = AnthropicGenerator(
        api_key="secret",
        model="test-model",
        transport=transport,
    )

    assert generator.generate("What?", "Evidence.") == "Grounded answer"
    prompt = transport.calls[0]["payload"]["messages"][0]["content"]
    assert "Evidence." in prompt
    assert "What?" in prompt
    assert "Do NOT use your pretrained knowledge" in prompt
