from __future__ import annotations

import pandas as pd

from saida.results import ResultBuilder
from saida.schemas import (
    AnalysisPlan,
    AnalysisRequest,
    ColumnProfile,
    DatasetProfile,
    ExecutionTraceEvent,
    ForecastResult,
    Metric,
    ModelTrainingResult,
    PlanStep,
    TableArtifact,
)


def build_profile() -> DatasetProfile:
    return DatasetProfile(
        dataset_name="sales",
        row_count=3,
        column_count=3,
        columns=[
            ColumnProfile(
                name="revenue",
                inferred_type="float",
                nullable=False,
                null_ratio=0.0,
                unique_count=3,
                distinct_ratio=1.0,
                sample_values=[100.0],
                is_measure_candidate=True,
            ),
            ColumnProfile(
                name="region",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=2,
                distinct_ratio=0.67,
                sample_values=["West"],
                is_dimension_candidate=True,
            ),
            ColumnProfile(
                name="posted_at",
                inferred_type="datetime",
                nullable=False,
                null_ratio=0.0,
                unique_count=3,
                distinct_ratio=1.0,
                sample_values=["2026-03-01"],
                is_time_candidate=True,
            ),
        ],
        measure_columns=["revenue"],
        dimension_columns=["region"],
        time_columns=["posted_at"],
        identifier_columns=[],
        warnings=["profile warning"],
    )


def test_build_analysis_result_populates_artifacts() -> None:
    builder = ResultBuilder()
    plan = AnalysisPlan(
        task_type="diagnostic",
        rationale="Test plan.",
        steps=[
            PlanStep(
                step_id="summary_metrics",
                tool_family="duckdb",
                action="dataset_summary",
                parameters={},
                description="Compute summary metrics.",
            )
        ],
    )
    request = AnalysisRequest(question="Why did revenue drop?", task_type_hint="diagnostic", target="revenue")
    metrics = [Metric(name="row_count", value=3), Metric(name="revenue_sum", value=270.0)]
    tables = [
        TableArtifact(
            name="dataset_preview",
            description="First rows.",
            dataframe=pd.DataFrame({"revenue": [100.0, 90.0]}),
        )
    ]
    trace = [
        ExecutionTraceEvent(stage="adapter", message="loaded"),
        ExecutionTraceEvent(stage="results", message="packaged"),
    ]

    result = builder.build_analysis_result(
        summary="Test summary.",
        deterministic_summary="Deterministic summary.",
        llm_summary="LLM summary.",
        summary_source="llm",
        metrics=metrics,
        tables=tables,
        warnings=["request warning"],
        plan=plan,
        request=request,
        profile=build_profile(),
        trace=trace,
    )

    assert result.summary == "Test summary."
    assert result.deterministic_summary == "Deterministic summary."
    assert result.llm_summary == "LLM summary."
    assert result.summary_source == "llm"
    assert result.artifacts["request"]["target"] == "revenue"
    assert result.artifacts["metric_lookup"]["revenue_sum"] == 270.0
    assert result.artifacts["table_index"]["dataset_preview"]["rows"] == 2
    assert result.artifacts["profile"]["dataset_name"] == "sales"
    assert result.artifacts["warning_count"] == 1
    assert result.artifacts["trace_stages"] == ["adapter", "results"]
    assert result.artifacts["plan_step_ids"] == ["summary_metrics"]
    assert result.response["schema_version"] == "saida.response.v2"
    assert result.response["status"] == "ok"
    assert result.response["request"]["question"] == "Why did revenue drop?"
    assert result.response["request"]["dataset"]["name"] == "sales"
    assert result.response["interpretation"]["target"] == "revenue"
    assert result.response["execution"]["step_count"] == 1
    assert result.response["execution"]["steps"][0]["action"] == "dataset_summary"
    assert result.response["meta"]["metric_lookup"]["revenue_sum"] == 270.0
    assert result.response["tables"][0]["name"] == "dataset_preview"
    assert result.response["result"]["name"] == "dataset_preview"
    assert result.to_response_dict()["reasoning"]["summary"] == "Test summary."
    assert result.response["reasoning"]["deterministic_summary"] == "Deterministic summary."
    assert result.response["reasoning"]["llm_summary"] == "LLM summary."
    assert result.response["reasoning"]["summary_source"] == "llm"


def test_build_train_and_forecast_results_keep_payloads() -> None:
    builder = ResultBuilder()

    train_result = builder.build_train_result(
        summary="Training placeholder.",
        training=ModelTrainingResult(model_name="baseline", problem_type="regression", target="revenue"),
        trace=[ExecutionTraceEvent(stage="ml", message="placeholder")],
    )
    forecast_result = builder.build_forecast_result(
        summary="Forecast placeholder.",
        forecast=ForecastResult(target="revenue", horizon=3, forecast_values=[1.0, 2.0, 3.0]),
        trace=[ExecutionTraceEvent(stage="ml", message="placeholder")],
    )

    assert train_result.training.model_name == "baseline"
    assert train_result.trace[0].stage == "ml"
    assert forecast_result.forecast.horizon == 3
    assert forecast_result.forecast.forecast_values == [1.0, 2.0, 3.0]


