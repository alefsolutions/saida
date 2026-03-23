from __future__ import annotations

import pandas as pd
import pytest

from saida import Saida
from saida.config import LlmConfig
from saida.core import get_capability_contract
from saida.core.contracts import Dataset
from saida.llm import BaseLlmProvider, IntentProposal, OpenAiLlmProvider, OllamaLlmProvider, ResponseContext, ResponseProposal, build_llm_provider
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


class RefusingLlmProvider(BaseLlmProvider):
    """Provider that refuses requests so deterministic override can be tested."""

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
        return IntentProposal(status="refuse", message="Refused by test provider.", warnings=["llm refusal"])

    def generate_response(self, response_context: ResponseContext) -> ResponseProposal | None:
        return ResponseProposal(status="ready", summary=response_context.deterministic_summary)


class YearMonthFilterLlmProvider(BaseLlmProvider):
    """Provider that proposes a raw YYYY-MM filter on a time column."""

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
        return IntentProposal(
            status="ready",
            task_type_hint="descriptive",
            filters={"created_at": "2025-01"},
            warnings=["llm prompt path used"],
        )

    def generate_response(self, response_context: ResponseContext) -> ResponseProposal | None:
        return ResponseProposal(status="ready", summary=response_context.deterministic_summary)


class CanonicalQuestionLlmProvider(BaseLlmProvider):
    """Provider that simplifies awkward phrasing into a clearer equivalent prompt."""

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
        return IntentProposal(
            status="ready",
            canonical_question="Count rows for Q1",
            prompt_family_hint="row_count",
            confidence=0.94,
            warnings=["llm prompt path used"],
        )

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
        "prompt_capability_contract": True,
        "capability_registry": True,
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
    assert result.response["interpretation"]["capability_contract"]["status"] in {
        "supported_and_data_feasible",
        "supported_with_partial_fallback",
    }
    assert result.response["execution"]["step_count"] >= 1
    assert any(operation["action"] == "aggregate_value" for operation in result.response["execution"]["steps"])
    assert "revenue_mean" in result.response["meta"]["metric_lookup"]
    assert result.response["meta"]["capability_contract_status"] in {
        "supported_and_data_feasible",
        "supported_with_partial_fallback",
    }
    assert result.deterministic_summary is not None
    assert result.response["reasoning"]["deterministic_summary"] == result.deterministic_summary


def test_engine_coerces_llm_year_month_filter_on_time_column() -> None:
    engine = Saida(llm_provider=YearMonthFilterLlmProvider())
    engine.config.llm.enabled = True
    dataset = Dataset(
        name="support",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "created_at": ["2025-01-01", "2025-01-15", "2025-02-01", "2026-01-01"],
                "team": ["Support", "Platform", "Support", "Payments"],
                "priority": ["High", "Low", "Medium", "High"],
            }
        ),
    )

    result = engine.analyze(dataset, "List all rows for January 2025")

    assert result.response["status"] == "ok"
    assert result.response["interpretation"]["filters"] == {
        "created_at": {
            "op": "year_month_eq",
            "value": "2025-01",
            "year": 2025,
            "month": 1,
            "label": "2025-01",
        }
    }
    assert result.response["result"]["name"] == "tabular_query"
    assert result.response["result"]["row_count"] == 2
    assert result.response["result"]["pagination"]["total_rows"] == 2
    assert result.artifacts["request"]["options"]["nlp_backend"] == "llm+validation"


def test_engine_uses_llm_canonical_question_for_condensed_prompt_routing() -> None:
    engine = Saida(llm_provider=CanonicalQuestionLlmProvider())
    engine.config.llm.enabled = True
    dataset = Dataset(
        name="support",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "created_at": ["2025-01-01", "2025-02-01", "2025-03-01", "2025-04-01"],
                "team": ["Support", "Platform", "Support", "Payments"],
                "priority": ["High", "Low", "Medium", "High"],
            }
        ),
    )

    result = engine.analyze(dataset, "Count total rows in dataset for Q1")

    assert result.response["status"] == "ok"
    assert result.response["interpretation"]["intent_name"] == "row_count"
    assert result.response["interpretation"]["prompt_family"] == "row_count"
    assert result.response["interpretation"]["filters"] == {
        "created_at": {"op": "quarter_eq", "value": 1, "label": "q1"}
    }
    assert result.response["result"]["name"] == "row_count"
    assert result.response["result"]["value"] == 3
    assert result.artifacts["request"]["options"]["canonical_question"] == "Count rows for Q1"
    assert result.artifacts["request"]["options"]["canonical_question_used"] is True
    assert result.artifacts["request"]["options"]["prompt_family_hint"] == "row_count"
    assert result.artifacts["request"]["options"]["llm_confidence"] == 0.94
    assert result.artifacts["request"]["options"]["nlp_backend"] == "llm+validation"


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


