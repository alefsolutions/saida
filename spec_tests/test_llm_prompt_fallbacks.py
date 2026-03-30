from __future__ import annotations

import pandas as pd

from saida import PromptAnalysisFrontend
from saida.config import LlmConfig, SaidaConfig
from saida.core.contracts import Dataset
from saida.exceptions import LlmIntegrationError
from saida.llm import BaseLlmProvider, SummaryContext, SummaryProposal


class PromptFailingProvider(BaseLlmProvider):
    provider_name = "ollama"

    def __init__(self, code: str) -> None:
        self.code = code

    def interpret_prompt(self, question: str, dataset_name: str, profile_summary: str, context_summary: str | None):
        raise LlmIntegrationError("Prompt failed.", code=self.code, provider=self.provider_name)

    def generate_summary(self, summary_context: SummaryContext):
        return SummaryProposal(status="ready", summary=summary_context.deterministic_summary)


def test_prompt_fallback_warning_reports_model_unavailable_reason() -> None:
    dataset = Dataset(name="sales", source_type="pandas", data=pd.DataFrame({"revenue": [1.0, 2.0], "region": ["West", "East"]}))
    frontend = PromptAnalysisFrontend(
        config=SaidaConfig(llm=LlmConfig(enabled=True, provider="ollama", use_for_prompting=True, use_for_summary=False)),
        llm_provider=PromptFailingProvider("model_missing"),
    )

    result = frontend.analyze(dataset, "How many rows are in the dataset?")

    assert any("configured model was unavailable on the ollama provider" in warning for warning in result.warnings)
    assert result.response["result"]["value"] == 2


def test_prompt_fallback_warning_reports_invalid_structured_output_reason() -> None:
    dataset = Dataset(name="sales", source_type="pandas", data=pd.DataFrame({"revenue": [1.0, 2.0], "region": ["West", "East"]}))
    frontend = PromptAnalysisFrontend(
        config=SaidaConfig(llm=LlmConfig(enabled=True, provider="ollama", use_for_prompting=True, use_for_summary=False)),
        llm_provider=PromptFailingProvider("invalid_contract_json"),
    )

    result = frontend.analyze(dataset, "How many rows are in the dataset?")

    assert any("returned invalid structured output" in warning for warning in result.warnings)
    assert result.response["interpretation"]["prompt_family"] == "row_count"

