from __future__ import annotations

from saida.core import ResultBuilder
from saida.core.contracts import (
    AnalysisPlan,
    PlanInput,
    AnalysisRequest,
    ExecutionArtifact,
    PlanStep,
    StepInputRef,
    StepOutputSpec,
)

from .test_phase10_result_packaging import build_profile


def test_phase24_result_builder_exposes_terminal_lineage_and_secondary_outputs() -> None:
    builder = ResultBuilder()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Expose terminal lineage.",
        final_output_ref="ranked_regions",
        steps=[
            PlanStep(
                step_id="group_frame",
                tool_family="duckdb",
                action="group_frame",
                method_id="group_frame",
                family="transforms",
                parameters={"group_by": ["team"]},
                description="Prepare grouped rows.",
                output_refs=["grouped_rows"],
                outputs=[
                    StepOutputSpec(
                        output_id="grouped_rows",
                        kind="frame",
                        logical_shape="table",
                        physical_shape="recordset",
                    )
                ],
            ),
            PlanStep(
                step_id="rank_regions",
                tool_family="duckdb",
                action="rank_frame",
                method_id="rank_frame",
                family="ranking",
                parameters={"sort_by": "row_count", "limit": 1},
                description="Rank grouped rows.",
                inputs=[
                    StepInputRef(
                        input_id="grouped_rows_input",
                        source_type="step_output",
                        ref="grouped_rows",
                        expected_kind="frame",
                    )
                ],
                output_refs=["ranked_regions"],
                outputs=[
                    StepOutputSpec(
                        output_id="ranked_regions",
                        kind="frame",
                        logical_shape="table",
                        physical_shape="recordset",
                        metadata={"output_label": "Top Regions"},
                    )
                ],
            ),
            PlanStep(
                step_id="summary_metrics",
                tool_family="duckdb",
                action="dataset_summary",
                method_id="dataset_summary",
                family="diagnostic_workflows",
                parameters={"target": "resolution_hours"},
                description="Produce an auxiliary summary output.",
                inputs=[
                    StepInputRef(
                        input_id="grouped_rows_input",
                        source_type="step_output",
                        ref="grouped_rows",
                        expected_kind="frame",
                    )
                ],
                output_refs=["summary_metrics"],
                outputs=[
                    StepOutputSpec(
                        output_id="summary_metrics",
                        kind="frame",
                        logical_shape="table",
                        physical_shape="recordset",
                    )
                ],
            ),
        ],
    )
    result = builder.build_analysis_result(
        summary="Terminal result payload.",
        deterministic_summary="Terminal result payload.",
        llm_summary=None,
        summary_source="deterministic",
        metrics=[],
        tables=[],
        warnings=[],
        plan=plan,
        request=AnalysisRequest(question="Show the top region"),
        profile=build_profile(),
        trace=[],
        artifact_index={
            "grouped_rows": ExecutionArtifact(
                artifact_id="grouped_rows",
                kind="frame",
                value=[{"team": "Support", "row_count": 4}, {"team": "Billing", "row_count": 3}],
                logical_shape="table",
                physical_shape="recordset",
                producer_step_id="group_frame",
            ),
            "ranked_regions": ExecutionArtifact(
                artifact_id="ranked_regions",
                kind="frame",
                value=[{"team": "Support", "row_count": 4}],
                logical_shape="table",
                physical_shape="recordset",
                producer_step_id="rank_regions",
            ),
            "summary_metrics": ExecutionArtifact(
                artifact_id="summary_metrics",
                kind="frame",
                value=[{"metric": "resolution_hours", "mean": 12.4}],
                logical_shape="table",
                physical_shape="recordset",
                producer_step_id="summary_metrics",
            ),
        },
    )

    assert result.response["execution"]["terminal_output_ref"] == "ranked_regions"
    assert result.response["execution"]["terminal_output"]["display_name"] == "Top Regions"
    assert result.response["execution"]["secondary_outputs"][0]["name"] == "summary_metrics"
    assert result.response["execution"]["terminal_lineage"] == {
        "terminal_output_ref": "ranked_regions",
        "producer_step_id": "rank_regions",
        "upstream_step_ids": ["group_frame"],
        "upstream_output_refs": ["grouped_rows"],
        "path_step_ids": ["group_frame", "rank_regions"],
    }
    assert result.response["execution"]["graph_summary"]["leaf_output_refs"] == ["ranked_regions", "summary_metrics"]
    assert result.response["meta"]["secondary_output_refs"] == ["summary_metrics"]


