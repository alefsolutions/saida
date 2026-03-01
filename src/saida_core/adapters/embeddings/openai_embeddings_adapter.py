from __future__ import annotations

from saida_core.core.contracts.embedding import EmbeddingModel


class OpenAIEmbeddingAdapter(EmbeddingModel):
    def embed(self, text: str) -> list[float]:
        # Placeholder implementation; wire embeddings API here.
        return [float(len(text) % 10)] * 8