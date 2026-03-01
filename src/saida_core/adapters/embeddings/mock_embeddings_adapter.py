from __future__ import annotations

from saida_core.core.contracts.embedding import EmbeddingModel


class MockEmbeddingAdapter(EmbeddingModel):
    def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]