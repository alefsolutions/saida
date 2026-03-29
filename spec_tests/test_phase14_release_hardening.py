from __future__ import annotations

from pathlib import Path

from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec

from .factories import build_support_dataset


def test_legacy_plan_execution_exposes_compatibility_metadata() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Legacy single-step plan.",
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                parameters={},
                description="Count rows without explicit DAG metadata.",
            )
        ],
    )

    result = engine.execute_plan(dataset, plan)

    compatibility = result.response["execution"]["compatibility"]

    assert result.response["schema_version"] == "saida.response.v2"
    assert result.response["execution"]["execution_model"] == "dag-single-threaded"
    assert compatibility["legacy_plan_compatible"] is True
    assert compatibility["explicit_dag_contract"] is False
    assert "plan_inputs" in compatibility["legacy_plan_shims"]
    assert "row_count:step_inputs" in compatibility["legacy_plan_shims"]
    assert "row_count:output_refs" in compatibility["legacy_plan_shims"]
    assert "final_output_ref" in compatibility["legacy_plan_shims"]


def test_explicit_dag_plan_execution_reports_no_legacy_shims() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Explicit DAG contract.",
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        final_output_ref="row_count",
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                method_id="row_count",
                family="aggregation_grouping",
                parameters={},
                description="Count rows with explicit graph metadata.",
                inputs=[
                    StepInputRef(
                        input_id="dataset_input",
                        source_type="plan_input",
                        ref="primary_dataset",
                        expected_kind="dataset",
                    )
                ],
                output_refs=["row_count"],
                outputs=[StepOutputSpec(output_id="row_count", kind="scalar", logical_shape="scalar")],
                expected_output={"output_id": "row_count", "logical_shape": "scalar", "physical_shape": "scalar"},
            )
        ],
    )

    result = engine.execute_plan(dataset, plan)

    compatibility = result.response["meta"]["compatibility"]

    assert result.response["execution"]["execution_model"] == "dag-single-threaded"
    assert compatibility["legacy_plan_compatible"] is True
    assert compatibility["explicit_dag_contract"] is True
    assert compatibility["legacy_plan_shims"] == []


def test_changelog_documents_dag_release_hardening() -> None:
    changelog_path = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
    content = changelog_path.read_text(encoding="utf-8")

    assert "### DAG Execution" in content
    assert "### Compatibility And Release Hardening" in content
    assert "Preserved `saida.response.v2` as the public response schema" in content
    assert "Added compatibility metadata to execution results" in content
