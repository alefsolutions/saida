from __future__ import annotations

import pandas as pd
import pytest

from saida import PromptAnalysisFrontend, Saida
from saida.core import PlanValidator
from saida.core.contracts import AnalysisPlan, Dataset, PlanInput, PlanStep, StepInputRef, StepOutputSpec
from saida.exceptions import PlanningError
from tests.helpers.factories import build_explicit_single_step_plan, build_support_dataset, json_safe


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
    assert plan.metadata["interpretation_snapshot"]["question"] == "How many rows do we have?"
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
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Count unresolved support tickets deterministically.",
        step_id="row_count",
        tool_family="duckdb",
        method_id="row_count",
        family="aggregation_grouping",
        parameters={"filters": {"reopened_flag": "no"}},
        description="Count rows where reopened_flag is no.",
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
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Count support rows without invoking prompt generation.",
        step_id="row_count",
        tool_family="duckdb",
        method_id="row_count",
        family="aggregation_grouping",
        parameters={},
        description="Count all support rows.",
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
    assert "prompt_plan_contract" not in capabilities


def test_prompt_frontend_exposes_prompt_surface_capabilities() -> None:
    capabilities = PromptAnalysisFrontend().capabilities()

    assert capabilities["execute_plan"] is True
    assert capabilities["profile"] is True
    assert capabilities["plan"] is True
    assert capabilities["analyze"] is True
    assert capabilities["prompt_plan_contract"] is True


def test_plan_validator_rejects_duplicate_step_ids() -> None:
    validator = PlanValidator()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Invalid duplicate ids.",
        dataset_refs=["support"],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref="support")],
        final_output_ref="duplicate",
        steps=[
            PlanStep(
                step_id="duplicate",
                tool_family="duckdb",
                action="row_count",
                parameters={},
                description="First row count.",
                family="aggregation_grouping",
                method_id="row_count",
                inputs=[StepInputRef(input_id="dataset_input", source_type="plan_input", ref="primary_dataset", expected_kind="dataset")],
                output_refs=["duplicate"],
                outputs=[StepOutputSpec(output_id="duplicate", kind="scalar", logical_shape="scalar", physical_shape="scalar")],
                expected_output={"output_id": "duplicate", "logical_shape": "scalar", "physical_shape": "scalar"},
            ),
            PlanStep(
                step_id="duplicate",
                tool_family="duckdb",
                action="row_count",
                parameters={},
                description="Second row count.",
                family="aggregation_grouping",
                method_id="row_count",
                inputs=[StepInputRef(input_id="dataset_input_2", source_type="plan_input", ref="primary_dataset", expected_kind="dataset")],
                output_refs=["duplicate_2"],
                outputs=[StepOutputSpec(output_id="duplicate_2", kind="scalar", logical_shape="scalar", physical_shape="scalar")],
                expected_output={"output_id": "duplicate_2", "logical_shape": "scalar", "physical_shape": "scalar"},
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
        dataset_refs=["support"],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref="support")],
        final_output_ref="row_count",
        steps=[
            PlanStep(
                step_id="summary",
                tool_family="stats",
                action="numeric_summary",
                parameters={},
                description="Summarize numeric data.",
                family="diagnostic_workflows",
                method_id="numeric_summary",
                depends_on=["row_count"],
                inputs=[StepInputRef(input_id="row_count_input", source_type="step_output", ref="row_count")],
                output_refs=["summary"],
                outputs=[StepOutputSpec(output_id="summary", kind="frame", logical_shape="table", physical_shape="recordset")],
                expected_output={"output_id": "summary", "logical_shape": "table", "physical_shape": "recordset"},
            ),
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                parameters={},
                description="Count rows.",
                family="aggregation_grouping",
                method_id="row_count",
                inputs=[StepInputRef(input_id="dataset_input", source_type="plan_input", ref="primary_dataset", expected_kind="dataset")],
                output_refs=["row_count"],
                outputs=[StepOutputSpec(output_id="row_count", kind="scalar", logical_shape="scalar", physical_shape="scalar")],
                expected_output={"output_id": "row_count", "logical_shape": "scalar", "physical_shape": "scalar"},
            ),
        ],
    )

    with pytest.raises(PlanningError, match="appear later"):
        validator.validate_plan(plan)


def test_analysis_plan_to_dict_contains_vnext_contract_fields() -> None:
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Count rows in the primary dataset.",
        plan_id="support:row_count:row_count",
        dataset_refs=["support"],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref="support")],
        expected_result_name="row_count",
        expected_result_shape="scalar",
        final_output_ref="row_count",
        metadata={"author": "spec"},
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                parameters={},
                description="Count rows.",
                family="aggregation_grouping",
                method_id="row_count",
                inputs=[StepInputRef(input_id="dataset_input", source_type="plan_input", ref="primary_dataset", expected_kind="dataset")],
                output_refs=["row_count"],
                outputs=[StepOutputSpec(output_id="row_count", kind="scalar", logical_shape="scalar", physical_shape="scalar")],
                expected_output={"output_id": "row_count", "logical_shape": "scalar", "physical_shape": "scalar"},
            )
        ],
    )

    payload = plan.to_dict()

    assert payload["version"] == "saida.plan.v2"
    assert payload["dataset_refs"] == ["support"]
    assert payload["inputs"][0]["input_id"] == "primary_dataset"
    assert payload["steps"][0]["family"] == "aggregation_grouping"
    assert payload["steps"][0]["output_refs"] == ["row_count"]
    assert payload["expected_result_shape"] == "scalar"


def test_prompt_frontend_metadata_plan_strips_placeholder_parameters() -> None:
    engine = PromptAnalysisFrontend()
    dataset = build_support_dataset()

    plan = engine.plan(dataset, "What are the dataset columns?")

    assert plan.steps[0].method_id == "column_inventory"
    assert plan.steps[0].parameters == {}


def test_prompt_frontend_generated_plan_keeps_only_supported_statistical_parameters() -> None:
    engine = PromptAnalysisFrontend()
    dataset = Dataset(
        name="sales",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "region": ["North"] * 6 + ["South"] * 6,
                "revenue": [100, 104, 98, 102, 101, 99, 135, 138, 132, 140, 136, 134],
            }
        ),
    )

    plan = engine.plan(dataset, "Do regions differ in revenue?")

    assert plan.steps[0].method_id == "significance_inference"
    assert set(plan.steps[0].parameters) == {"target", "group_by", "alpha"}


def test_prompt_frontend_generated_plan_omits_group_by_for_ungrouped_period_comparison() -> None:
    engine = PromptAnalysisFrontend()
    dataset = Dataset(
        name="sales",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "posted_at": [
                    "2025-01-01",
                    "2025-04-01",
                    "2025-07-01",
                    "2025-10-01",
                    "2026-01-01",
                    "2026-04-01",
                    "2026-07-01",
                    "2026-10-01",
                ],
                "revenue": [100.0, 120.0, 140.0, 160.0, 180.0, 200.0, 220.0, 240.0],
                "region": ["West", "East", "West", "East", "West", "East", "West", "East"],
            }
        ),
    )

    plan = engine.plan(dataset, "Compare revenue this quarter to last quarter")

    assert [step.method_id for step in plan.steps] == ["time_bucket_frame", "period_comparison"]
    assert "group_by" not in plan.steps[1].parameters