def test_engine_passes_tabular_table_metadata_into_llm_response_stage() -> None:
    provider = FakeLlmProvider()
    engine = Saida(llm_provider=provider)
    engine.config.llm.enabled = True
    dataset = Dataset(
        name="tickets",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "ticket_id": ["T1", "T2", "T3"],
                "created_at": ["2026-01-01", "2026-01-02", "2026-01-03"],
                "reopened_flag": ["yes", "no", "yes"],
                "priority": ["Low", "Medium", "High"],
            }
        ),
    )

    engine.analyze(dataset, "Give me 2 tickets from the data set")

    assert provider.last_response_context is not None
    assert "tabular_query" in provider.last_response_context.table_index
    assert "metadata" in provider.last_response_context.table_index["tabular_query"]


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


def test_engine_overrides_llm_refusal_for_supported_tabular_query() -> None:
    engine = Saida(llm_provider=RefusingLlmProvider())
    engine.config.llm.enabled = True
    dataset = Dataset(
        name="tickets",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "ticket_id": ["T1", "T2", "T3"],
                "created_at": ["2026-01-01", "2026-01-02", "2026-01-03"],
                "reopened_flag": ["yes", "no", "yes"],
                "priority": ["Low", "Medium", "High"],
            }
        ),
    )

    result = engine.analyze(dataset, "Give me 2 tickets from the data set")

    assert result.response["status"] == "ok"
    assert result.response["interpretation"]["intent_name"] == "tabular_query"
    assert any(table.name == "tabular_query" for table in result.tables)
    assert any("deterministic request normalization found a valid supported intent" in warning for warning in result.warnings)


def test_openai_intent_prompt_mentions_tabular_query_capabilities() -> None:
    provider = OpenAiLlmProvider(LlmConfig(enabled=True, provider="openai", model="gpt-4.1-mini", options={"api_key": "test-key"}))

    prompt = provider._build_intent_prompt("Give me 20 tickets", "tickets", "rows=500", None)

    assert "tabular query workflows" in prompt
    assert "selected columns" in prompt
    assert "sorting" in prompt
    assert "limits" in prompt
    assert "grouped table outputs" in prompt
    assert "pagination-friendly requests" in prompt


def test_ollama_intent_prompt_mentions_tabular_query_capabilities() -> None:
    provider = OllamaLlmProvider(LlmConfig(enabled=True, provider="ollama", model="llama3.1"))

    prompt = provider._build_intent_prompt("Give me 20 tickets", "tickets", "rows=500", None)

    assert "tabular query workflows" in prompt
    assert "selected columns" in prompt
    assert "sorting" in prompt
    assert "limits" in prompt
    assert "grouped table outputs" in prompt
    assert "pagination-friendly requests" in prompt


def test_capability_contract_exposes_live_input_and_result_surfaces() -> None:
    contract = get_capability_contract()

    assert "input_surface" in contract
    assert "intent_families" in contract
    assert "result_contract" in contract
    assert "tabular_querying" in contract["intent_families"]
    assert "ranking" in contract["intent_families"]
    assert "analysis_result_top_level_fields" in contract["result_contract"]
    assert "physical_shapes" in contract["result_contract"]
    assert "logical_shapes" in contract["result_contract"]
    assert "recordset" in contract["result_contract"]["physical_shapes"]
    assert "verification" in contract["result_contract"]["logical_shapes"]
    assert "pagination_fields" in contract["result_contract"]


def test_provider_prompts_include_contract_driven_result_surface_text() -> None:
    provider = OpenAiLlmProvider(LlmConfig(enabled=True, provider="openai", model="gpt-4.1-mini", options={"api_key": "test-key"}))
    response_prompt = provider._build_response_prompt(
        ResponseContext(
            question="Show revenue by region",
            dataset_name="sales",
            task_type="descriptive",
            deterministic_summary="Deterministic summary.",
            context_summary=None,
            metric_lookup={"revenue_sum": 100.0},
            table_index={"group_breakdown": {"rows": 2, "columns": ["region", "target_total"], "description": "Breakdown", "metadata": {}}},
            warnings=[],
        )
    )

    assert "schema_version, status, request, interpretation, execution, result, tables, reasoning, history, warnings, errors, meta" in response_prompt
    assert "name, description, physical_shape, logical_shape, dtype, schema, dimensions, row_count, labels, pagination, metadata, value" in response_prompt


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
