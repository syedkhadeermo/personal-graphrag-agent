from app.embeddings.ollama_embeddings import OllamaEmbeddingService
from app.vectorstore.chroma_store import ChromaVectorStore


def test_vector_store_retrieval():

    embedding_service = OllamaEmbeddingService()

    vector_store = ChromaVectorStore(
        persist_directory="data/test_chroma",
        collection_name="test_collection",
    )

    documents = [
        "AutoDock Vina is used for protein ligand molecular docking.",
        "GROMACS can be used for molecular dynamics simulations.",
        "FreeCAD is used for computer aided engineering design.",
    ]

    ids = [
        "doc_1",
        "doc_2",
        "doc_3",
    ]

    embeddings = [
        embedding_service.embed(document)
        for document in documents
    ]

    vector_store.add_documents(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
    )

    query = "What software can be used for molecular docking?"

    query_embedding = embedding_service.embed(query)

    results = vector_store.search(
        query_embedding=query_embedding,
        n_results=2,
    )

    print("\nRetrieved documents:")

    for document in results["documents"][0]:
        print("-", document)

    assert len(results["documents"][0]) == 2