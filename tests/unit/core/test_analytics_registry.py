from __future__ import annotations

from saida import PromptAnalysisFrontend, Saida
from saida.core import get_analytics_registry
from saida.core.contracts import AnalysisRequest
from saida.plan_generation import build_prompt_plan_contract
from tests.helpers.factories import build_support_dataset


def test_default_analytics_registry_covers_live_row_count_method() -> None:
    registry = get_analytics_registry()

    family = registry.get_family("aggregation_grouping")
    method = registry.get_method("row_count")

    assert family is not None
    assert method is not None
    assert method.family_id == "aggregation_grouping"
    assert "row_count" in family.method_ids
    assert method.output_shapes == ("scalar",)


def test_default_analytics_registry_exposes_prompt_relevant_concepts_and_relations() -> None:
    registry = get_analytics_registry()

    concept = registry.get_concept("top_n_by_metric")

    assert concept is not None
    assert concept.category == "pattern"
    assert "requires_metric" in registry.related("top_n_by_metric", "requires")
    assert "ranked_breakdown" in registry.related("top_n_by_metric", "uses")


def test_engine_plan_binds_step_family_from_analytics_registry() -> None:
    engine = PromptAnalysisFrontend()
    dataset = build_support_dataset()

    plan = engine.plan(dataset, "How many rows do we have?")

    assert plan.steps[0].family == "aggregation_grouping"
    assert plan.steps[0].method_id == "row_count"
    assert plan.steps[0].expected_output == {
        "output_id": "row_count",
        "logical_shape": "scalar",
        "physical_shape": "scalar",
    }


def test_prompt_plan_contract_exposes_analytics_families_and_methods() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    request = AnalysisRequest(
        question="How many rows do we have?",
        prompt_family="row_count",
        intent_name="row_count",
        task_type_hint="descriptive",
    )

    contract = build_prompt_plan_contract(request, profile)

    assert contract.analytics_method_ids == ["row_count"]
    assert contract.analytics_family_ids == ["aggregation_grouping"]

