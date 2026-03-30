from __future__ import annotations

from copy import deepcopy

from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanStep
from tests.helpers.factories import build_explicit_single_step_plan, build_sales_dataset, build_support_dataset
from tests.helpers.result_helpers import normalized_result_value


def test_execute_plan_returns_scalar_row_count_for_filtered_slice() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Count support rows where reopened_flag is no.",
        step_id="row_count",
        tool_family="duckdb",
        method_id="row_count",
        family="aggregation_grouping",
        parameters={"filters": {"reopened_flag": "no"}},
        description="Count support rows where reopened_flag is no.",
        expected_result_name="row_count",
        expected_result_shape="scalar",
    )

    result = engine.execute_plan(dataset, plan)

    assert result.response["result"]["name"] == "row_count"
    assert result.response["result"]["logical_shape"] == "scalar"
    assert normalized_result_value(result.response["result"]) == 4


def test_execute_plan_returns_scalar_aggregate_value() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Sum revenue across all rows.",
        step_id="aggregate_value",
        tool_family="duckdb",
        method_id="aggregate_value",
        family="aggregation_grouping",
        parameters={"target": "revenue", "aggregation": "sum"},
        description="Sum revenue across all rows.",
        expected_result_name="revenue_sum",
        expected_result_shape="scalar",
    )

    result = engine.execute_plan(dataset, plan)

    assert result.response["result"]["name"] == "revenue_sum"
    assert result.response["result"]["logical_shape"] == "scalar"
    assert normalized_result_value(result.response["result"]) == 630.0


def test_execute_plan_returns_grouped_row_count_table() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Count tickets by team.",
        step_id="count_rows_by_group",
        tool_family="duckdb",
        method_id="count_rows_by_group",
        family="aggregation_grouping",
        parameters={"group_by": ["team"]},
        description="Count tickets by team.",
        expected_result_name="group_row_counts",
        expected_result_shape="table",
    )

    result = engine.execute_plan(dataset, plan)
    records = result.response["result"]["value"]

    assert result.response["result"]["name"] == "group_row_counts"
    assert result.response["result"]["logical_shape"] == "table"
    assert records[0]["team"] == "Support"
    assert records[0]["row_count"] == 4
    assert records[1]["team"] == "Platform"
    assert records[1]["row_count"] == 3


def test_execute_plan_returns_filtered_recordset() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Return posted_at and revenue for West rows.",
        step_id="tabular_query",
        tool_family="duckdb",
        method_id="tabular_query",
        family="projection_field_selection",
        parameters={
            "selected_columns": ["posted_at", "revenue"],
            "filters": {"region": "West"},
            "sort_by": "posted_at",
            "sort_direction": "asc",
            "page": 1,
            "page_size": 50,
        },
        description="Return selected fields for West rows.",
        expected_result_name="tabular_query",
        expected_result_shape="table",
    )

    result = engine.execute_plan(dataset, plan)
    records = result.response["result"]["value"]

    assert result.response["result"]["name"] == "tabular_query"
    assert result.response["result"]["logical_shape"] == "recordset"
    assert len(records) == 3
    assert records[0] == {"posted_at": "2025-10-01", "revenue": 100.0}
    assert records[-1] == {"posted_at": "2026-02-01", "revenue": 110.0}


def test_execute_plan_returns_verification_for_row_existence() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Check whether Platform tickets exist.",
        step_id="row_existence",
        tool_family="duckdb",
        method_id="row_existence",
        family="validation_verification",
        parameters={"filters": {"team": "Platform"}},
        description="Verify whether any Platform tickets exist.",
        expected_result_name="row_existence",
        expected_result_shape="verification",
    )

    result = engine.execute_plan(dataset, plan)

    assert result.response["result"]["name"] == "row_existence"
    assert result.response["result"]["logical_shape"] == "verification"
    assert normalized_result_value(result.response["result"])["exists"] is True
    assert normalized_result_value(result.response["result"])["matching_row_count"] == 3


def test_execute_plan_returns_scalar_column_count() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Count support dataset columns.",
        step_id="column_count",
        tool_family="metadata",
        method_id="column_count",
        family="schema_metadata_inspection",
        parameters={},
        description="Count dataset columns.",
        expected_result_name="column_count",
        expected_result_shape="scalar",
    )

    result = engine.execute_plan(dataset, plan)

    assert result.response["result"]["name"] == "column_count"
    assert result.response["result"]["logical_shape"] == "scalar"
    assert normalized_result_value(result.response["result"]) == 7


def test_execute_plan_returns_scalar_distinct_value_count() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Count distinct support teams.",
        step_id="distinct_value_count",
        tool_family="duckdb",
        method_id="distinct_value_count",
        family="distinct_cardinality_analysis",
        parameters={"target": "team"},
        description="Count distinct team values.",
        expected_result_name="distinct_value_count",
        expected_result_shape="scalar",
    )

    result = engine.execute_plan(dataset, plan)

    assert result.response["result"]["name"] == "distinct_value_count"
    assert result.response["result"]["logical_shape"] == "scalar"
    assert normalized_result_value(result.response["result"]) == 2


def test_execute_plan_returns_scalar_column_type_lookup_from_plan_metadata() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = build_explicit_single_step_plan(
        dataset_name=dataset.name,
        task_type="descriptive",
        rationale="Look up the data type for created_at.",
        step_id="column_type_inventory",
        tool_family="metadata",
        method_id="column_type_inventory",
        family="schema_metadata_inspection",
        parameters={"target": "created_at"},
        description="Return the schema type for created_at.",
        expected_result_name="column_type_inventory",
        expected_result_shape="table",
    )
    plan.metadata["prompt_family"] = "column_type_lookup"
    result = engine.execute_plan(dataset, deepcopy(plan))

    assert result.response["result"]["name"] == "column_type_inventory"
    assert result.response["result"]["logical_shape"] == "table"
    assert normalized_result_value(result.response["result"])["dtype"] == "datetime"

