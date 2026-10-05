from app.retrieval.retrieval_service import RetrievalService


class FakeEmbeddingService:
    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0]


class FakeVectorStore:
    def search(self, **kwargs) -> dict:
        return {
            "ids": [["source-1:chunk-7"]],
            "documents": [["Exact retrieved evidence."]],
            "metadatas": [[{"source_id": "source-1", "chunk_number": 7}]],
            "distances": [[0.12]],
        }


def test_retrieval_result_preserves_vector_store_identity() -> None:
    service = RetrievalService(
        embedding_service=FakeEmbeddingService(),
        vector_store=FakeVectorStore(),
    )

    assert service.search("question") == [
        {
            "id": "source-1:chunk-7",
            "text": "Exact retrieved evidence.",
            "metadata": {"source_id": "source-1", "chunk_number": 7},
            "distance": 0.12,
        }
    ]
