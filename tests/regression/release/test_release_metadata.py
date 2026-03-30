from __future__ import annotations

from pathlib import Path

import pytest

from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec
from saida.exceptions import PlanningError

from tests.helpers.factories import build_support_dataset


def test_execute_plan_rejects_minimally_declared_authored_plan_under_strict_dag_contract() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Minimally declared single-step plan.",
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

    with pytest.raises(PlanningError, match="must declare at least one dataset_ref"):
        engine.execute_plan(dataset, plan)


def test_explicit_dag_plan_execution_reports_clean_dag_execution_metadata() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Explicit DAG contract.",
        dataset_refs=[dataset.name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
        expected_result_name="row_count",
        expected_result_shape="scalar",
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

    assert result.response["execution"]["execution_model"] == "dag-single-threaded"
    assert "contract_binding" not in result.response["execution"]
    assert "contract_binding" not in result.response["meta"]


def test_changelog_documents_dag_release_hardening() -> None:
    changelog_path = Path(__file__).resolve().parents[3] / "CHANGELOG.md"
    content = changelog_path.read_text(encoding="utf-8")

    assert "### DAG Execution" in content
    assert "### Compatibility And Release Hardening" in content
    assert "Preserved `saida.response.v2` as the public response schema" in content
    assert "Removed runtime plan binding metadata from execution results" in content

