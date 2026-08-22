from ollama import Client


class OllamaEmbeddingService:
    """Generate text embeddings using a local Ollama model."""

    def __init__(
        self,
        model: str = "nomic-embed-text:latest",
        host: str = "http://localhost:11434",
    ):
        self.model = model
        self.client = Client(host=host)

    def embed(self, text: str) -> list[float]:
        """Generate an embedding for a single piece of text."""

        if not text or not text.strip():
            raise ValueError("Text cannot be empty.")

        response = self.client.embed(
            model=self.model,
            input=text,
        )

        return response["embeddings"][0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in one request."""

        if not texts:
            raise ValueError("Texts cannot be empty.")

        if any(not text or not text.strip() for text in texts):
            raise ValueError("Texts cannot contain empty values.")

        response = self.client.embed(
            model=self.model,
            input=texts,
        )

        return response["embeddings"]

    def dimension(self) -> int:
        """Return the embedding dimension."""

        vector = self.embed("dimension test")
        return len(vector)