"""Optional model-agnostic LLM integrations."""

from saida.llm.base import BaseLlmProvider
from saida.llm.factory import build_llm_provider
from saida.llm.models import IntentProposal, SummaryContext, SummaryProposal
from saida.llm.openai_provider import OpenAiLlmProvider
from saida.llm.ollama import OllamaLlmProvider

__all__ = [
    "BaseLlmProvider",
    "IntentProposal",
    "OpenAiLlmProvider",
    "OllamaLlmProvider",
    "SummaryContext",
    "SummaryProposal",
    "build_llm_provider",
]
