from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from saida_core.core.contracts.llm import LLM


class OpenAILLMAdapter(LLM):
    def __init__(self, client: Any | None = None, model: str | None = None, temperature: float = 0.0):
        self._client = client
        self.model = model or os.getenv("SAIDA_OPENAI_LLM_MODEL", "gpt-4o-mini")
        self.temperature = temperature

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAILLMAdapter.")
        self._client = OpenAI(api_key=api_key)
        return self._client

    def generate(self, prompt: str) -> str:
        response = self._get_client().responses.create(
            model=self.model,
            input=prompt,
            temperature=self.temperature,
        )

        output_text = getattr(response, "output_text", None)
        if output_text:
            return output_text.strip()

        fragments: list[str] = []
        for item in getattr(response, "output", []) or []:
            for part in getattr(item, "content", []) or []:
                text = getattr(part, "text", None)
                if text:
                    fragments.append(text)
        return "".join(fragments).strip()
