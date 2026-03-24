from __future__ import annotations

from saida import Saida
from saida.core import get_analytics_registry
from saida.core.contracts import AnalysisRequest
from saida.core.prompt_capability_contract import build_prompt_capability_contract
from .factories import build_support_dataset


def test_default_analytics_registry_covers_live_row_count_method() -> None:
    registry = get_analytics_registry()

    family = registry.get_family("aggregation_grouping")
    method = registry.get_method("row_count")

    assert family is not None
    assert method is not None
    assert method.family_id == "aggregation_grouping"
    assert "row_count" in family.method_ids
    assert method.output_shapes == ("scalar",)


def test_engine_plan_binds_step_family_from_analytics_registry() -> None:
    engine = Saida()
    dataset = build_support_dataset()

    plan = engine.plan(dataset, "How many rows do we have?")

    assert plan.steps[0].family == "aggregation_grouping"
    assert plan.steps[0].method_id == "row_count"
    assert plan.steps[0].expected_output == {
        "output_id": "row_count",
        "logical_shape": "scalar",
        "physical_shape": "scalar",
    }


def test_prompt_capability_contract_exposes_analytics_families_and_methods() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    request = AnalysisRequest(
        question="How many rows do we have?",
        prompt_family="row_count",
        intent_name="row_count",
        task_type_hint="descriptive",
    )

    contract = build_prompt_capability_contract(request, profile)

    assert contract.analytics_method_ids == ["row_count"]
    assert contract.analytics_family_ids == ["aggregation_grouping"]
