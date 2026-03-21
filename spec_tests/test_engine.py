from __future__ import annotations

import pandas as pd
import pytest

from saida import Saida
from saida.config import LlmConfig
from saida.core.contracts import Dataset
from saida.llm import BaseLlmProvider, IntentProposal, ResponseContext, ResponseProposal, build_llm_provider
from saida.exceptions import ValidationError


class FakeLlmProvider(BaseLlmProvider):
    """Deterministic provider used to exercise the optional LLM path in tests."""

    def interpret_prompt(
        self,
        question: str,
        dataset_name: str,
        profile_summary: str,
        context_summary: str | None,
    ) -> IntentProposal | None:
        _ = dataset_name
        _ = profile_summary
        _ = context_summary
        lowered = question.lower()
        if "clarify" in lowered:
            return IntentProposal(status="clarify", message="Please clarify the target metric.", warnings=["clarification requested"])
        if "refuse" in lowered:
            return IntentProposal(status="refuse", message="We are not able to provide this information at this time.", warnings=["request refused"])

        group_by = ["region"] if "by region" in lowered else None
        time_reference = {"type": "month_name", "value": "march", "month": "3"} if "march" in lowered else None
        task_type_hint = "diagnostic" if "why" in lowered else "descriptive"
        aggregation = "mean" if "average" in lowered else None
        return IntentProposal(
            status="ready",
            task_type_hint=task_type_hint,
            target="revenue",
            aggregation=aggregation,
            group_by=group_by,
            time_reference=time_reference,
            warnings=["llm prompt path used"],
        )

    def generate_response(self, response_context: ResponseContext) -> ResponseProposal | None:
        self.last_response_context = response_context
        return ResponseProposal(
            status="ready",
            summary=f"LLM_RESPONSE_V1: {response_context.deterministic_summary}",
            warnings=["llm response path used"],
        )


class ClarifyingLlmProvider(BaseLlmProvider):
    """Provider that over-clarifies so deterministic fallback can be tested."""

    def interpret_prompt(
        self,
        question: str,
        dataset_name: str,
        profile_summary: str,
        context_summary: str | None,
    ) -> IntentProposal | None:
        _ = question
        _ = dataset_name
        _ = profile_summary
        _ = context_summary
        return IntentProposal(status="clarify", message="Please clarify.", warnings=["llm clarification"])

    def generate_response(self, response_context: ResponseContext) -> ResponseProposal | None:
        return ResponseProposal(status="ready", summary=response_context.deterministic_summary)


def test_engine_load_context_parses_markdown() -> None:
    engine = Saida()

    context = engine.load_context(
        """
# Dataset: Sales

## Metric Definitions
revenue: total revenue
""".strip()
    )

    assert context.source_summary == "Sales"
    assert context.metric_definitions["revenue"] == "total revenue"


def test_engine_exposes_current_capabilities() -> None:
    engine = Saida()

    capabilities = engine.capabilities()

    assert capabilities == {
        "analyze": True,
        "profile": True,
        "load_context": True,
        "train": False,
        "predict": False,
        "forecast": False,
        "llm_prompting": False,
        "llm_reasoning": False,
    }


def test_engine_rejects_empty_dataset() -> None:
    engine = Saida()
    dataset = Dataset(name="empty", source_type="pandas", data=pd.DataFrame({"revenue": []}))

    with pytest.raises(ValidationError, match="Cannot analyze an empty dataset"):
        engine.analyze(dataset, "Show revenue")


def test_engine_rejects_duplicate_columns() -> None:
    engine = Saida()
    dataset = Dataset(name="dup", source_type="pandas", data=pd.DataFrame([[1, 2]], columns=["revenue", "revenue"]))

    with pytest.raises(ValidationError, match="duplicate column names"):
        engine.analyze(dataset, "Show revenue")


def test_engine_rejects_non_dataframe_dataset() -> None:
    engine = Saida()
    dataset = Dataset(name="bad", source_type="pandas", data=[{"revenue": 1}])  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="must be a pandas DataFrame"):
        engine.analyze(dataset, "Show revenue")


def test_engine_profile_returns_dataset_profile() -> None:
    engine = Saida()
    dataset = Dataset(
        name="sales",
        source_type="pandas",
        data=pd.DataFrame({"revenue": [100.0, 90.0], "region": ["West", "East"]}),
    )

    profile = engine.profile(dataset)

    assert profile.dataset_name == "sales"
    assert "revenue" in profile.measure_columns


