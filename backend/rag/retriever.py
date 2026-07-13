"""Schema-aware retriever backed by ChromaDB.

We compute embeddings ourselves (via the pluggable EmbeddingProvider) and
pass them directly to Chroma's add/query calls, rather than wrapping TF-IDF
as a Chroma EmbeddingFunction. Because the schema corpus is small and only
changes when datasets are added/edited, we rebuild the whole collection
(refit + re-embed + upsert) on every change instead of doing incremental
inserts against a fixed vocabulary -- this keeps the TF-IDF vector space
internally consistent without the complexity of an online vocabulary.
"""
from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger

from backend.config import get_settings
from backend.rag.embeddings import get_embedding_provider
from backend.rag.schema_loader import SchemaDocument, load_schema_documents

settings = get_settings()
_COLLECTION_NAME = "schema_knowledge_base"


def _get_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(
        path=settings.vector_db_path,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def rebuild_schema_index(documents: list[SchemaDocument] | None = None) -> int:
    documents = documents if documents is not None else load_schema_documents()
    client = _get_client()
    try:
        client.delete_collection(_COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(_COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

    if not documents:
        logger.info("Schema index rebuild: no datasets yet, nothing to embed.")
        return 0

    provider = get_embedding_provider()
    texts = [doc.text for doc in documents]
    provider.fit(texts)
    vectors = provider.embed(texts)

    collection.add(
        ids=[doc.id for doc in documents],
        embeddings=vectors.tolist(),
        documents=texts,
        metadatas=[doc.metadata for doc in documents],
    )
    logger.info("Schema index rebuilt with {} documents.", len(documents))
    return len(documents)


def retrieve_schema_context(question: str, top_k: int = 8) -> list[dict]:
    client = _get_client()
    provider = get_embedding_provider()

    try:
        collection = client.get_collection(_COLLECTION_NAME)
        if not provider.is_fitted or collection.count() == 0:
            raise ValueError("stale or empty index")
    except Exception:
        rebuild_schema_index()
        collection = client.get_collection(_COLLECTION_NAME)

    if collection.count() == 0:
        return []

    query_vector = provider.embed([question])
    results = collection.query(query_embeddings=query_vector.tolist(), n_results=min(top_k, collection.count()))

    return [
        {"text": doc, "metadata": meta, "distance": dist}
        for doc, meta, dist in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        )
    ]
