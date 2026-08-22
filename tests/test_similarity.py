import math

from app.embeddings.ollama_embeddings import OllamaEmbeddingService


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot_product = sum(x * y for x, y in zip(a, b))
    magnitude_a = math.sqrt(sum(x * x for x in a))
    magnitude_b = math.sqrt(sum(x * x for x in b))

    return dot_product / (magnitude_a * magnitude_b)


def test_semantic_similarity():
    service = OllamaEmbeddingService()

    texts = [
        "I am studying computational drug discovery.",
        "Machine learning can help discover new medicines.",
        "The football match was played yesterday.",
    ]

    vectors = service.embed_batch(texts)

    similarity_related = cosine_similarity(vectors[0], vectors[1])
    similarity_unrelated = cosine_similarity(vectors[0], vectors[2])

    print(f"\nRelated similarity:   {similarity_related:.4f}")
    print(f"Unrelated similarity: {similarity_unrelated:.4f}")

    assert similarity_related > similarity_unrelated