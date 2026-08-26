from ollama import Client

from app.generation.provider import grounded_prompt


class OllamaGenerator:
    """Generate strictly context-grounded answers using Ollama."""

    def __init__(
        self,
        model: str = "deepseek-coder:6.7b",
        host: str = "http://localhost:11434",
    ):
        self.model = model
        self.client = Client(host=host)

    def generate(self, question: str, context: str) -> str:
        """Generate an answer using only the supplied context."""
        return self.chat(
            [{"role": "user", "content": grounded_prompt(question, context)}]
        )

    def chat(
        self,
        messages,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        options = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        response = self.client.chat(
            model=self.model,
            messages=list(messages),
            options=options,
        )
        return response["message"]["content"].strip()
