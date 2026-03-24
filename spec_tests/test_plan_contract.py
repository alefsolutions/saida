from __future__ import annotations

import pytest

from saida import Saida
from saida.core import PlanValidator
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep
from saida.exceptions import PlanningError
from .factories import build_support_dataset, json_safe


def test_engine_plan_builds_bound_vnext_plan() -> None:
    engine = Saida()
    dataset = build_support_dataset()

    plan = engine.plan(dataset, "How many rows do we have?")

    assert plan.plan_id is not None
    assert plan.version == "saida.plan.v2"
    assert plan.dataset_refs == [dataset.name]
    assert plan.inputs[0].ref == dataset.name
    assert plan.expected_result_name == "row_count"
    assert plan.expected_result_shape == "scalar"
    assert plan.metadata["dataset_name"] == dataset.name
    assert plan.metadata["request_snapshot"]["question"] == "How many rows do we have?"
    assert plan.steps[0].family == "row_count"
    assert plan.steps[0].method_id == "row_count"
    assert plan.steps[0].output_refs == ["row_count"]
    assert plan.steps[0].metadata["execution_order"] == 1


def test_engine_execute_plan_round_trip_matches_analyze_for_row_count() -> None:
    engine = Saida()
    dataset = build_support_dataset()

    plan = engine.plan(dataset, "How many rows do we have?")
    analyzed = engine.analyze(dataset, "How many rows do we have?")
    executed = engine.execute_plan(dataset, plan)

    assert json_safe(executed.response["result"]) == json_safe(analyzed.response["result"])
    assert executed.response["execution"]["plan_id"] == plan.plan_id
    assert executed.response["execution"]["expected_result_name"] == "row_count"
    assert executed.response["interpretation"]["prompt_family"] == "row_count"


def test_engine_execute_plan_supports_user_authored_row_count_plan() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Count unresolved support tickets deterministically.",
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                parameters={"filters": {"reopened_flag": "no"}},
                description="Count rows where reopened_flag is no.",
            )
        ],
        expected_result_name="row_count",
        expected_result_shape="scalar",
    )

    result = engine.execute_plan(dataset, plan)

    assert result.response["result"]["name"] == "row_count"
    assert result.response["result"]["value"] == 4
    assert result.response["interpretation"]["prompt_family"] == "row_count"
    assert result.response["interpretation"]["filters"] == {"reopened_flag": "no"}


def test_plan_validator_rejects_duplicate_step_ids() -> None:
    validator = PlanValidator()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Invalid duplicate ids.",
        steps=[
            PlanStep(
                step_id="duplicate",
                tool_family="duckdb",
                action="row_count",
                parameters={},
                description="First row count.",
            ),
            PlanStep(
                step_id="duplicate",
                tool_family="duckdb",
                action="row_count",
                parameters={},
                description="Second row count.",
            ),
        ],
    )

    with pytest.raises(PlanningError, match="duplicate step_ids"):
        validator.validate_plan(plan)


def test_plan_validator_rejects_out_of_order_dependencies() -> None:
    validator = PlanValidator()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Invalid dependency order.",
        steps=[
            PlanStep(
                step_id="summary",
                tool_family="stats",
                action="numeric_summary",
                parameters={},
                description="Summarize numeric data.",
                depends_on=["row_count"],
            ),
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                parameters={},
                description="Count rows.",
            ),
        ],
    )

    with pytest.raises(PlanningError, match="appear later"):
        validator.validate_plan(plan)


def test_analysis_plan_to_dict_contains_vnext_contract_fields() -> None:
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Count rows in the primary dataset.",
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                parameters={},
                description="Count rows.",
                family="row_count",
                method_id="row_count",
                output_refs=["row_count"],
            )
        ],
        plan_id="support:row_count:row_count",
        dataset_refs=["support"],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref="support")],
        expected_result_name="row_count",
        expected_result_shape="scalar",
        metadata={"author": "spec"},
    )

    payload = plan.to_dict()

    assert payload["version"] == "saida.plan.v2"
    assert payload["dataset_refs"] == ["support"]
    assert payload["inputs"][0]["input_id"] == "primary_dataset"
    assert payload["steps"][0]["family"] == "row_count"
    assert payload["steps"][0]["output_refs"] == ["row_count"]
    assert payload["expected_result_shape"] == "scalar"
