from __future__ import annotations

from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec

from tests.helpers.factories import build_sales_dataset


def test_phase25_executes_deep_transform_graph_end_to_end() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Stress the DAG engine with a deep transform chain.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="final_ranked_rows",
        expected_result_shape="table",
        final_output_ref="final_ranked_rows",
        steps=[
            _frame_step(
                step_id="filter_west",
                method_id="filter_frame",
                family="selection_filtering",
                parameters={"filters": {"region": "West"}},
                input_ref="primary_dataset",
                input_source_type="plan_input",
                input_kind="dataset",
                output_ref="west_rows",
            ),
            _frame_step(
                step_id="derive_scaled",
                method_id="derive_column",
                family="transformation",
                parameters={"target": "revenue_scaled", "expression": {"op": "multiply", "source": "revenue", "value": 2}},
                input_ref="west_rows",
                input_source_type="step_output",
                input_kind="frame",
                output_ref="scaled_rows",
            ),
            _frame_step(
                step_id="project_selected",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["posted_at", "region", "revenue", "revenue_scaled"]},
                input_ref="scaled_rows",
                input_source_type="step_output",
                input_kind="frame",
                output_ref="projected_rows",
            ),
            _frame_step(
                step_id="sort_desc",
                method_id="sort_frame",
                family="selection_filtering",
                parameters={"sort_by": "posted_at", "sort_direction": "desc"},
                input_ref="projected_rows",
                input_source_type="step_output",
                input_kind="frame",
                output_ref="sorted_rows",
            ),
            _frame_step(
                step_id="limit_recent",
                method_id="limit_frame",
                family="selection_filtering",
                parameters={"limit": 2},
                input_ref="sorted_rows",
                input_source_type="step_output",
                input_kind="frame",
                output_ref="limited_rows",
            ),
            _frame_step(
                step_id="derive_rank_metric",
                method_id="derive_column",
                family="transformation",
                parameters={"target": "rank_metric", "expression": {"op": "add", "source": "revenue_scaled", "value": 1}},
                input_ref="limited_rows",
                input_source_type="step_output",
                input_kind="frame",
                output_ref="rank_metric_rows",
            ),
            _frame_step(
                step_id="sort_metric",
                method_id="sort_frame",
                family="selection_filtering",
                parameters={"sort_by": "rank_metric", "sort_direction": "desc"},
                input_ref="rank_metric_rows",
                input_source_type="step_output",
                input_kind="frame",
                output_ref="metric_sorted_rows",
            ),
            _frame_step(
                step_id="project_rank_cols",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["posted_at", "rank_metric"]},
                input_ref="metric_sorted_rows",
                input_source_type="step_output",
                input_kind="frame",
                output_ref="projected_rank_rows",
            ),
            _frame_step(
                step_id="rank_final",
                method_id="rank_frame",
                family="ranking",
                parameters={"sort_by": "rank_metric", "sort_direction": "desc", "limit": 2},
                input_ref="projected_rank_rows",
                input_source_type="step_output",
                input_kind="frame",
                output_ref="final_ranked_rows",
            ),
        ],
    )

    result = engine.execute_plan(dataset, plan)

    assert result.response["execution"]["step_count"] == 9
    assert result.response["execution"]["graph_summary"]["artifact_count"] >= 10
    assert result.response["execution"]["terminal_output_ref"] == "final_ranked_rows"
    assert len(result.node_results) == 9
    assert result.response["result"]["value"] == [
        {"rank": 1, "posted_at": "2026-02-01", "rank_metric": 221.0},
        {"rank": 2, "posted_at": "2025-12-01", "rank_metric": 181.0},
    ]


def _frame_step(
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

