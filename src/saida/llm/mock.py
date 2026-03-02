from __future__ import annotations

from saida.llm.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    name = "mock"

    def explain(self, prompt: str) -> str:
        return "Mock explanation generated from validated tool outputs."