def test_engine_analyze_includes_context_trace_stage() -> None:
    engine = Saida()
    context = engine.load_context(
        """
# Dataset: Sales

## Metric Definitions
revenue: total revenue
""".strip()
    )
    dataset = Dataset(
        name="sales",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "posted_at": ["2026-02-01", "2026-03-01"],
                "revenue": [100.0, 90.0],
                "region": ["West", "East"],
            }
        ),
        context=context,
    )

    result = engine.analyze(dataset, "Why did revenue drop in March?")

    assert any(event.stage == "context" for event in result.trace)


def test_engine_analyze_without_context_has_no_context_trace_stage() -> None:
    engine = Saida()
    dataset = Dataset(
        name="sales",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "posted_at": ["2026-02-01", "2026-03-01"],
                "revenue": [100.0, 90.0],
                "region": ["West", "East"],
            }
        ),
    )

    result = engine.analyze(dataset, "Why did revenue drop in March?")

    assert all(event.stage != "context" for event in result.trace)


def test_engine_with_llm_provider_exposes_llm_capabilities() -> None:
    engine = Saida(llm_provider=FakeLlmProvider())
    engine.config.llm.enabled = True

    capabilities = engine.capabilities()

    assert capabilities["llm_prompting"] is True
    assert capabilities["llm_reasoning"] is True


def test_engine_returns_clarification_when_llm_requests_it() -> None:
    engine = Saida(llm_provider=FakeLlmProvider())
    engine.config.llm.enabled = True
    dataset = Dataset(
        name="sales",
        source_type="pandas",
        data=pd.DataFrame({"revenue": [100.0, 90.0], "region": ["West", "East"]}),
    )

    result = engine.analyze(dataset, "clarify this request")

    assert result.summary == "Please clarify the target metric."
    assert result.deterministic_summary is None
    assert result.llm_summary is None
    assert result.summary_source == "deterministic"
    assert result.plan.task_type == "clarification"
    assert result.tables == []
    assert result.response["status"] == "clarify"
    assert result.response["reasoning"]["summary"] == "Please clarify the target metric."
    assert result.response["errors"] == []


def test_engine_returns_refusal_when_llm_declines_request() -> None:
    engine = Saida(llm_provider=FakeLlmProvider())
    engine.config.llm.enabled = True
    dataset = Dataset(
        name="sales",
        source_type="pandas",
        data=pd.DataFrame({"revenue": [100.0, 90.0], "region": ["West", "East"]}),
    )

    result = engine.analyze(dataset, "refuse this request")

    assert result.summary == "We are not able to provide this information at this time."
    assert result.deterministic_summary is None
    assert result.llm_summary is None
    assert result.summary_source == "deterministic"
    assert result.plan.task_type == "unavailable"
    assert result.metrics == []
    assert result.response["status"] == "refuse"
    assert result.response["reasoning"]["summary"] == "We are not able to provide this information at this time."


def test_engine_overrides_llm_clarification_when_deterministic_intent_is_clear() -> None:
    engine = Saida(llm_provider=ClarifyingLlmProvider())
    engine.config.llm.enabled = True
    dataset = Dataset(
        name="sales",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "posted_at": ["2026-01-01", "2026-01-02", "2026-01-03"],
                "revenue": [100.0, 90.0, 80.0],
                "segment": ["Retail", "Wholesale", "Retail"],
            }
        ),
    )

    result = engine.analyze(dataset, "Which segment is the least represented?")

    assert result.plan.task_type == "descriptive"
    assert result.response["status"] == "ok"
    assert result.response["interpretation"]["intent_name"] == "representation_ranking"


def test_engine_analysis_response_contract_records_intent_and_operations() -> None:
    engine = Saida()
    dataset = Dataset(
        name="sales",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "posted_at": ["2026-01-01", "2026-02-01", "2026-03-01"],
                "revenue": [100.0, 90.0, 80.0],
                "region": ["West", "West", "East"],
            }
        ),
    )

    result = engine.analyze(dataset, "What is the average revenue?")

    assert result.response["schema_version"] == "saida.response.v2"
    assert result.response["status"] == "ok"
    assert result.response["interpretation"]["aggregation"] == "mean"
    assert result.response["interpretation"]["target"] == "revenue"
    assert result.response["execution"]["step_count"] >= 1
    assert any(operation["action"] == "aggregate_value" for operation in result.response["execution"]["steps"])
    assert "revenue_mean" in result.response["meta"]["metric_lookup"]
    assert result.deterministic_summary is not None
    assert result.response["reasoning"]["deterministic_summary"] == result.deterministic_summary


