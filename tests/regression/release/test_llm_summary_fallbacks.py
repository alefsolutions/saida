from __future__ import annotations

import pandas as pd

from saida import PromptAnalysisFrontend
from saida.config import LlmConfig, SaidaConfig
from saida.core.contracts import Dataset
from saida.exceptions import LlmIntegrationError
from saida.llm import BaseLlmProvider, IntentProposal, SummaryContext


class SummaryFailingProvider(BaseLlmProvider):
    provider_name = "openai"

    def __init__(self, code: str) -> None:
        self.code = code

    def interpret_prompt(self, question: str, dataset_name: str, profile_summary: str, context_summary: str | None):
        return IntentProposal(status="ready")

    def generate_summary(self, summary_context: SummaryContext):
        raise LlmIntegrationError("Summary failed.", code=self.code, provider=self.provider_name)


def test_summary_fallback_warning_reports_auth_configuration_reason() -> None:
    dataset = Dataset(name="sales", source_type="pandas", data=pd.DataFrame({"revenue": [1.0, 2.0], "region": ["West", "East"]}))
    engine = PromptAnalysisFrontend(
        config=SaidaConfig(llm=LlmConfig(enabled=True, provider="openai", use_for_summary=True)),
        llm_provider=SummaryFailingProvider("auth_missing"),
    )

    result = engine.analyze(dataset, "How many rows are in the dataset?")

    assert any("authentication or configuration was invalid" in warning for warning in result.warnings)
    assert result.response["summary"]["summary_source"] == "deterministic"


def test_summary_fallback_warning_reports_provider_unreachable_reason() -> None:
    dataset = Dataset(name="sales", source_type="pandas", data=pd.DataFrame({"revenue": [1.0, 2.0], "region": ["West", "East"]}))
    engine = PromptAnalysisFrontend(
        config=SaidaConfig(llm=LlmConfig(enabled=True, provider="openai", use_for_summary=True)),
        llm_provider=SummaryFailingProvider("provider_unreachable"),
    )

    result = engine.analyze(dataset, "How many rows are in the dataset?")

    assert any("provider was unreachable" in warning for warning in result.warnings)
    assert result.response["summary"]["llm_summary"] is None

