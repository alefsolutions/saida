from __future__ import annotations

from time import perf_counter

from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec

from tests.helpers.factories import build_sales_dataset


def test_phase25_deep_graph_completes_within_smoke_budget() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Exercise a longer DAG under a gentle performance budget.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="summary_metrics",
        expected_result_shape="table",
        final_output_ref="summary_metrics",
        steps=[
            _frame_step("filter_east", "filter_frame", "selection_filtering", {"filters": {"region": "East"}}, "primary_dataset", "plan_input", "dataset", "east_rows"),
            _frame_step("derive_bonus", "derive_column", "transformation", {"target": "revenue_bonus", "expression": {"op": "add", "source": "revenue", "value": 5}}, "east_rows", "step_output", "frame", "bonus_rows"),
            _frame_step("project_bonus", "select_columns", "selection_filtering", {"selected_columns": ["posted_at", "region", "revenue_bonus"]}, "bonus_rows", "step_output", "frame", "projected_bonus_rows"),
            _frame_step("sort_bonus", "sort_frame", "selection_filtering", {"sort_by": "posted_at", "sort_direction": "asc"}, "projected_bonus_rows", "step_output", "frame", "sorted_bonus_rows"),
            _frame_step("limit_bonus", "limit_frame", "selection_filtering", {"limit": 3}, "sorted_bonus_rows", "step_output", "frame", "limited_bonus_rows"),
            _frame_step("derive_bonus_twice", "derive_column", "transformation", {"target": "revenue_bonus_twice", "expression": {"op": "multiply", "source": "revenue_bonus", "value": 2}}, "limited_bonus_rows", "step_output", "frame", "bonus_twice_rows"),
            _frame_step("project_summary_source", "select_columns", "selection_filtering", {"selected_columns": ["revenue_bonus_twice"]}, "bonus_twice_rows", "step_output", "frame", "summary_source_rows"),
            PlanStep(
                step_id="summary_metrics",
                tool_family="stats",
                action="numeric_summary",
                method_id="numeric_summary",
                family="diagnostic_workflows",
                parameters={},
                description="Produce a summary table from the prepared frame.",
                inputs=[StepInputRef(input_id="frame_input", source_type="step_output", ref="summary_source_rows", expected_kind="frame")],
                output_refs=["summary_metrics"],
                outputs=[StepOutputSpec(output_id="summary_metrics", kind="frame", logical_shape="table", physical_shape="recordset")],
                expected_output={"output_id": "summary_metrics", "logical_shape": "table", "physical_shape": "recordset"},
            ),
        ],
    )

    started = perf_counter()
    result = engine.execute_plan(dataset, plan)
    elapsed = perf_counter() - started

    assert elapsed < 5.0
    assert result.response["execution"]["terminal_output_ref"] == "summary_metrics"
    assert result.response["execution"]["graph_summary"]["step_count"] == 8


def _frame_step(
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

