import time
from typing import Any

from app.embeddings.ollama_embeddings import OllamaEmbeddingService
from app.vectorstore.chroma_store import ChromaVectorStore


class KnowledgeIndexer:
    """
    Index knowledge chunks into the existing Chroma vector store.

    Optimizations:
        - batch embedding
        - batch Chroma insertion
        - metadata preservation
        - progress reporting
        - timing statistics
    """

    def __init__(
        self,
        embedding_service: OllamaEmbeddingService | None = None,
        vector_store: ChromaVectorStore | None = None,
        batch_size: int = 16,
    ):
        if batch_size <= 0:
            raise ValueError(
                "batch_size must be greater than zero."
            )

        self.embedding_service = (
            embedding_service
            or OllamaEmbeddingService()
        )

        self.vector_store = (
            vector_store
            or ChromaVectorStore()
        )

        self.batch_size = batch_size

    # =========================================================
    # Index chunks
    # =========================================================

    def index_chunks(
        self,
        chunks: list[dict[str, Any]],
    ) -> dict[str, Any]:

        if not chunks:
            raise ValueError(
                "No knowledge chunks supplied."
            )

        start_time = time.perf_counter()

        total = len(chunks)

        indexed = 0
        batches = 0

        for start in range(
            0,
            total,
            self.batch_size,
        ):

            end = min(
                start + self.batch_size,
                total,
            )

            batch = chunks[start:end]

            texts = [
                item["text"]
                for item in batch
            ]

            ids = [
                item["chunk_id"]
                for item in batch
            ]

            metadatas = []

            for item in batch:

                metadata = {
                    "source": (
                        item.get("source")
                        or ""
                    ),
                    "domain": (
                        item.get("domain")
                        or ""
                    ),
                    "page": int(
                        item.get("page")
                        or 0
                    ),
                    "chunk_index": int(
                        item.get("chunk_index")
                        or 0
                    ),
                    "character_count": int(
                        item.get(
                            "character_count"
                        )
                        or 0
                    ),
                }

                metadatas.append(
                    metadata
                )

            # ---------------------------------------------
            # Batch embedding
            # ---------------------------------------------

            embedding_start = (
                time.perf_counter()
            )

            embeddings = (
                self.embedding_service
                .embed_batch(texts)
            )

            embedding_seconds = round(
                time.perf_counter()
                - embedding_start,
                3,
            )

            if len(embeddings) != len(batch):
                raise RuntimeError(
                    "Embedding count does not match "
                    "chunk count."
                )

            # ---------------------------------------------
            # Batch vector-store write
            # ---------------------------------------------

            self.vector_store.add_documents(
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
            )

            indexed += len(batch)
            batches += 1

            print(
                f"[KnowledgeIndexer] "
                f"{indexed}/{total} chunks indexed "
                f"(batch={batches}, "
                f"embedding={embedding_seconds}s)"
            )

        total_seconds = round(
            time.perf_counter()
            - start_time,
            3,
        )

        chunks_per_second = round(
            total / total_seconds,
            3,
        ) if total_seconds > 0 else 0.0

        return {
            "status": "completed",
            "chunks_indexed": indexed,
            "batches": batches,
            "batch_size": self.batch_size,
            "duration_seconds": total_seconds,
            "chunks_per_second": chunks_per_second,
            "vector_count": (
                self.vector_store.count()
            ),
        }