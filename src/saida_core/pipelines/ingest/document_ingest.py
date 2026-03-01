from __future__ import annotations

from saida_core.core.contracts.embedding import EmbeddingModel
from saida_core.core.contracts.vector_store import VectorStore


class DocumentIngestPipeline:
    def __init__(self, embedding: EmbeddingModel, vector_store: VectorStore):
        self.embedding = embedding
        self.vector_store = vector_store

    def ingest(self, item_id: str, text: str, metadata: dict | None = None) -> None:
        vec = self.embedding.embed(text)
        self.vector_store.upsert(item_id, vec, metadata or {})