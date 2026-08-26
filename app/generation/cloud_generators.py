import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.generation.provider import ChatMessage, grounded_prompt

JsonTransport = Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]


class ProviderRequestError(RuntimeError):
    """Cloud generation request failed without exposing credentials."""


def _default_transport(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ProviderRequestError(
            f"Generation provider returned HTTP {exc.code}."
        ) from exc
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise ProviderRequestError("Generation provider request failed.") from exc


def _validate_messages(
    messages: Sequence[Mapping[str, str]],
) -> list[ChatMessage]:
    if not messages:
        raise ValueError("Messages cannot be empty.")
    validated: list[ChatMessage] = []
    for message in messages:
        role = message.get("role", "").strip()
        content = message.get("content", "").strip()
        if role not in {"system", "user", "assistant"} or not content:
            raise ValueError("Each message needs a valid role and non-empty content.")
        validated.append({"role": role, "content": content})
    return validated


class _CloudGenerator:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        transport: JsonTransport | None = None,
    ):
        if not api_key.strip():
            raise ValueError("API key cannot be empty.")
        if not model.strip():
            raise ValueError("Model cannot be empty.")
        if timeout <= 0:
            raise ValueError("Timeout must be greater than zero.")
        self._api_key = api_key
        self.model = model
        self.timeout = timeout
        self._transport = transport or _default_transport

    def generate(self, question: str, context: str) -> str:
        return self.chat([{"role": "user", "content": grounded_prompt(question, context)}])


class OpenAIGenerator(_CloudGenerator):
    """Generate text through the OpenAI Responses API."""

    endpoint = "https://api.openai.com/v1/responses"

    def chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        validated = _validate_messages(messages)
        instructions = "\n\n".join(
            item["content"] for item in validated if item["role"] == "system"
        )
        input_messages = [item for item in validated if item["role"] != "system"]
        payload: dict[str, Any] = {"model": self.model, "input": input_messages}
        if instructions:
            payload["instructions"] = instructions
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_output_tokens"] = max_tokens
        response = self._transport(
            self.endpoint,
            {"Authorization": f"Bearer {self._api_key}"},
            payload,
            self.timeout,
        )
        parts = [
            content.get("text", "")
            for item in response.get("output", [])
            for content in item.get("content", [])
            if content.get("type") == "output_text"
        ]
        answer = "".join(parts).strip()
        if not answer:
            raise ProviderRequestError("OpenAI returned no text output.")
        return answer


class AnthropicGenerator(_CloudGenerator):
    """Generate text through the Anthropic Messages API."""

    endpoint = "https://api.anthropic.com/v1/messages"

    def chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        validated = _validate_messages(messages)
        system = "\n\n".join(
            item["content"] for item in validated if item["role"] == "system"
        )
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [item for item in validated if item["role"] != "system"],
            "max_tokens": max_tokens or 1024,
            "temperature": temperature,
        }
        if system:
            payload["system"] = system
        response = self._transport(
            self.endpoint,
            {"x-api-key": self._api_key, "anthropic-version": "2023-06-01"},
            payload,
            self.timeout,
        )
        answer = "".join(
            item.get("text", "")
            for item in response.get("content", [])
            if item.get("type") == "text"
        ).strip()
        if not answer:
            raise ProviderRequestError("Anthropic returned no text output.")
        return answer


class GeminiGenerator(_CloudGenerator):
    """Generate text through the Gemini generateContent API."""

    endpoint_root = "https://generativelanguage.googleapis.com/v1beta/models"

    def chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        validated = _validate_messages(messages)
        system = "\n\n".join(
            item["content"] for item in validated if item["role"] == "system"
        )
        contents = [
            {
                "role": "model" if item["role"] == "assistant" else "user",
                "parts": [{"text": item["content"]}],
            }
            for item in validated
            if item["role"] != "system"
        ]
        config: dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None:
            config["maxOutputTokens"] = max_tokens
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": config,
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        response = self._transport(
            f"{self.endpoint_root}/{self.model}:generateContent",
            {"x-goog-api-key": self._api_key},
            payload,
            self.timeout,
        )
        candidates = response.get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        answer = "".join(item.get("text", "") for item in parts).strip()
        if not answer:
            raise ProviderRequestError("Gemini returned no text output.")
        return answer
