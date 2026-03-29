from __future__ import annotations

import pytest

from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec
from saida.exceptions import PlanningError

from .factories import build_sales_dataset, build_support_dataset


def test_phase21_rejects_scalar_output_as_frame_input() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="A scalar reduction cannot feed a frame transform.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="projected_rows",
        expected_result_shape="table",
        final_output_ref="projected_rows",
        steps=[
            _step(
                step_id="row_count",
                tool_family="duckdb",
                method_id="row_count",
                family="aggregation_grouping",
                parameters={},
                inputs=[_input("dataset_input", "plan_input", "primary_dataset", "dataset")],
                output_ref="row_count_value",
                output_kind="scalar",
                logical_shape="scalar",
                physical_shape="scalar",
                semantic_kind="scalar",
            ),
            _step(
                step_id="project_count",
                tool_family="duckdb",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["ticket_id"]},
                inputs=[_input("frame_input", "step_output", "row_count_value", "frame")],
                output_ref="projected_rows",
                output_kind="frame",
                logical_shape="table",
                physical_shape="recordset",
            ),
        ],
    )

    with pytest.raises(PlanningError, match="resolved output kind is 'scalar'"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_phase21_rejects_fan_in_for_non_merge_method() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Only join and union may merge multiple upstream artifacts.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="aggregated_rows",
        expected_result_shape="table",
        final_output_ref="aggregated_rows",
        steps=[
            _step(
                step_id="west_rows",
                tool_family="duckdb",
                method_id="filter_frame",
                family="selection_filtering",
                parameters={"filters": {"region": "West"}},
                inputs=[_input("dataset_input", "plan_input", "primary_dataset", "dataset")],
                output_ref="west_rows",
                output_kind="frame",
                logical_shape="table",
                physical_shape="recordset",
            ),
            _step(
                step_id="east_rows",
                tool_family="duckdb",
                method_id="filter_frame",
                family="selection_filtering",
                parameters={"filters": {"region": "East"}},
                inputs=[_input("dataset_input", "plan_input", "primary_dataset", "dataset")],
                output_ref="east_rows",
                output_kind="frame",
                logical_shape="table",
                physical_shape="recordset",
            ),
            _step(
                step_id="bad_merge",
                tool_family="duckdb",
                method_id="aggregate_frame",
                family="transformation",
                parameters={"aggregation": "count"},
                inputs=[
                    _input("left_input", "step_output", "west_rows", "frame"),
                    _input("right_input", "step_output", "east_rows", "frame"),
                ],
                output_ref="aggregated_rows",
                output_kind="frame",
                logical_shape="table",
                physical_shape="recordset",
                semantic_kind="grouped_table",
            ),
        ],
    )

    with pytest.raises(PlanningError, match="does not support fan-in merging"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_phase21_rejects_time_aware_method_without_time_series_input() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Period comparison should require a time-series upstream artifact when chained.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="period_delta",
        expected_result_shape="table",
        final_output_ref="period_delta",
        steps=[
            _step(
                step_id="project_rows",
                tool_family="duckdb",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["posted_at", "revenue"]},
                inputs=[_input("dataset_input", "plan_input", "primary_dataset", "dataset")],
                output_ref="projected_rows",
                output_kind="frame",
                logical_shape="table",
                physical_shape="recordset",
                semantic_kind="table",
            ),
            _step(
                step_id="period_compare",
                tool_family="duckdb",
                method_id="period_comparison",
                family="period_comparison",
                parameters={
                    "target": "revenue",
                    "time_column": "posted_at",
                    "time_reference": {"mode": "latest_complete_period"},
                    "bucket": "month",
                    "aggregation": "sum",
                },
                inputs=[_input("time_input", "step_output", "projected_rows", "frame")],
                output_ref="period_delta",
                output_kind="frame",
                logical_shape="timeseries",
                physical_shape="recordset",
                semantic_kind="time_series",
            ),
        ],
    )

    with pytest.raises(PlanningError, match="requires a time_series upstream artifact"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_phase21_accepts_time_aware_method_with_time_series_input() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="A time bucket artifact may feed a time-aware downstream node.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="period_delta",
        expected_result_shape="table",
        final_output_ref="period_delta",
        steps=[
            _step(
                step_id="bucket_rows",
                tool_family="duckdb",
                method_id="time_bucket_frame",
                family="transformation",
                parameters={"time_column": "posted_at", "bucket": "month"},
                inputs=[_input("dataset_input", "plan_input", "primary_dataset", "dataset")],
                output_ref="bucketed_rows",
                output_kind="frame",
                logical_shape="table",
                physical_shape="recordset",
                semantic_kind="time_series",
            ),
            _step(
                step_id="period_compare",
                tool_family="duckdb",
                method_id="period_comparison",
                family="period_comparison",
                parameters={
                    "target": "revenue",
                    "time_column": "posted_at",
                    "time_reference": {"mode": "latest_complete_period"},
                    "bucket": "month",
                    "aggregation": "sum",
                },
                inputs=[_input("time_input", "step_output", "bucketed_rows", "frame")],
                output_ref="period_delta",
                output_kind="frame",
                logical_shape="timeseries",
                physical_shape="recordset",
                semantic_kind="time_series",
            ),
        ],
    )

    engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def test_phase21_rejects_statistical_method_consuming_verification_output() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Statistical methods must consume frame-like artifacts, not verification payloads.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="significance_result",
        expected_result_shape="table",
        final_output_ref="significance_result",
        steps=[
            _step(
                step_id="column_check",
                tool_family="metadata",
                method_id="column_presence_check",
                family="validation_verification",
                parameters={"requested_column": "priority"},
                inputs=[_input("dataset_input", "plan_input", "primary_dataset", "dataset")],
                output_ref="column_check_result",
                output_kind="verification",
                logical_shape="verification",
                physical_shape="object",
                semantic_kind="verification_result",
            ),
            _step(
                step_id="run_significance",
                tool_family="stats",
                method_id="significance_inference",
                family="statistical_inference",
                parameters={"target": "resolution_hours", "group_by": ["team"], "alpha": 0.05},
                inputs=[_input("stats_input", "step_output", "column_check_result", "frame")],
                output_ref="significance_result",
                output_kind="frame",
                logical_shape="statistical_test",
                physical_shape="recordset",
                semantic_kind="statistical_test",
            ),
        ],
    )

    with pytest.raises(PlanningError, match="resolved output kind is 'verification'"):
        engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=engine.router)


def _step(
    *,
    step_id: str,
    tool_family: str,
    method_id: str,
    family: str,
    parameters: dict[str, object],
    inputs: list[StepInputRef],
    output_ref: str,
    output_kind: str,
    logical_shape: str,
    physical_shape: str,
    semantic_kind: str | None = None,
) -> PlanStep:
    expected_output = {
        "output_id": output_ref,
        "logical_shape": logical_shape,
        "physical_shape": physical_shape,
    }
    if semantic_kind is not None:
        expected_output["semantic_kind"] = semantic_kind
    return PlanStep(
        step_id=step_id,
        tool_family=tool_family,
        action=method_id,
        method_id=method_id,
        family=family,
        parameters=parameters,
        description=f"Execute {method_id}.",
        inputs=inputs,
        output_refs=[output_ref],
        outputs=[
            StepOutputSpec(
                output_id=output_ref,
                kind=output_kind,
                logical_shape=logical_shape,
                physical_shape=physical_shape,
                semantic_kind=semantic_kind,
            )
        ],
        expected_output=expected_output,
    )


def _input(input_id: str, source_type: str, ref: str, expected_kind: str) -> StepInputRef:
    return StepInputRef(input_id=input_id, source_type=source_type, ref=ref, expected_kind=expected_kind)
