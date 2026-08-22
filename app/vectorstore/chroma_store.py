import chromadb


class ChromaVectorStore:
    """
    Persistent ChromaDB vector store.

    Stores document text, embeddings, and metadata for
    the RAG/GraphRAG knowledge base.
    """

    def __init__(
        self,
        persist_directory: str = "data/chroma",
        collection_name: str = "personal_knowledge",
    ):
        self.client = chromadb.PersistentClient(
            path=persist_directory
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name
        )

    def add_documents(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
    ) -> None:
        """Add documents and their embeddings to ChromaDB."""

        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 3,
        where: dict | None = None,
    ):
        """
        Search ChromaDB using a query embedding.

        Args:
            query_embedding: Embedding vector for the query.
            n_results: Maximum number of results.
            where: Optional metadata filter, for example:
                   {"domain": "drug_discovery"}.
        """

        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
        )

    def count(self) -> int:
        """Return the number of stored documents."""

        return self.collection.count()

    def reset(self) -> None:
        """Delete all documents from the current collection."""

        collection_name = self.collection.name

        self.client.delete_collection(
            collection_name
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name
        )