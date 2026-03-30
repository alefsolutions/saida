from __future__ import annotations

from saida import PromptAnalysisFrontend, Saida
from saida.core.analytics_registry import get_analytics_registry
from saida.plan_generation.prompt_family_catalog import get_prompt_family_catalog

from tests.helpers.factories import build_basic_row_count_plan, build_sales_dataset, build_statistical_dataset, build_support_dataset


def test_release_gate_registry_and_prompt_catalog_are_populated() -> None:
    registry = get_analytics_registry()
    prompt_catalog = get_prompt_family_catalog()

    assert registry.families
    assert registry.methods
    assert prompt_catalog.families

    implemented_family_ids = {
        family_id
        for family_id, family in registry.families.items()
        if family.availability in {"implemented", "partial"}
    }
    assert all(registry.families[family_id].method_ids for family_id in implemented_family_ids)
    assert all(spec.allowed_plan_actions for spec in prompt_catalog.families.values())
    assert all(spec.primary_result_shapes for spec in prompt_catalog.families.values())
    assert all(spec.label and spec.description for spec in prompt_catalog.families.values())


def test_release_gate_direct_plan_execution_stays_deterministic() -> None:
    dataset = build_support_dataset()
    result = Saida().execute_plan(dataset, build_basic_row_count_plan(dataset.name))

    assert result.to_response_dict()["result"]["value"] == 7
    assert result.to_debug_response_dict()["execution"]["terminal_output_ref"] == "row_count"


def test_release_gate_prompt_grouped_table_flow_returns_grouped_result() -> None:
    dataset = build_sales_dataset()
    result = PromptAnalysisFrontend().analyze(dataset, "Show a table of revenue by region")
    payload = result.to_response_dict()

    assert payload["interpretation"]["prompt_family"] == "grouped_metric_table"
    assert payload["result"]["logical_shape"] == "table"
    assert payload["result"]["dtype"] == "frame"
    assert payload["result"]["value"] == [
        {"region": "West", "target_total": 300.0},
        {"region": "East", "target_total": 330.0},
    ]


def test_release_gate_prompt_retrieval_flow_honors_latest_and_limit() -> None:
    dataset = build_support_dataset()
    result = PromptAnalysisFrontend().analyze(dataset, "Show the latest 3 rows")
    payload = result.to_response_dict()

    assert payload["interpretation"]["prompt_family"] == "tabular_record_retrieval"
    assert payload["result"]["logical_shape"] == "recordset"
    assert len(payload["result"]["value"]) == 3
    assert payload["result"]["value"][0]["ticket_id"] == "T7"
    assert payload["result"]["value"][1]["ticket_id"] == "T6"
    assert payload["result"]["value"][2]["ticket_id"] == "T5"


def test_release_gate_prompt_filter_and_statistical_flows_are_available() -> None:
    frontend = PromptAnalysisFrontend()

    support_result = frontend.analyze(build_support_dataset(), "How many rows have resolution_hours greater than 6?")
    stats_result = frontend.analyze(build_statistical_dataset(), "Run a t-test on revenue by region")

    assert support_result.to_response_dict()["result"]["value"] == 3
    assert stats_result.to_response_dict()["interpretation"]["prompt_family"] == "t_test"
    assert stats_result.to_response_dict()["result"]["logical_shape"] == "statistical_test"

