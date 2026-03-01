from __future__ import annotations

from saida_core.core.contracts.llm import LLM


class OpenAILLMAdapter(LLM):
    def generate(self, prompt: str) -> str:
        # Placeholder implementation; wire OpenAI SDK here.
        return f"[openai-placeholder] {prompt[:220]}"