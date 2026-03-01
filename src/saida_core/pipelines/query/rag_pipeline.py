from __future__ import annotations

from saida_core.core.contracts.embedding import EmbeddingModel
from saida_core.core.contracts.retriever import Retriever
from saida_core.core.contracts.vector_store import VectorStore


class SimpleRetriever(Retriever):
    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        return [{"source": "retriever", "query": query, "score": 1.0}][:top_k]


class VectorStoreRetriever(Retriever):
    def __init__(self, embedding: EmbeddingModel, vector_store: VectorStore):
        self.embedding = embedding
        self.vector_store = vector_store

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        vector = self.embedding.embed(query)
        rows = self.vector_store.query(vector, top_k=top_k)
        normalized: list[dict] = []
        for row in rows:
            normalized.append(
                {
                    "source": "vector_store",
                    "id": row.get("id"),
                    "distance": row.get("distance"),
                    "document": row.get("document"),
                    "metadata": row.get("metadata", {}),
                }
            )
        return normalized
