from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import pytest

from saida import PromptAnalysisFrontend
from saida.core import (
    AnalyticsConceptSpec,
    AnalyticsRegistry,
    ColumnProfile,
    DatasetProfile,
)
from saida.core.contracts import AnalysisRequest, Dataset
from saida.llm import BaseLlmProvider, IntentProposal, SummaryContext, SummaryProposal
from saida.plan_generation import build_prompt_plan_contract


def build_profile(*, include_time: bool = True, include_dimension: bool = True) -> DatasetProfile:
    columns = [
        ColumnProfile(
            name="revenue",
            inferred_type="float",
            nullable=False,
            null_ratio=0.0,
            unique_count=12,
            distinct_ratio=1.0,
            sample_values=[100.0],
            is_measure_candidate=True,
        ),
        ColumnProfile(
            name="region",
            inferred_type="category",
            nullable=False,
            null_ratio=0.0,
            unique_count=4,
            distinct_ratio=0.3,
            sample_values=["West"],
            is_dimension_candidate=True,
        ),
    ]
    time_columns: list[str] = []
    dimension_columns: list[str] = ["region"] if include_dimension else []
    if include_time:
        columns.insert(
            0,
            ColumnProfile(
                name="posted_at",
                inferred_type="datetime",
                nullable=False,
                null_ratio=0.0,
                unique_count=12,
                distinct_ratio=1.0,
                sample_values=["2026-01-01"],
                is_time_candidate=True,
            ),
        )
        time_columns = ["posted_at"]
    return DatasetProfile(
        dataset_name="sales",
        row_count=12,
        column_count=len(columns),
        columns=columns,
        measure_columns=["revenue"],
        dimension_columns=dimension_columns,
        time_columns=time_columns,
        identifier_columns=[],
    )


def build_tickets_dataset() -> Dataset:
    return Dataset(
        name="tickets",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "ticket_id": ["T1", "T2", "T3", "T4"],
                "channel": ["Email", "Phone", "Email", "Chat"],
                "priority": ["High", "High", "Low", "Low"],
                "revenue": [100.0, 200.0, 50.0, 75.0],
            }
        ),
    )


def build_tickets_dataset_with_missing_priority() -> Dataset:
    return Dataset(
        name="tickets",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "ticket_id": ["T1", "T2", "T3", "T4"],
                "channel": ["Email", "Phone", "Email", "Chat"],
                "priority": ["High", None, "Low", "Low"],
                "revenue": [100.0, 200.0, 50.0, 75.0],
            }
        ),
    )


def build_null_verification_registry_without_target_requirement() -> AnalyticsRegistry:
    registry = AnalyticsRegistry()
    registry.add_concept(AnalyticsConceptSpec("verification", "domain", "Verification", "Yes/no checks against the dataset."))
    registry.add_concept(
        AnalyticsConceptSpec(
            "null_verification",
            "pattern",
            "Null Verification",
            "Verify whether a column has or does not have null values.",
            planner_actions=["null_check"],
            result_shapes=["verification"],
        )
    )
    return registry


class CandidateCapabilityLlmProvider(BaseLlmProvider):
    """Deterministic provider used to verify candidate capability propagation."""

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
        if "missing values" in lowered:
            return IntentProposal(
                status="ready",
                candidate_capabilities=["null_verification", "verification"],
                warnings=["llm prompt path used"],
            )
        return IntentProposal(
            status="ready",
            candidate_capabilities=["grouped_tabular_retrieval", "segmentation"],
            warnings=["llm prompt path used"],
        )

    def generate_summary(self, summary_context: SummaryContext) -> SummaryProposal | None:
        return SummaryProposal(status="ready", summary=summary_context.deterministic_summary)


