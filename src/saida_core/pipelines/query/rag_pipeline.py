from __future__ import annotations

from saida_core.core.contracts.retriever import Retriever


class SimpleRetriever(Retriever):
    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        return [{"source": "retriever", "query": query, "score": 1.0}][:top_k]