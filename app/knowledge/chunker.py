from typing import Any


class KnowledgeChunker:
    """
    Split normalized document pages into overlapping text chunks.

    Each chunk preserves:
        - source filename
        - domain
        - page number
        - chunk index
        - chunk_id
        - text
    """

    def __init__(
        self,
        chunk_size: int = 1200,
        overlap: int = 200,
    ):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0.")

        if overlap < 0:
            raise ValueError("overlap cannot be negative.")

        if overlap >= chunk_size:
            raise ValueError(
                "overlap must be smaller than chunk_size."
            )

        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_document(
        self,
        document: dict[str, Any],
    ) -> list[dict[str, Any]]:

        filename = document.get("filename")
        domain = document.get("domain")
        pages = document.get("pages", [])

        chunks: list[dict[str, Any]] = []

        for page in pages:

            page_number = page.get("page")
            text = (
                page.get("text", "")
                or ""
            ).strip()

            if not text:
                continue

            page_chunks = self._chunk_text(
                text=text,
            )

            for chunk_index, chunk_text in enumerate(
                page_chunks,
                start=1,
            ):

                chunk_id = (
                    f"{filename}"
                    f"::p{page_number}"
                    f"::c{chunk_index}"
                )

                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "source": filename,
                        "domain": domain,
                        "page": page_number,
                        "chunk_index": chunk_index,
                        "text": chunk_text,
                        "character_count": len(
                            chunk_text
                        ),
                    }
                )

        return chunks

    def _chunk_text(
        self,
        text: str,
    ) -> list[str]:

        chunks = []

        start = 0
        text_length = len(text)

        while start < text_length:

            end = min(
                start + self.chunk_size,
                text_length,
            )

            chunk = text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            if end >= text_length:
                break

            start = end - self.overlap

        return chunks