@pytest.mark.parametrize(
    (
        "analysis_request",
        "profile",
        "registry",
        "expected_status",
        "expected_missing_parameters",
        "expected_issue_codes",
        "expected_data_statuses",
        "expected_unsupported_capabilities",
    ),
    [
        (
            AnalysisRequest(
                question="Compare revenue this quarter to last quarter",
                intent_name="time_period_comparison",
                task_type_hint="descriptive",
                target="revenue",
                time_reference={"type": "relative_period", "value": "this_quarter"},
            ),
            build_profile(),
            None,
            "supported_and_data_feasible",
            [],
            set(),
            {"satisfied"},
            [],
        ),
        (
            AnalysisRequest(
                question="Do regions differ in revenue?",
                task_type_hint="statistical",
                target="revenue",
                options={"statistical_test": "significance_inference"},
            ),
            build_profile(),
            None,
            "supported_with_partial_fallback",
            ["group_by"],
            {"missing_requirement"},
            {"satisfied", "missing"},
            [],
        ),
        (
            AnalysisRequest(
                question="Compare revenue this quarter to last quarter",
                intent_name="time_period_comparison",
                task_type_hint="descriptive",
                target="revenue",
                time_reference={"type": "relative_period", "value": "this_quarter"},
            ),
            build_profile(include_time=False),
            None,
            "supported_but_data_insufficient",
            [],
            {"insufficient_data_support"},
            {"satisfied", "insufficient"},
            [],
        ),
        (
            AnalysisRequest(
                question="Does unknown_col have missing values?",
                intent_name="existence_check",
                task_type_hint="descriptive",
                target="unknown_col",
                options={"existence_mode": "null_check"},
            ),
            build_profile(),
            build_null_verification_registry_without_target_requirement(),
            "supported_but_data_infeasible",
            [],
            {"unknown_target"},
            set(),
            [],
        ),
        (
            AnalysisRequest(
                question="Forecast revenue for the next 3 periods",
                task_type_hint="forecasting",
                target="revenue",
                horizon=3,
            ),
            build_profile(),
            AnalyticsRegistry(),
            "unsupported_capability",
            [],
            set(),
            set(),
            ["forecast_series"],
        ),
    ],
    ids=[
        "feasible-period-comparison",
        "partial-fallback-significance-missing-group",
        "insufficient-time-support",
        "infeasible-unknown-target",
        "unsupported-forecast-capability",
    ],
)
def test_prompt_plan_contract_status_matrix(
    analysis_request: AnalysisRequest,
    profile: DatasetProfile,
    registry: AnalyticsRegistry | None,
    expected_status: str,
    expected_missing_parameters: list[str],
    expected_issue_codes: set[str],
    expected_data_statuses: set[str],
    expected_unsupported_capabilities: list[str],
) -> None:
    contract = build_prompt_plan_contract(analysis_request, profile, registry)

    assert contract.status == expected_status
    assert contract.missing_parameters == expected_missing_parameters
    assert {issue.code for issue in contract.validation_issues} == expected_issue_codes
    assert {check.status for check in contract.data_feasibility} == expected_data_statuses
    assert contract.unsupported_capabilities == expected_unsupported_capabilities


@pytest.mark.parametrize(
    ("question", "expected_target", "expected_aggregation", "expected_group_by"),
    [
        ("Give me a list of total tickets per channel.", None, "count", ["channel"]),
        ("Count tickets by channel", None, "count", ["channel"]),
        ("Number of tickets per channel", None, "count", ["channel"]),
        ("Give me a list of total tickets per channel and priority", None, "count", ["channel", "priority"]),
        ("Show revenue by channel as table", "revenue", "sum", ["channel"]),
    ],
    ids=[
        "ticket-totals-list",
        "count-by-channel",
        "number-by-channel",
        "count-by-two-dimensions",
        "grouped-metric-table",
    ],
)
def test_engine_grouped_tabular_prompt_matrix(
    question: str,
    expected_target: str | None,
    expected_aggregation: str,
    expected_group_by: list[str],
) -> None:
    result = PromptAnalysisFrontend().analyze(build_tickets_dataset(), question)

    interpretation = result.response["interpretation"]

    assert interpretation["intent_name"] == "grouped_tabular_query"
    assert interpretation["options"]["intent_name"] == "grouped_tabular_query"
    assert interpretation["target"] == expected_target
    assert interpretation["aggregation"] == expected_aggregation
    assert interpretation["group_by"] == expected_group_by
    assert interpretation["prompt_contract"]["status"] == "supported_and_data_feasible"
    assert any(table.name == "grouped_tabular_query" for table in result.tables)


