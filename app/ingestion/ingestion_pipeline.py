from app.embeddings.ollama_embeddings import OllamaEmbeddingService
from app.vectorstore.chroma_store import ChromaVectorStore
from app.chunking.text_chunker import TextChunker
from app.ingestion.document_loader import MarkdownDocumentLoader
from app.knowledge_graph.graph_builder import KnowledgeGraphBuilder


class IngestionPipeline:
    """Ingest documents into both the vector store and knowledge graph."""

    def __init__(self):
        self.loader = MarkdownDocumentLoader()
        self.chunker = TextChunker(
            chunk_size=500,
            chunk_overlap=50,
        )
        self.embedding_service = OllamaEmbeddingService()
        self.vector_store = ChromaVectorStore()
        self.graph_builder = KnowledgeGraphBuilder()

    def ingest_file(self, file_path: str, domain: str) -> int:
        """Load, chunk, embed, and store a document."""

        # 1. Load document
        document = self.loader.load(file_path)

        # 2. Create chunks
        chunks = self.chunker.chunk_document(
            document["text"],
            domain=domain,
            source=document["metadata"]["file_name"],
            metadata=document["metadata"],
        )

        if not chunks:
            return 0

        # 3. Extract texts
        texts = [chunk.text for chunk in chunks]

        # 4. Generate embeddings
        embeddings = self.embedding_service.embed_batch(texts)

        # 5. Prepare vector-store data
        ids = [chunk.chunk_id for chunk in chunks]

        metadatas = [
            {
                **chunk.metadata,
                "domain": chunk.domain,
                "source": chunk.source,
                "chunk_id": chunk.chunk_id,
                "chunk_number": index,
                "chunk_size": len(chunk.text),
            }
            for index, chunk in enumerate(chunks)
        ]

        # 6. Store in ChromaDB
        self.vector_store.add_documents(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        # 7. Build knowledge graph
        for chunk in chunks:
            self.graph_builder.build_from_chunk(
                chunk.text,
                domain=chunk.domain,
                source=chunk.source,
            )

        return len(chunks)