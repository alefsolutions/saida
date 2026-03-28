from __future__ import annotations

import pytest

from saida import PromptAnalysisFrontend, Saida
from saida.core import PlanValidator
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep
from saida.exceptions import PlanningError
from .factories import build_support_dataset, json_safe


def test_engine_plan_builds_bound_vnext_plan() -> None:
    engine = PromptAnalysisFrontend()
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
    assert plan.steps[0].family == "aggregation_grouping"
    assert plan.steps[0].method_id == "row_count"
    assert plan.steps[0].output_refs == ["row_count"]
    assert plan.steps[0].metadata["execution_order"] == 1


def test_engine_execute_plan_round_trip_matches_analyze_for_row_count() -> None:
    prompt_frontend = PromptAnalysisFrontend()
    engine = Saida()
    dataset = build_support_dataset()

    plan = prompt_frontend.plan(dataset, "How many rows do we have?")
    analyzed = prompt_frontend.analyze(dataset, "How many rows do we have?")
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


def test_execute_plan_does_not_require_prompt_generation_path_for_authored_plan() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Count support rows without invoking prompt generation.",
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                parameters={},
                description="Count all support rows.",
            )
        ],
        expected_result_name="row_count",
        expected_result_shape="scalar",
    )

    result = engine.execute_plan(dataset, plan)

    assert not hasattr(engine, "plan")
    assert not hasattr(engine, "analyze")
    assert not hasattr(engine, "_generate_plan_result")
    assert result.response["status"] == "ok"
    assert result.response["result"]["name"] == "row_count"
    assert result.response["result"]["value"] == 7


def test_capabilities_expose_execute_plan_as_core_framework_surface() -> None:
    capabilities = Saida().capabilities()

    assert capabilities["execute_plan"] is True
    assert capabilities["profile"] is True
    assert capabilities["render_output"] is True
    assert "plan" not in capabilities
    assert "analyze" not in capabilities
    assert "prompt_capability_contract" not in capabilities


def test_prompt_frontend_exposes_prompt_surface_capabilities() -> None:
    capabilities = PromptAnalysisFrontend().capabilities()

    assert capabilities["execute_plan"] is True
    assert capabilities["profile"] is True
    assert capabilities["plan"] is True
    assert capabilities["analyze"] is True
    assert capabilities["prompt_capability_contract"] is True


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
                family="aggregation_grouping",
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
    assert payload["steps"][0]["family"] == "aggregation_grouping"
    assert payload["steps"][0]["output_refs"] == ["row_count"]
    assert payload["expected_result_shape"] == "scalar"
