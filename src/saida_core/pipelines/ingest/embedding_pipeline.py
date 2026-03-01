from __future__ import annotations

from saida_core.core.contracts.embedding import EmbeddingModel


class EmbeddingPipeline:
    def __init__(self, model: EmbeddingModel):
        self.model = model

    def run(self, text: str) -> list[float]:
        return self.model.embed(text)