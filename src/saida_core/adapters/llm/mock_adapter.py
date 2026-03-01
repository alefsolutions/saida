from __future__ import annotations

from saida_core.core.contracts.llm import LLM


class MockLLMAdapter(LLM):
    def generate(self, prompt: str) -> str:
        return f"[mock-llm] {prompt}"