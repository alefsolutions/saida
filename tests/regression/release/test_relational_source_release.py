from __future__ import annotations

from saida import PromptAnalysisFrontend, Saida

from tests.helpers.factories import build_explicit_single_step_plan
from tests.helpers.relational_fixtures import (
    build_ambiguous_country_sqlite_source,
    build_commerce_sqlite_source,
)


def test_relational_source_release_prompt_flow_materializes_and_executes(tmp_path) -> None:
    source = build_commerce_sqlite_source(tmp_path / "warehouse.sqlite")

    result = PromptAnalysisFrontend().analyze_source(source, "Show a table of total_sales by country")
    payload = result.to_response_dict()
    debug_payload = result.to_debug_response_dict()

    assert payload["status"] == "ok"
    assert payload["interpretation"]["prompt_family"] == "grouped_metric_table"
    assert payload["result"]["value"] == [
        {"country": "Japan", "target_total": 80.0},
        {"country": "Germany", "target_total": 150.0},
        {"country": "Australia", "target_total": 220.0},
    ]
    assert debug_payload["execution"]["source_provenance"]["required_tables"] == ["customers", "orders"]
    assert debug_payload["execution"]["source_provenance"]["join_count"] == 1


def test_relational_source_release_direct_plan_executes_against_materialized_dataset(tmp_path) -> None:
    source = build_commerce_sqlite_source(tmp_path / "warehouse_direct.sqlite")
    dataset = source.load_for_columns(
        required_columns=["country", "total_sales"],
        preferred_base_table="orders",
    )
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Aggregate materialized relational sales by country.",
        step_id="grouped_totals",
        tool_family="duckdb",
        method_id="aggregate_frame",
        family="transformation",
        parameters={"target": "total_sales", "aggregation": "sum", "group_by": ["country"]},
        description="Aggregate relational sales totals by country.",
        expected_result_name="grouped_totals",
        expected_result_shape="table",
    )

    result = Saida().execute_plan(dataset, plan)
    payload = result.to_response_dict()

    assert dataset.metadata["materialization_mode"] == "relational_access_plan"
    assert payload["result"]["logical_shape"] == "table"
    assert payload["result"]["value"] == [
        {"country": "Australia", "aggregate_value": 220.0},
        {"country": "Germany", "aggregate_value": 150.0},
        {"country": "Japan", "aggregate_value": 80.0},
    ]


def test_relational_source_release_ambiguous_prompt_returns_clarification(tmp_path) -> None:
    source = build_ambiguous_country_sqlite_source(tmp_path / "warehouse_ambiguous.sqlite")

    result = PromptAnalysisFrontend().analyze_source(source, "List distinct country values")
    payload = result.to_response_dict()
    debug_payload = result.to_debug_response_dict()

    assert payload["status"] == "clarify"
    assert result.plan.task_type == "clarification"
    assert "which table you mean" in payload["summary"]["summary"]
    assert "source_provenance" not in payload["execution"]
    assert debug_payload["execution"]["source_provenance"]["clarification"]["reason"] == "ambiguous_relational_column"