def test_engine_passes_context_summary_into_llm_response_stage() -> None:
    provider = FakeLlmProvider()
    engine = Saida(llm_provider=provider)
    engine.config.llm.enabled = True
    context = engine.load_context(
        """
# Dataset: Sales

## Caveats
- refunds arrive one day late

## Freshness Notes
- source refreshes daily
""".strip()
    )
    dataset = Dataset(
        name="sales",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "posted_at": ["2026-02-01", "2026-03-01"],
                "revenue": [100.0, 90.0],
                "region": ["West", "East"],
            }
        ),
        context=context,
    )

    engine.analyze(dataset, "Why did revenue drop in March?")

    assert provider.last_response_context is not None
    assert provider.last_response_context.context_summary is not None
    assert "caveats=['refunds arrive one day late']" in provider.last_response_context.context_summary
    assert "freshness_notes=['source refreshes daily']" in provider.last_response_context.context_summary


def test_llm_factory_builds_openai_provider() -> None:
    provider = build_llm_provider(
        LlmConfig(
            enabled=True,
            provider="openai",
            model="gpt-4.1-mini",
            options={"api_key": "test-key"},
        )
    )

    assert provider is not None
    assert provider.provider_name == "openai"


_ENGINE_PROFILE_CASES = [
    (
        index,
        pd.DataFrame(
            {
                "posted_at": ["2026-02-01", "2026-03-01", "2026-04-01"],
                "revenue": [float(index), float(index + 5), float(index + 10)],
                "region": [f"Region{index % 4}", f"Region{(index + 1) % 4}", f"Region{(index + 2) % 4}"],
            }
        ),
    )
    for index in range(1, 92)
]


@pytest.mark.parametrize(("case_id", "dataframe"), _ENGINE_PROFILE_CASES)
def test_engine_profiles_many_valid_datasets(case_id: int, dataframe: pd.DataFrame) -> None:
    engine = Saida()
    dataset = Dataset(name=f"sales_{case_id}", source_type="pandas", data=dataframe)

    profile = engine.profile(dataset)

    assert profile.dataset_name == f"sales_{case_id}"
    assert profile.row_count == 3
    assert "posted_at" in profile.time_columns


_DIRECT_NLP_CASES = [
    (
        index,
        pd.DataFrame(
            {
                "posted_at": ["2026-02-01", "2026-03-01", "2026-04-01"],
                "revenue": [float(index + 20), float(index + 10), float(index + 5)],
                "region": ["West", "East", "West"],
            }
        ),
        "Why did revenue drop in March?" if index % 2 == 0 else "Show revenue by region",
    )
    for index in range(1, 51)
]


@pytest.mark.parametrize(("case_id", "dataframe", "question"), _DIRECT_NLP_CASES)
def test_engine_direct_nlp_path_across_many_cases(case_id: int, dataframe: pd.DataFrame, question: str) -> None:
    engine = Saida()
    dataset = Dataset(name=f"direct_{case_id}", source_type="pandas", data=dataframe)

    result = engine.analyze(dataset, question)

    assert result.artifacts["request"]["options"]["nlp_backend"] in {"rules", "transformer+rules"}
    assert all(event.stage != "llm" for event in result.trace)
    assert result.summary


_LLM_CASES = [
    (
        index,
        pd.DataFrame(
            {
                "posted_at": ["2026-02-01", "2026-03-01", "2026-04-01"],
                "revenue": [float(index + 30), float(index + 20), float(index + 10)],
                "region": ["West", "East", "West"],
            }
        ),
        "Why did revenue drop in March by region?" if index % 2 == 0 else "Show revenue by region in March",
    )
    for index in range(1, 51)
]


@pytest.mark.parametrize(("case_id", "dataframe", "question"), _LLM_CASES)
def test_engine_llm_prompt_and_response_path_across_many_cases(case_id: int, dataframe: pd.DataFrame, question: str) -> None:
    engine = Saida(llm_provider=FakeLlmProvider())
    engine.config.llm.enabled = True
    dataset = Dataset(name=f"llm_{case_id}", source_type="pandas", data=dataframe)

    result = engine.analyze(dataset, question)

    assert result.summary.startswith("LLM_RESPONSE_V1:")
    assert result.deterministic_summary is not None
    assert result.llm_summary == result.summary
    assert result.summary_source == "llm"
    assert result.artifacts["request"]["options"]["nlp_backend"] == "llm+validation"
    assert any(event.stage == "llm" for event in result.trace)
