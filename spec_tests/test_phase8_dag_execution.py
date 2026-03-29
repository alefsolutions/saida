from __future__ import annotations

from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec
from .factories import build_support_dataset


def test_engine_builds_execution_dependencies_from_step_output_inputs() -> None:
    engine = Saida()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Build dependencies from artifact references.",
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref="support")],
        steps=[
            PlanStep(
                step_id="first_count",
                tool_family="duckdb",
                action="row_count",
                method_id="row_count",
                family="aggregation_grouping",
                parameters={},
                description="Count all rows.",
                outputs=[StepOutputSpec(output_id="count_all", kind="scalar", logical_shape="count")],
                output_refs=["count_all"],
            ),
            PlanStep(
                step_id="summary",
                tool_family="stats",
                action="numeric_summary",
                method_id="numeric_summary",
                family="diagnostic_workflows",
                parameters={},
                description="Summarize numeric columns.",
                inputs=[StepInputRef(input_id="count_input", source_type="step_output", ref="count_all")],
            ),
        ],
    )

    dependencies = engine._build_execution_dependencies(plan)

    assert dependencies == {
        "first_count": set(),
        "summary": {"first_count"},
    }


def test_engine_execute_plan_records_node_results_and_artifact_index_for_dag_style_plan() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Project rows and summarize numeric fields with explicit graph metadata.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="numeric_summary_table",
        expected_result_shape="table",
        final_output_ref="numeric_summary_table",
        steps=[
            PlanStep(
                step_id="project_rows",
                tool_family="duckdb",
                action="select_columns",
                method_id="select_columns",
                family="selection_filtering",
                parameters={"selected_columns": ["resolution_hours", "csat_score"]},
                description="Project numeric columns for downstream stats.",
                inputs=[StepInputRef(input_id="dataset_input", source_type="plan_input", ref="primary_dataset", expected_kind="dataset")],
                output_refs=["projected_rows"],
                outputs=[StepOutputSpec(output_id="projected_rows", kind="frame", logical_shape="table", physical_shape="recordset")],
                expected_output={
                    "output_id": "projected_rows",
                    "logical_shape": "table",
                    "physical_shape": "recordset",
                },
            ),
            PlanStep(
                step_id="numeric_summary",
                tool_family="stats",
                action="numeric_summary",
                method_id="numeric_summary",
                family="diagnostic_workflows",
                parameters={},
                description="Summarize numeric columns.",
                inputs=[StepInputRef(input_id="frame_input", source_type="step_output", ref="projected_rows", expected_kind="frame")],
                output_refs=["numeric_summary_table"],
                outputs=[
                    StepOutputSpec(
                        output_id="numeric_summary_table",
                        kind="frame",
                        logical_shape="table",
                        physical_shape="recordset",
                    )
                ],
                expected_output={
                    "output_id": "numeric_summary_table",
                    "logical_shape": "table",
                    "physical_shape": "recordset",
                },
            ),
        ],
    )

    result = engine.execute_plan(dataset, plan)

    assert [node_result.step_id for node_result in result.node_results] == ["project_rows", "numeric_summary"]
    assert result.node_results[0].produced_outputs == ["projected_rows"]
    assert result.node_results[1].consumed_inputs == ["frame_input"]
    assert "primary_dataset" in result.artifact_index
    assert "projected_rows" in result.artifact_index
    assert "numeric_summary_table" in result.artifact_index
    assert result.artifact_index["projected_rows"].kind == "frame"
    assert result.artifact_index["numeric_summary_table"].kind == "frame"
    assert result.response["execution"]["final_output_ref"] == "numeric_summary_table"