@pytest.mark.parametrize(
    (
        "question",
        "expected_intent",
        "expected_target",
        "expected_aggregation",
        "expected_group_by",
        "expected_selected_columns",
        "present_table_name",
        "absent_table_name",
    ),
    [
        ("Give me total revenue per channel", None, "revenue", "sum", ["channel"], None, "group_breakdown", "grouped_tabular_query"),
        ("What is the average revenue by channel", None, "revenue", "mean", ["channel"], None, "group_breakdown", "grouped_tabular_query"),
        ("Give me a list of all channels", "distinct_values", "channel", None, [], None, "distinct_values", "grouped_tabular_query"),
        ("Show channels by revenue", "tabular_query", None, None, [], ["channel", "revenue"], "tabular_query", "grouped_tabular_query"),
    ],
    ids=[
        "metric-total-by-group",
        "metric-average-by-group",
        "distinct-dimension-listing",
        "row-level-tabular-request",
    ],
)
def test_engine_grouped_entity_count_guard_matrix(
    question: str,
    expected_intent: str | None,
    expected_target: str | None,
    expected_aggregation: str | None,
    expected_group_by: list[str],
    expected_selected_columns: list[str] | None,
    present_table_name: str,
    absent_table_name: str,
) -> None:
    result = PromptAnalysisFrontend().analyze(build_tickets_dataset(), question)

    interpretation = result.response["interpretation"]

    assert interpretation["intent_name"] == expected_intent
    assert interpretation["target"] == expected_target
    assert interpretation["aggregation"] == expected_aggregation
    assert interpretation["group_by"] == expected_group_by
    if expected_selected_columns is not None:
        assert interpretation["options"]["selected_columns"] == expected_selected_columns
    assert any(table.name == present_table_name for table in result.tables)
    assert all(table.name != absent_table_name for table in result.tables)


@pytest.mark.parametrize(
    ("question", "expected_capability_ids", "expected_intent_name", "dataset_builder"),
    [
        ("Count tickets by channel", ["grouped_tabular_retrieval", "segmentation"], "grouped_tabular_query", build_tickets_dataset),
        ("Does priority have missing values?", ["null_verification", "verification"], "existence_check", build_tickets_dataset_with_missing_priority),
    ],
    ids=["llm-candidates-grouped-tabular", "llm-candidates-null-verification"],
)
def test_engine_llm_candidate_capability_matrix(
    question: str,
    expected_capability_ids: list[str],
    expected_intent_name: str,
    dataset_builder: Callable[[], Dataset],
) -> None:
    engine = PromptAnalysisFrontend(llm_provider=CandidateCapabilityLlmProvider())
    engine.config.llm.enabled = True

    result = engine.analyze(dataset_builder(), question)

    interpretation = result.response["interpretation"]
    prompt_contract = interpretation["prompt_contract"]
    llm_candidates = [
        candidate
        for candidate in prompt_contract["candidate_capabilities"]
        if candidate["source"] == "llm"
    ]

    assert interpretation["intent_name"] == expected_intent_name
    assert result.artifacts["request"]["options"]["candidate_capabilities"] == expected_capability_ids
    assert [candidate["capability_id"] for candidate in llm_candidates] == expected_capability_ids
    assert all(candidate["source"] == "llm" for candidate in llm_candidates)