def test_build_analysis_result_handles_empty_metrics_and_tables() -> None:
    builder = ResultBuilder()
    result = builder.build_analysis_result(
        summary="Empty result.",
        deterministic_summary="Empty result.",
        llm_summary=None,
        summary_source="deterministic",
        metrics=[],
        tables=[],
        warnings=[],
        plan=AnalysisPlan(task_type="descriptive", rationale="Empty."),
        request=AnalysisRequest(question="Show revenue"),
        profile=build_profile(),
        trace=[],
    )

    assert result.artifacts["metric_lookup"] == {}
    assert result.artifacts["table_index"] == {}
    assert result.artifacts["trace_stages"] == []
    assert result.response["meta"]["metrics"] == []
    assert result.response["tables"] == []
    assert result.response["reasoning"]["summary_source"] == "deterministic"
    assert result.response["result"]["logical_shape"] == "empty"


def test_build_analysis_result_uses_last_metric_value_for_lookup() -> None:
    builder = ResultBuilder()

    result = builder.build_analysis_result(
        summary="Duplicate metric names.",
        deterministic_summary="Duplicate metric names.",
        llm_summary=None,
        summary_source="deterministic",
        metrics=[Metric(name="row_count", value=1), Metric(name="row_count", value=2)],
        tables=[],
        warnings=[],
        plan=AnalysisPlan(task_type="descriptive", rationale="Duplicate metrics."),
        request=AnalysisRequest(question="Show revenue"),
        profile=build_profile(),
        trace=[],
    )

    assert result.artifacts["metric_lookup"]["row_count"] == 2
    assert result.response["meta"]["metric_lookup"]["row_count"] == 2
    assert result.response["result"]["name"] == "row_count"
    assert result.response["result"]["value"] == 2


def test_build_analysis_result_indexes_multiple_tables() -> None:
    builder = ResultBuilder()
    tables = [
        TableArtifact(name="first", description="First table", dataframe=pd.DataFrame({"value": [1]})),
        TableArtifact(name="second", description="Second table", dataframe=pd.DataFrame({"value": [1, 2]})),
    ]

    result = builder.build_analysis_result(
        summary="Multiple tables.",
        deterministic_summary="Multiple tables.",
        llm_summary=None,
        summary_source="deterministic",
        metrics=[],
        tables=tables,
        warnings=["warning one", "warning two"],
        plan=AnalysisPlan(task_type="descriptive", rationale="Multiple tables."),
        request=AnalysisRequest(question="Show revenue"),
        profile=build_profile(),
        trace=[ExecutionTraceEvent(stage="results", message="packaged")],
    )

    assert result.artifacts["table_index"]["first"]["rows"] == 1
    assert result.artifacts["table_index"]["second"]["rows"] == 2
    assert result.artifacts["warning_count"] == 2
    assert result.response["meta"]["warning_count"] == 2
    assert len(result.response["tables"]) == 2


import pytest


_RESULT_BUILDER_CASES = [
    (
        index,
        [Metric(name="row_count", value=index), Metric(name="revenue_sum", value=float(index * 10))],
        [
            TableArtifact(
                name=f"table_{index}",
                description="Synthetic table.",
                dataframe=pd.DataFrame({"value": list(range(index % 3 + 1))}),
            )
        ],
    )
    for index in range(1, 96)
]


@pytest.mark.parametrize(("case_id", "metrics", "tables"), _RESULT_BUILDER_CASES)
def test_result_builder_handles_many_metric_and_table_shapes(
    case_id: int,
    metrics: list[Metric],
    tables: list[TableArtifact],
) -> None:
    builder = ResultBuilder()
    result = builder.build_analysis_result(
        summary=f"Summary {case_id}",
        deterministic_summary=f"Summary {case_id}",
        llm_summary=None,
        summary_source="deterministic",
        metrics=metrics,
        tables=tables,
        warnings=["warning"] if case_id % 2 == 0 else [],
        plan=AnalysisPlan(task_type="descriptive", rationale="Synthetic."),
        request=AnalysisRequest(question=f"Question {case_id}", target="revenue"),
        profile=build_profile(),
        trace=[ExecutionTraceEvent(stage="results", message="packaged")],
    )

    assert result.summary == f"Summary {case_id}"
    assert result.artifacts["metric_lookup"]["row_count"] == case_id
    assert list(result.artifacts["table_index"].keys()) == [f"table_{case_id}"]
    assert result.response["request"]["dataset"]["name"] == "sales"
    assert result.response["request"]["question"] == f"Question {case_id}"
    assert result.response["meta"]["metric_lookup"]["row_count"] == case_id
