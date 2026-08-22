from dataclasses import dataclass
from typing import Any


@dataclass
class TextChunk:
    """A chunk of a source document prepared for RAG processing."""

    chunk_id: str
    text: str
    domain: str
    source: str
    metadata: dict[str, Any]


class TextChunker:
    """Split documents into overlapping text chunks."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero.")

        if chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative.")

        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size."
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(
        self,
        text: str,
        domain: str,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[TextChunk]:
        """Split a document into overlapping chunks."""

        if not text or not text.strip():
            raise ValueError("Document text cannot be empty.")

        if not domain or not domain.strip():
            raise ValueError("Domain cannot be empty.")

        if not source or not source.strip():
            raise ValueError("Source cannot be empty.")

        metadata = metadata or {}

        chunks = []

        start = 0
        chunk_number = 0
        text_length = len(text)

        while start < text_length:
            end = min(start + self.chunk_size, text_length)

            chunk_text = text[start:end].strip()

            if chunk_text:
                chunk_id = (
                    f"{self._source_id(source)}"
                    f"_chunk_{chunk_number:03d}"
                )

                chunk_metadata = {
                    **metadata,
                    "domain": domain,
                    "source": source,
                    "chunk_number": chunk_number,
                    "chunk_size": len(chunk_text),
                }

                chunks.append(
                    TextChunk(
                        chunk_id=chunk_id,
                        text=chunk_text,
                        domain=domain,
                        source=source,
                        metadata=chunk_metadata,
                    )
                )

            if end >= text_length:
                break

            start = end - self.chunk_overlap
            chunk_number += 1

        return chunks

    @staticmethod
    def _source_id(source: str) -> str:
        """Create a filesystem-friendly identifier from the source name."""

        source_id = source.replace("\\", "_").replace("/", "_")

        if "." in source_id:
            source_id = source_id.rsplit(".", 1)[0]

        return source_id