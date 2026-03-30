from __future__ import annotations

from saida.core.contracts import (
    AnalysisPlan,
    AnalysisResult,
    ExecutionArtifact,
    NodeExecutionResult,
    PlanStep,
    StepInputRef,
    StepOutputSpec,
)


def test_plan_step_supports_explicit_input_and_output_contracts() -> None:
    step = PlanStep(
        step_id="rank_regions",
        tool_family="duckdb",
        action="ranked_breakdown",
        method_id="ranked_breakdown",
        family="ranking",
        parameters={"target": "revenue", "group_by": ["region"], "aggregation": "sum"},
        description="Rank grouped revenue by region.",
        inputs=[
            StepInputRef(
                input_id="source_table",
                source_type="plan_input",
                ref="primary_dataset",
                expected_kind="dataset",
            )
        ],
        outputs=[
            StepOutputSpec(
                output_id="ranked_regions",
                kind="frame",
                logical_shape="table",
                physical_shape="recordset",
            )
        ],
    )

    payload = step.to_dict()

    assert payload["inputs"][0]["ref"] == "primary_dataset"
    assert payload["inputs"][0]["expected_kind"] == "dataset"
    assert payload["outputs"][0]["output_id"] == "ranked_regions"
    assert payload["outputs"][0]["kind"] == "frame"
    assert payload["outputs"][0]["logical_shape"] == "table"


def test_analysis_plan_supports_final_output_ref() -> None:
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Compute a grouped table and mark the final output explicitly.",
        final_output_ref="ranked_regions",
        steps=[
            PlanStep(
                step_id="rank_regions",
                tool_family="duckdb",
                action="ranked_breakdown",
                method_id="ranked_breakdown",
                family="ranking",
                parameters={"target": "revenue", "group_by": ["region"], "aggregation": "sum"},
                description="Rank grouped revenue by region.",
                outputs=[StepOutputSpec(output_id="ranked_regions", kind="frame", logical_shape="table")],
            )
        ],
    )

    payload = plan.to_dict()

    assert payload["final_output_ref"] == "ranked_regions"
    assert payload["steps"][0]["outputs"][0]["output_id"] == "ranked_regions"


def test_analysis_result_supports_node_results_and_artifact_index() -> None:
    result = AnalysisResult(
        summary="Ranked grouped revenue.",
        deterministic_summary="Ranked grouped revenue.",
        llm_summary=None,
        summary_source="deterministic",
        metrics=[],
        tables=[],
        warnings=[],
        plan=AnalysisPlan(task_type="descriptive", rationale="Synthetic."),
        trace=[],
        node_results=[
            NodeExecutionResult(
                step_id="rank_regions",
                status="completed",
                consumed_inputs=["primary_dataset"],
                produced_outputs=["ranked_regions"],
            )
        ],
        artifact_index={
            "ranked_regions": ExecutionArtifact(
                artifact_id="ranked_regions",
                kind="frame",
                value={"rows": 2},
                logical_shape="table",
                physical_shape="recordset",
                producer_step_id="rank_regions",
            )
        },
    )

    assert result.node_results[0].step_id == "rank_regions"
    assert result.node_results[0].produced_outputs == ["ranked_regions"]
    assert result.artifact_index["ranked_regions"].producer_step_id == "rank_regions"
    assert result.artifact_index["ranked_regions"].kind == "frame"

