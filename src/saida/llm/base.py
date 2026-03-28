"""Base interface for optional LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from saida.llm.models import IntentProposal, SummaryContext, SummaryProposal


class BaseLlmProvider(ABC):
    """Abstract provider used by SAIDA for optional prompt and summary handling."""

    provider_name: str = "base"

    @abstractmethod
    def interpret_prompt(
        self,
        question: str,
        dataset_name: str,
        profile_summary: str,
        context_summary: str | None,
    ) -> IntentProposal | None:
        """Return a structured prompt interpretation or None to skip LLM handling."""

    @abstractmethod
    def generate_summary(self, summary_context: SummaryContext) -> SummaryProposal | None:
        """Return a structured summary proposal or None to skip optional LLM summary generation."""
