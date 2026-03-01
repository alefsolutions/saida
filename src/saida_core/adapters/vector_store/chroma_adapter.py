from __future__ import annotations

from saida_core.core.contracts.vector_store import VectorStore


class ChromaVectorStoreAdapter(VectorStore):
    def __init__(self):
        self._items: dict[str, dict] = {}

    def upsert(self, item_id: str, vector: list[float], metadata: dict) -> None:
        self._items[item_id] = {"vector": vector, "metadata": metadata}

    def query(self, vector: list[float], top_k: int = 5) -> list[dict]:
        results = []
        for item_id, payload in self._items.items():
            results.append({"id": item_id, **payload})
        return results[:top_k]