def test_phase24_result_builder_uses_leaf_output_when_final_output_ref_missing_from_artifacts() -> None:
    builder = ResultBuilder()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Fallback to leaf output.",
        final_output_ref="missing_output",
        steps=[
            PlanStep(
                step_id="aggregate_value",
                tool_family="duckdb",
                action="aggregate_value",
                method_id="aggregate_value",
                family="aggregation_grouping",
                parameters={"target": "resolution_hours", "aggregation": "mean"},
                description="Aggregate a scalar result.",
                output_refs=["average_resolution"],
                outputs=[
                    StepOutputSpec(
                        output_id="average_resolution",
                        kind="scalar",
                        logical_shape="aggregate",
                        physical_shape="scalar",
                    )
                ],
            )
        ],
    )

    result = builder.build_analysis_result(
        summary="Fallback output.",
        deterministic_summary="Fallback output.",
        llm_summary=None,
        summary_source="deterministic",
        metrics=[],
        tables=[],
        warnings=[],
        plan=plan,
        request=AnalysisRequest(question="Average resolution"),
        profile=build_profile(),
        trace=[],
        artifact_index={
            "average_resolution": ExecutionArtifact(
                artifact_id="average_resolution",
                kind="scalar",
                value=12.4,
                logical_shape="aggregate",
                physical_shape="scalar",
                producer_step_id="aggregate_value",
            )
        },
    )

    assert result.response["execution"]["terminal_output_ref"] == "average_resolution"
    assert result.response["execution"]["terminal_lineage"]["producer_step_id"] == "aggregate_value"
    assert result.response["execution"]["graph_summary"]["secondary_output_count"] == 0


def test_phase24_result_builder_summarizes_primary_dataset_artifact_but_keeps_terminal_records() -> None:
    builder = ResultBuilder()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Keep explicit record results while summarizing source artifacts.",
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref="support")],
        final_output_ref="tabular_query",
        steps=[
            PlanStep(
                step_id="tabular_query",
                tool_family="duckdb",
                action="tabular_query",
                method_id="tabular_query",
                family="projection_field_selection",
                parameters={},
                description="Return requested records.",
                output_refs=["tabular_query"],
                outputs=[
                    StepOutputSpec(
                        output_id="tabular_query",
                        kind="frame",
                        logical_shape="recordset",
                        physical_shape="recordset",
                    )
                ],
            )
        ],
    )

    result = builder.build_analysis_result(
        summary="Tabular output.",
        deterministic_summary="Tabular output.",
        llm_summary=None,
        summary_source="deterministic",
        metrics=[],
        tables=[],
        warnings=[],
        plan=plan,
        request=AnalysisRequest(question="Show me the rows"),
        profile=build_profile(),
        trace=[],
        artifact_index={
            "primary_dataset": ExecutionArtifact(
                artifact_id="primary_dataset",
                kind="frame",
                value=[
                    {"ticket_id": "T1", "team": "Support", "resolution_hours": 4.0},
                    {"ticket_id": "T2", "team": "Billing", "resolution_hours": 7.0},
                ],
                logical_shape="table",
                physical_shape="recordset",
                producer_step_id=None,
            ),
            "tabular_query": ExecutionArtifact(
                artifact_id="tabular_query",
                kind="frame",
                value=[
                    {"ticket_id": "T1", "team": "Support", "resolution_hours": 4.0},
                    {"ticket_id": "T2", "team": "Billing", "resolution_hours": 7.0},
                ],
                logical_shape="recordset",
                physical_shape="recordset",
                producer_step_id="tabular_query",
            ),
        },
    )

    primary_dataset_payload = result.response["execution"]["artifact_index"]["primary_dataset"]

    assert primary_dataset_payload["summarized"] is True
    assert primary_dataset_payload["value"] == {
        "row_count": 2,
        "column_count": 3,
        "columns": ["ticket_id", "team", "resolution_hours"],
    }
    assert result.response["result"]["name"] == "tabular_query"
    assert result.response["result"]["value"] == [
        {"ticket_id": "T1", "team": "Support", "resolution_hours": 4.0},
        {"ticket_id": "T2", "team": "Billing", "resolution_hours": 7.0},
    ]
