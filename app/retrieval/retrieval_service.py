from typing import Any

from app.embeddings.ollama_embeddings import (
    OllamaEmbeddingService,
)
from app.vectorstore.chroma_store import (
    ChromaVectorStore,
)


class RetrievalService:
    """
    Retrieve relevant knowledge from ChromaDB.

    Supports:
        - semantic vector search
        - domain filtering
        - subdomain filtering
        - tool filtering
        - version filtering
        - visibility filtering
        - document-type filtering
        - source filtering
        - compound metadata filtering
        - relevance threshold
        - clean result formatting

    Existing domain-only calls remain supported.
    """

    _FILTER_FIELDS = (
        "domain",
        "subdomain",
        "tool",
        "version",
        "visibility",
        "document_type",
        "source",
    )

    def __init__(
        self,
        embedding_service: OllamaEmbeddingService | None = None,
        vector_store: ChromaVectorStore | None = None,
        relevance_threshold: float = 0.85,
    ):
        self.embedding_service = (
            embedding_service
            or OllamaEmbeddingService()
        )

        self.vector_store = (
            vector_store
            or ChromaVectorStore(
                collection_name="technical_knowledge"
            )
        )

        self.relevance_threshold = (
            relevance_threshold
        )

    def search(
        self,
        query: str,
        n_results: int = 5,
        domain: str | None = None,
        subdomain: str | None = None,
        tool: str | None = None,
        version: str | None = None,
        visibility: str | None = None,
        document_type: str | None = None,
        source: str | None = None,
    ) -> list[dict]:
        """
        Search the knowledge base using semantic similarity.

        Metadata and input validation occurs before embedding
        generation so invalid requests perform no model work.
        """

        if not query or not query.strip():
            raise ValueError(
                "Query cannot be empty."
            )

        if n_results <= 0:
            raise ValueError(
                "n_results must be greater than zero."
            )

        # Validate and construct metadata filters before invoking
        # the embedding model.
        where = self._build_where(
            domain=domain,
            subdomain=subdomain,
            tool=tool,
            version=version,
            visibility=visibility,
            document_type=document_type,
            source=source,
        )

        query_embedding = (
            self.embedding_service.embed(
                query.strip()
            )
        )

        search_kwargs: dict[str, Any] = {
            "query_embedding":
                query_embedding,

            "n_results":
                n_results,
        }

        if where is not None:
            search_kwargs["where"] = (
                where
            )

        raw_results = (
            self.vector_store.search(
                **search_kwargs
            )
        )

        documents = raw_results.get(
            "documents",
            [[]],
        )

        metadatas = raw_results.get(
            "metadatas",
            [[]],
        )

        distances = raw_results.get(
            "distances",
            [[]],
        )

        if (
            not documents
            or not documents[0]
        ):
            return []

        documents = documents[0]

        metadatas = (
            metadatas[0]
            if metadatas
            else []
        )

        distances = (
            distances[0]
            if distances
            else []
        )

        results = []

        for index, text in enumerate(
            documents
        ):

            metadata = (
                metadatas[index]
                if index < len(
                    metadatas
                )
                else {}
            )

            distance = (
                distances[index]
                if index < len(
                    distances
                )
                else None
            )

            if (
                distance is not None
                and distance
                > self.relevance_threshold
            ):
                continue

            results.append(
                {
                    "text": text,
                    "metadata": metadata,
                    "distance": distance,
                }
            )

        return results

    def search_by_domain(
        self,
        query: str,
        domain: str,
        n_results: int = 5,
    ) -> list[dict]:
        """
        Convenience method for domain-specific retrieval.

        This method preserves the existing public interface.
        """

        return self.search(
            query=query,
            n_results=n_results,
            domain=domain,
        )

    def search_by_tool(
        self,
        query: str,
        domain: str,
        tool: str,
        n_results: int = 5,
    ) -> list[dict]:
        """
        Convenience method for domain-and-tool retrieval.
        """

        return self.search(
            query=query,
            n_results=n_results,
            domain=domain,
            tool=tool,
        )

    @classmethod
    def _build_where(
        cls,
        domain: str | None = None,
        subdomain: str | None = None,
        tool: str | None = None,
        version: str | None = None,
        visibility: str | None = None,
        document_type: str | None = None,
        source: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Build a Chroma-compatible metadata filter.

        A single condition preserves the original simple filter
        structure. Multiple conditions use Chroma's $and syntax.
        """

        supplied_filters = {
            "domain": domain,
            "subdomain": subdomain,
            "tool": tool,
            "version": version,
            "visibility": visibility,
            "document_type": document_type,
            "source": source,
        }

        normalized_filters: dict[
            str,
            str,
        ] = {}

        for field in cls._FILTER_FIELDS:

            value = supplied_filters[
                field
            ]

            if value is None:
                continue

            if not isinstance(
                value,
                str,
            ):
                raise TypeError(
                    f"{field} must be a string."
                )

            normalized_value = (
                value.strip()
            )

            if not normalized_value:
                raise ValueError(
                    f"{field} cannot be empty."
                )

            normalized_filters[
                field
            ] = normalized_value

        if not normalized_filters:
            return None

        if len(normalized_filters) == 1:

            field, value = next(
                iter(
                    normalized_filters.items()
                )
            )

            return {
                field: value,
            }

        return {
            "$and": [
                {
                    field: {
                        "$eq": value,
                    }
                }
                for field, value
                in normalized_filters.items()
            ]
        }
