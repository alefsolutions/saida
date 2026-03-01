from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from saida_core.core.contracts.embedding import EmbeddingModel


class OpenAIEmbeddingAdapter(EmbeddingModel):
    def __init__(self, client: Any | None = None, model: str | None = None):
        self._client = client
        self.model = model or os.getenv("SAIDA_OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAIEmbeddingAdapter.")
        self._client = OpenAI(api_key=api_key)
        return self._client

    def embed(self, text: str) -> list[float]:
        response = self._get_client().embeddings.create(
            model=self.model,
            input=text,
        )
        return list(response.data[0].embedding)
