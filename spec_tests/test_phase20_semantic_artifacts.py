from __future__ import annotations

import pandas as pd
import pytest

from saida import Saida
from saida.core import (
    AnalysisPlan,
    ExecutionArtifact,
    GroupedTableArtifact,
    PlanInput,
    RankedTableArtifact,
    StatisticalTestArtifact,
    StepInputRef,
    StepOutputSpec,
    TimeSeriesArtifact,
    artifact_from_value,
    get_analytics_registry,
)
from saida.core.contracts import AnalysisInterpretation, Dataset, DatasetProfile, PlanStep
from saida.core.result_canonicalization import ResultCanonicalizer
from saida.exceptions import PlanningError


def test_phase20_artifact_factory_selects_semantic_frame_artifact_types() -> None:
    grouped = artifact_from_value(
        "grouped_rows",
        pd.DataFrame({"region": ["West"], "aggregate_value": [210.0]}),
        metadata={"table_name": "group_breakdown", "group_by": ["region"]},
    )
    ranked = artifact_from_value(
        "ranked_rows",
        pd.DataFrame({"rank": [1], "region": ["West"], "target_total": [210.0]}),
        metadata={"table_name": "ranked_breakdown"},
    )
    statistical = artifact_from_value(
        "t_test_result",
        pd.DataFrame({"p_value": [0.03], "is_significant": [True]}),
        logical_shape="statistical_test",
        metadata={"table_name": "t_test"},
    )
    time_series = artifact_from_value(
        "trend_rows",
        pd.DataFrame({"month": ["2026-01"], "target_total": [210.0]}),
        metadata={"table_name": "time_trend", "bucket": "month"},
    )

    assert isinstance(grouped, GroupedTableArtifact)
    assert grouped.semantic_kind == "grouped_table"
    assert isinstance(ranked, RankedTableArtifact)
    assert ranked.semantic_kind == "ranked_table"
    assert isinstance(statistical, StatisticalTestArtifact)
    assert statistical.semantic_kind == "statistical_test"
    assert isinstance(time_series, TimeSeriesArtifact)
    assert time_series.semantic_kind == "time_series"


def test_phase20_registry_exposes_semantic_output_contracts() -> None:
    registry = get_analytics_registry()

    assert registry.get_method("group_frame").semantic_output_kinds == ("grouped_table",)
    assert registry.get_method("rank_frame").semantic_output_kinds == ("ranked_table",)
    assert registry.get_method("time_trend").semantic_output_kinds == ("time_series",)
    assert registry.get_method("t_test").semantic_output_kinds == ("statistical_test",)
    assert registry.get_method("column_presence_check").semantic_output_kinds == ("verification_result",)


def test_phase20_validation_rejects_semantic_output_mismatch() -> None:
    engine = Saida()
    dataset = Dataset(
        name="sales",
        source_type="pandas",
        data=pd.DataFrame({"region": ["West", "East"], "revenue": [100.0, 120.0]}),
    )
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Expect the wrong semantic kind on purpose.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="grouped_rows",
        expected_result_shape="table",
        final_output_ref="grouped_rows",
        steps=[
            PlanStep(
                step_id="group_rows",
                tool_family="duckdb",
                action="group_frame",
                method_id="group_frame",
                family="transformation",
                parameters={"group_by": ["region"]},
                description="Group rows by region.",
                inputs=[StepInputRef(input_id="dataset_input", source_type="plan_input", ref="primary_dataset", expected_kind="dataset")],
                output_refs=["grouped_rows"],
                outputs=[StepOutputSpec(output_id="grouped_rows", kind="frame", logical_shape="table", physical_shape="recordset")],
                expected_output={
                    "output_id": "grouped_rows",
                    "logical_shape": "table",
                    "physical_shape": "recordset",
                    "semantic_kind": "ranked_table",
                },
            )
        ],
    )

    with pytest.raises(PlanningError, match="semantic_kind 'ranked_table'"):
        engine.execute_plan(dataset, plan)


def test_phase20_result_packaging_preserves_semantic_kinds() -> None:
    canonicalizer = ResultCanonicalizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Preserve semantic kinds.", final_output_ref="ranked_rows")
    request = AnalysisInterpretation(question="Rank revenue by region")
    profile = DatasetProfile(
        dataset_name="sales",
        row_count=2,
        column_count=2,
        columns=[],
        measure_columns=["revenue"],
        dimension_columns=["region"],
        time_columns=[],
        identifier_columns=[],
    )
    artifact_index = {
        "ranked_rows": ExecutionArtifact(
            artifact_id="ranked_rows",
            kind="frame",
            value=[{"rank": 1, "region": "West", "target_total": 210.0}],
            logical_shape="table",
            physical_shape="recordset",
            semantic_kind="ranked_table",
            metadata={"table_name": "ranked_breakdown"},
        )
    }

    result = canonicalizer.build_analysis_result(
        summary="Ranked rows.",
        deterministic_summary="Ranked rows.",
        llm_summary=None,
        summary_source="deterministic",
        metrics=[],
        tables=[],
        warnings=[],
        plan=plan,
        request=request,
        profile=profile,
        trace=[],
        artifact_index=artifact_index,
    )

    assert result.response["result"]["semantic_kind"] == "ranked_table"
    assert result.response["execution"]["artifact_index"]["ranked_rows"]["semantic_kind"] == "ranked_table"
