from __future__ import annotations

import os

from saida_core.adapters.embeddings.mock_embeddings_adapter import MockEmbeddingAdapter
from saida_core.adapters.embeddings.openai_embeddings_adapter import OpenAIEmbeddingAdapter
from saida_core.adapters.vector_store.chroma_adapter import ChromaVectorStoreAdapter
from saida_core.adapters.vector_store.mock_vector_store_adapter import MockVectorStoreAdapter
from saida_core.pipelines.ingest.document_ingest import DocumentIngestPipeline


def ingest_data(path: str) -> int:
    embedding_provider = os.getenv("SAIDA_EMBEDDING_PROVIDER", "openai")
    vector_store_provider = os.getenv("SAIDA_VECTOR_STORE_PROVIDER", "chroma")

    embedding = OpenAIEmbeddingAdapter() if embedding_provider == "openai" else MockEmbeddingAdapter()
    vector_store = ChromaVectorStoreAdapter() if vector_store_provider == "chroma" else MockVectorStoreAdapter()

    pipeline = DocumentIngestPipeline(embedding=embedding, vector_store=vector_store)
    return pipeline.ingest_file(path)
