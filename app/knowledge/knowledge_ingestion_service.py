import hashlib
import time

from pathlib import Path
from typing import Any

from app.embeddings.ollama_embeddings import (
    OllamaEmbeddingService,
)
from app.knowledge.chunker import KnowledgeChunker
from app.knowledge.document_loader import DocumentLoader
from app.vectorstore.chroma_store import ChromaVectorStore


class KnowledgeIngestionService:
    """
    Idempotently ingest one knowledge document into ChromaDB.

    Document identity is based on SHA-256 file content.

    Guarantees:
        - identical document bytes have one identity
        - completed duplicate ingestion performs no embedding
        - interrupted ingestion can resume missing chunks
        - changed document content receives a new identity
        - private/public visibility is preserved in metadata
        - existing scientific documents are never modified
    """

    def __init__(
        self,
        embedding_service: (
            OllamaEmbeddingService
            | None
        ) = None,
        vector_store: (
            ChromaVectorStore
            | None
        ) = None,
        chunker: KnowledgeChunker | None = None,
        batch_size: int = 32,
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
            or ChromaVectorStore(
                collection_name=(
                    "technical_knowledge"
                )
            )
        )

        self.chunker = (
            chunker
            or KnowledgeChunker(
                chunk_size=1200,
                overlap=200,
            )
        )

        self.batch_size = batch_size
        self.loader = DocumentLoader()

    @staticmethod
    def calculate_sha256(
        path: str | Path,
        block_size: int = 1024 * 1024,
    ) -> str:
        """
        Calculate a document SHA-256 without loading the
        complete file into memory.
        """

        file_path = Path(path)

        if not file_path.is_file():
            raise FileNotFoundError(
                f"Knowledge document not found: "
                f"{file_path}"
            )

        digest = hashlib.sha256()

        with file_path.open("rb") as handle:
            while True:
                block = handle.read(
                    block_size
                )

                if not block:
                    break

                digest.update(block)

        return digest.hexdigest()

    def ingest_file(
        self,
        path: str,
        domain: str,
        subdomain: str,
        tool: str | None = None,
        version: str | None = None,
        visibility: str = "private",
        document_type: str = "technical_document",
    ) -> dict[str, Any]:
        """
        Load, chunk, embed and register one document.

        Existing complete documents return duplicate=True.

        Existing incomplete documents resume by embedding only
        the missing chunks.
        """

        file_path = self._validate_inputs(
            path=path,
            domain=domain,
            subdomain=subdomain,
            visibility=visibility,
            document_type=document_type,
        )

        normalized_domain = domain.strip()
        normalized_subdomain = (
            subdomain.strip()
        )
        normalized_tool = (
            tool.strip()
            if tool and tool.strip()
            else ""
        )
        normalized_version = (
            version.strip()
            if version and version.strip()
            else ""
        )
        normalized_visibility = (
            visibility.strip().lower()
        )
        normalized_document_type = (
            document_type.strip()
        )

        document_sha256 = (
            self.calculate_sha256(
                file_path
            )
        )

        document = self.loader.load(
            path=str(file_path),
            domain=normalized_domain,
        )

        chunks = self.chunker.chunk_document(
            document
        )

        if not chunks:
            raise RuntimeError(
                "Knowledge document produced no chunks: "
                f"{file_path}"
            )

        prepared_chunks = []

        for chunk in chunks:
            original_chunk_id = (
                chunk["chunk_id"]
            )

            content_chunk_id = (
                f"sha256:{document_sha256}"
                f"::{original_chunk_id}"
            )

            prepared_chunks.append(
                {
                    **chunk,
                    "chunk_id": content_chunk_id,
                }
            )

        expected_ids = {
            item["chunk_id"]
            for item in prepared_chunks
        }

        if len(expected_ids) != len(
            prepared_chunks
        ):
            raise RuntimeError(
                "Duplicate chunk IDs were generated "
                "for the document."
            )

        existing_records = (
            self.vector_store
            .collection
            .get(
                where={
                    "document_sha256": (
                        document_sha256
                    ),
                },
                include=[
                    "metadatas",
                ],
            )
        )

        existing_ids = set(
            existing_records.get(
                "ids",
                [],
            )
        )

        unexpected_ids = (
            existing_ids
            - expected_ids
        )

        if unexpected_ids:
            raise RuntimeError(
                "The document was previously indexed "
                "with an incompatible chunking layout. "
                f"document_sha256={document_sha256}; "
                f"unexpected_chunks="
                f"{len(unexpected_ids)}."
            )

        missing_chunks = [
            item
            for item in prepared_chunks
            if item["chunk_id"]
            not in existing_ids
        ]

        if not missing_chunks:
            return {
                "status": "completed",
                "created": False,
                "duplicate": True,
                "resumed": False,
                "source": file_path.name,
                "document_sha256": (
                    document_sha256
                ),
                "domain": normalized_domain,
                "subdomain": (
                    normalized_subdomain
                ),
                "tool": normalized_tool,
                "version": normalized_version,
                "visibility": (
                    normalized_visibility
                ),
                "chunks_total": len(
                    prepared_chunks
                ),
                "chunks_preexisting": len(
                    existing_ids
                ),
                "chunks_indexed": 0,
                "vector_count": (
                    self.vector_store.count()
                ),
            }

        resumed = bool(existing_ids)

        started_at = time.perf_counter()

        indexed = 0
        batches = 0

        for start in range(
            0,
            len(missing_chunks),
            self.batch_size,
        ):
            end = min(
                start + self.batch_size,
                len(missing_chunks),
            )

            batch = missing_chunks[
                start:end
            ]

            texts = [
                item["text"]
                for item in batch
            ]

            ids = [
                item["chunk_id"]
                for item in batch
            ]

            embeddings = (
                self.embedding_service
                .embed_batch(texts)
            )

            if len(embeddings) != len(
                batch
            ):
                raise RuntimeError(
                    "Embedding count does not match "
                    "knowledge chunk count."
                )

            metadatas = []

            for item in batch:
                metadatas.append(
                    {
                        "source": (
                            file_path.name
                        ),
                        "domain": (
                            normalized_domain
                        ),
                        "subdomain": (
                            normalized_subdomain
                        ),
                        "tool": (
                            normalized_tool
                        ),
                        "version": (
                            normalized_version
                        ),
                        "visibility": (
                            normalized_visibility
                        ),
                        "document_type": (
                            normalized_document_type
                        ),
                        "document_sha256": (
                            document_sha256
                        ),
                        "page": int(
                            item.get("page")
                            or 0
                        ),
                        "chunk_index": int(
                            item.get(
                                "chunk_index"
                            )
                            or 0
                        ),
                        "character_count": int(
                            item.get(
                                "character_count"
                            )
                            or len(
                                item["text"]
                            )
                        ),
                        "chunk_size_setting": int(
                            self.chunker.chunk_size
                        ),
                        "chunk_overlap_setting": int(
                            self.chunker.overlap
                        ),
                    }
                )

            self.vector_store.collection.upsert(
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
            )

            indexed += len(batch)
            batches += 1

            print(
                "[KnowledgeIngestionService] "
                f"{indexed}/"
                f"{len(missing_chunks)} "
                f"missing chunks indexed "
                f"(batch={batches})"
            )

        duration_seconds = round(
            time.perf_counter()
            - started_at,
            3,
        )

        verification_records = (
            self.vector_store
            .collection
            .get(
                where={
                    "document_sha256": (
                        document_sha256
                    ),
                },
                include=[
                    "metadatas",
                ],
            )
        )

        verified_ids = set(
            verification_records.get(
                "ids",
                [],
            )
        )

        if verified_ids != expected_ids:
            raise RuntimeError(
                "Document ingestion verification "
                "failed after Chroma write."
            )

        return {
            "status": "completed",
            "created": not resumed,
            "duplicate": False,
            "resumed": resumed,
            "source": file_path.name,
            "document_sha256": (
                document_sha256
            ),
            "domain": normalized_domain,
            "subdomain": (
                normalized_subdomain
            ),
            "tool": normalized_tool,
            "version": normalized_version,
            "visibility": (
                normalized_visibility
            ),
            "chunks_total": len(
                prepared_chunks
            ),
            "chunks_preexisting": len(
                existing_ids
            ),
            "chunks_indexed": indexed,
            "batches": batches,
            "batch_size": self.batch_size,
            "duration_seconds": (
                duration_seconds
            ),
            "vector_count": (
                self.vector_store.count()
            ),
        }

    @staticmethod
    def _validate_inputs(
        path: str,
        domain: str,
        subdomain: str,
        visibility: str,
        document_type: str,
    ) -> Path:
        if not path or not path.strip():
            raise ValueError(
                "Document path cannot be empty."
            )

        file_path = Path(path)

        if not file_path.is_file():
            raise FileNotFoundError(
                f"Knowledge document not found: "
                f"{file_path}"
            )

        if not domain or not domain.strip():
            raise ValueError(
                "Knowledge domain cannot be empty."
            )

        if (
            not subdomain
            or not subdomain.strip()
        ):
            raise ValueError(
                "Knowledge subdomain cannot be empty."
            )

        normalized_visibility = (
            visibility.strip().lower()
            if visibility
            else ""
        )

        if normalized_visibility not in {
            "private",
            "public",
        }:
            raise ValueError(
                "visibility must be private "
                "or public."
            )

        if (
            not document_type
            or not document_type.strip()
        ):
            raise ValueError(
                "document_type cannot be empty."
            )

        return file_path