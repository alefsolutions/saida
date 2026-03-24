"""Formal interfaces for optional analysis plan generation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from saida.core.contracts import AnalysisPlan, AnalysisRequest, Dataset, DatasetProfile, ExecutionTraceEvent, SourceContext
from saida.core.prompt_capability_contract import PromptCapabilityContract


@dataclass(slots=True)
class PlanGenerationResult:
    """Canonical output of a plan generator."""

    question: str
    request: AnalysisRequest
    request_warnings: list[str]
    capability_contract: PromptCapabilityContract
    contract_warning_messages: list[str]
    plan: AnalysisPlan
    terminal_summary: str | None = None
    trace_event: ExecutionTraceEvent | None = None
    generator_name: str = "rule_based"


class AnalysisPlanGeneratorInterface(ABC):
    """Formal interface for generating candidate AnalysisPlans from frontends."""

    @property
    @abstractmethod
    def generator_name(self) -> str:
        """Return the generator identifier."""

    @abstractmethod
    def generate(
        self,
        question: str,
        dataset: Dataset,
        profile: DatasetProfile,
        context: SourceContext | None,
    ) -> PlanGenerationResult:
        """Generate a candidate AnalysisPlan from the given frontend input."""
