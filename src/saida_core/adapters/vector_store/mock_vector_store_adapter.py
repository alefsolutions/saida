from __future__ import annotations

from saida_core.core.contracts.vector_store import VectorStore


class MockVectorStoreAdapter(VectorStore):
    def upsert(self, item_id: str, vector: list[float], metadata: dict) -> None:
        return None

    def query(self, vector: list[float], top_k: int = 5) -> list[dict]:
        return []