from __future__ import annotations

from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec

from .factories import build_sales_dataset


def test_phase16_executes_filter_select_sort_limit_transform_chain() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Use transform nodes to produce the latest West rows.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="limited_rows",
        expected_result_shape="table",
        final_output_ref="limited_rows",
        steps=[
            _step(
                step_id="filter_west",
                method_id="filter_frame",
                family="selection_filtering",
                parameters={"filters": {"region": "West"}},
                input_ref="primary_dataset",
                input_source_type="plan_input",
                input_kind="dataset",
                output_ref="west_rows",
            ),
            _step(
                step_id="project_columns",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["posted_at", "revenue"]},
                input_ref="west_rows",
                input_source_type="step_output",
                input_kind="frame",
                output_ref="projected_rows",
            ),
            _step(
                step_id="sort_rows",
                method_id="sort_frame",
                family="selection_filtering",
                parameters={"sort_by": "posted_at", "sort_direction": "desc"},
                input_ref="projected_rows",
                input_source_type="step_output",
                input_kind="frame",
                output_ref="sorted_rows",
            ),
            _step(
                step_id="limit_rows",
                method_id="limit_frame",
                family="selection_filtering",
                parameters={"limit": 2},
                input_ref="sorted_rows",
                input_source_type="step_output",
                input_kind="frame",
                output_ref="limited_rows",
            ),
        ],
    )

    result = engine.execute_plan(dataset, plan)
    records = result.response["result"]["value"]

    assert result.response["result"]["name"] == "limited_rows"
    assert result.response["result"]["logical_shape"] == "table"
    assert records == [
        {"posted_at": "2026-02-01", "revenue": 110.0},
        {"posted_at": "2025-12-01", "revenue": 90.0},
    ]


def test_phase16_executes_group_aggregate_rank_transform_chain() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Group rows, aggregate revenue, and rank regions.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="ranked_regions",
        expected_result_shape="table",
        final_output_ref="ranked_regions",
        steps=[
            _step(
                step_id="group_regions",
                method_id="group_frame",
                family="transformation",
                parameters={"group_by": ["region"]},
                input_ref="primary_dataset",
                input_source_type="plan_input",
                input_kind="dataset",
                output_ref="grouped_rows",
            ),
            _step(
                step_id="aggregate_revenue",
                method_id="aggregate_frame",
                family="transformation",
                parameters={"target": "revenue", "aggregation": "sum"},
                input_ref="grouped_rows",
                input_source_type="step_output",
                input_kind="frame",
                output_ref="aggregated_regions",
            ),
            _step(
                step_id="rank_regions",
                method_id="rank_frame",
                family="ranking",
                parameters={"sort_by": "aggregate_value", "sort_direction": "desc"},
                input_ref="aggregated_regions",
                input_source_type="step_output",
                input_kind="frame",
                output_ref="ranked_regions",
            ),
        ],
    )

    result = engine.execute_plan(dataset, plan)
    records = result.response["result"]["value"]

    assert records == [
        {"rank": 1, "region": "East", "aggregate_value": 330.0},
        {"rank": 2, "region": "West", "aggregate_value": 300.0},
    ]


def test_phase16_executes_derive_and_time_bucket_transforms() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Derive a scaled revenue column and add quarter buckets.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="bucketed_rows",
        expected_result_shape="table",
        final_output_ref="bucketed_rows",
        steps=[
            _step(
                step_id="derive_revenue",
                method_id="derive_column",
                family="transformation",
                parameters={"target": "revenue_twice", "expression": {"op": "multiply", "source": "revenue", "value": 2}},
                input_ref="primary_dataset",
                input_source_type="plan_input",
                input_kind="dataset",
                output_ref="derived_rows",
            ),
            _step(
                step_id="bucket_quarter",
                method_id="time_bucket_frame",
                family="transformation",
                parameters={"time_column": "posted_at", "bucket": "quarter"},
                input_ref="derived_rows",
                input_source_type="step_output",
                input_kind="frame",
                output_ref="bucketed_rows",
            ),
        ],
    )

    result = engine.execute_plan(dataset, plan)
    records = result.response["result"]["value"]

    assert records[0]["revenue_twice"] == 200.0
    assert {record["quarter"] for record in records} == {"2025-Q4", "2026-Q1"}


def _step(
    *,
    step_id: str,
    method_id: str,
    family: str,
    parameters: dict[str, object],
    input_ref: str,
    input_source_type: str,
    input_kind: str,
    output_ref: str,
) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        tool_family="duckdb",
        action=method_id,
        method_id=method_id,
        family=family,
        parameters=parameters,
        description=f"Execute {method_id}.",
        inputs=[StepInputRef(input_id="frame_input", source_type=input_source_type, ref=input_ref, expected_kind=input_kind)],
        output_refs=[output_ref],
        outputs=[StepOutputSpec(output_id=output_ref, kind="frame", logical_shape="table", physical_shape="recordset")],
        expected_output={"output_id": output_ref, "logical_shape": "table", "physical_shape": "recordset"},
    )
