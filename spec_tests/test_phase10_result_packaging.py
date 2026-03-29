from __future__ import annotations

from saida.core import ResultBuilder
from saida.core.contracts import (
    AnalysisPlan,
    AnalysisRequest,
    ColumnProfile,
    DatasetProfile,
    ExecutionArtifact,
    NodeExecutionResult,
    PlanStep,
)


def build_profile() -> DatasetProfile:
    return DatasetProfile(
        dataset_name="support",
        row_count=7,
        column_count=3,
        columns=[
            ColumnProfile(
                name="ticket_id",
                inferred_type="string",
                nullable=False,
                null_ratio=0.0,
                unique_count=7,
                distinct_ratio=1.0,
            ),
            ColumnProfile(
                name="team",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=2,
                distinct_ratio=0.29,
            ),
            ColumnProfile(
                name="resolution_hours",
                inferred_type="float",
                nullable=False,
                null_ratio=0.0,
                unique_count=7,
                distinct_ratio=1.0,
            ),
        ],
        measure_columns=["resolution_hours"],
        dimension_columns=["team"],
        time_columns=[],
        identifier_columns=["ticket_id"],
    )


def test_result_builder_uses_final_output_ref_from_artifact_index_as_primary_result() -> None:
    builder = ResultBuilder()
    result = builder.build_analysis_result(
        summary="Graph result.",
        deterministic_summary="Graph result.",
        llm_summary=None,
        summary_source="deterministic",
        metrics=[],
        tables=[],
        warnings=[],
        plan=AnalysisPlan(
            task_type="descriptive",
            rationale="Use the final artifact as the main result.",
            final_output_ref="ranked_regions",
            steps=[
                PlanStep(
                    step_id="rank_regions",
                    tool_family="duckdb",
                    action="ranked_breakdown",
                    method_id="ranked_breakdown",
                    family="ranking",
                    parameters={},
                    description="Rank regions.",
                    output_refs=["ranked_regions"],
                )
            ],
        ),
        request=AnalysisRequest(question="Rank regions"),
        profile=build_profile(),
        trace=[],
        node_results=[NodeExecutionResult(step_id="rank_regions", status="completed", produced_outputs=["ranked_regions"])],
        artifact_index={
            "ranked_regions": ExecutionArtifact(
                artifact_id="ranked_regions",
                kind="frame",
                value=[{"team": "Support", "row_count": 4}],
                logical_shape="table",
                physical_shape="recordset",
                producer_step_id="rank_regions",
                metadata={"table_name": "ranked_regions"},
            )
        },
    )

    assert result.response["result"]["name"] == "ranked_regions"
    assert result.response["result"]["producer_step_id"] == "rank_regions"
    assert result.response["result"]["value"] == [{"team": "Support", "row_count": 4}]


def test_result_builder_includes_serialized_artifact_index_in_execution_and_meta_payloads() -> None:
    builder = ResultBuilder()
    result = builder.build_analysis_result(
        summary="Artifact index payload.",
        deterministic_summary="Artifact index payload.",
        llm_summary=None,
        summary_source="deterministic",
        metrics=[],
        tables=[],
        warnings=[],
        plan=AnalysisPlan(task_type="descriptive", rationale="Expose artifact index.", final_output_ref="row_count"),
        request=AnalysisRequest(question="How many rows?"),
        profile=build_profile(),
        trace=[],
        artifact_index={
            "row_count": ExecutionArtifact(
                artifact_id="row_count",
                kind="scalar",
                value=7,
                logical_shape="count",
                physical_shape="scalar",
                producer_step_id="row_count",
            )
        },
    )

    assert result.response["execution"]["artifact_index"]["row_count"]["value"] == 7
    assert result.response["meta"]["artifact_index"]["row_count"]["logical_shape"] == "count"
