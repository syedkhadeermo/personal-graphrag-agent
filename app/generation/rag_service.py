from app.embeddings.ollama_embeddings import OllamaEmbeddingService
from app.retrieval.retrieval_service import RetrievalService
from app.generation.ollama_generator import OllamaGenerator


class RAGService:
    """End-to-end retrieval-augmented generation service."""

    def __init__(self):
        self.embedding_service = OllamaEmbeddingService()
        self.retrieval_service = RetrievalService()
        self.generator = OllamaGenerator()

    def answer(
        self,
        question: str,
        n_results: int = 3,
        domain: str | None = None,
    ) -> dict:
        """Retrieve knowledge, generate an answer, and return evidence."""

        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")

        results = self.retrieval_service.search(
            question,
            n_results=n_results,
            domain=domain,
        )

        if not results:
            return {
                "question": question,
                "answer": "No relevant information was found in the knowledge base.",
                "domain": domain,
                "retrieved_chunks": [],
                "sources": [],
            }

        context_parts = []

        for result in results:
            metadata = result["metadata"]

            context_parts.append(
                f"Source: {metadata.get('source', 'unknown')}\n"
                f"Domain: {metadata.get('domain', 'unknown')}\n"
                f"Chunk ID: {metadata.get('chunk_id', 'unknown')}\n"
                f"Content:\n{result['text']}"
            )

        context = "\n\n---\n\n".join(context_parts)

        answer = self.generator.generate(
            question=question,
            context=context,
        )

        retrieved_chunks = []

        for result in results:
            retrieved_chunks.append(
                {
                    "text": result["text"],
                    "metadata": result["metadata"],
                    "distance": result["distance"],
                }
            )

        sources = []

        for result in results:
            metadata = result["metadata"]

            sources.append(
                {
                    "source": metadata.get("source"),
                    "file_name": metadata.get("file_name"),
                    "domain": metadata.get("domain"),
                    "chunk_id": metadata.get("chunk_id"),
                    "distance": result["distance"],
                }
            )

        return {
            "question": question,
            "answer": answer,
            "domain": domain,
            "retrieved_chunks": retrieved_chunks,
            "sources": sources,
        }