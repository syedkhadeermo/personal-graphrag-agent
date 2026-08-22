from app.embeddings.ollama_embeddings import OllamaEmbeddingService


def test_embedding_generation():
    service = OllamaEmbeddingService()

    vector = service.embed(
        "This is a test document for my personal knowledge graph."
    )

    assert isinstance(vector, list)
    assert len(vector) == 768
    assert all(isinstance(value, float) for value in vector)


def test_empty_text_rejected():
    service = OllamaEmbeddingService()

    try:
        service.embed("")
        assert False, "Expected ValueError"
    except ValueError:
        pass