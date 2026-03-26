from __future__ import annotations

from copy import deepcopy

from saida import Saida
from saida.adapters import ComputeInterface, ComputeRequest, ComputeResponse, DuckDBAdapter, MetadataComputeAdapter
from saida.core.contracts import AnalysisPlan, PlanStep
from .factories import build_sales_dataset, build_support_dataset, json_safe


class DelegatingDuckDbAdapter(ComputeInterface):
    def __init__(self) -> None:
        self._delegate = DuckDBAdapter()

    @property
    def tool_family(self) -> str:
        return "duckdb"

    def supported_methods(self) -> tuple[str, ...]:
        return self._delegate.supported_methods()

    def execute(self, request: ComputeRequest) -> ComputeResponse:
        return self._delegate.execute(request)


class DelegatingMetadataAdapter(ComputeInterface):
    def __init__(self) -> None:
        self._delegate = MetadataComputeAdapter()

    @property
    def tool_family(self) -> str:
        return "metadata"

    def supported_methods(self) -> tuple[str, ...]:
        return self._delegate.supported_methods()

    def execute(self, request: ComputeRequest) -> ComputeResponse:
        return self._delegate.execute(request)


def test_same_row_count_plan_and_data_produce_same_response() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Count rows with reopened_flag set to no.",
        expected_result_name="row_count",
        expected_result_shape="scalar",
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                parameters={"filters": {"reopened_flag": "no"}},
                description="Count rows with reopened_flag set to no.",
                family="aggregation_grouping",
                method_id="row_count",
            )
        ],
    )

    first = engine.execute_plan(dataset, deepcopy(plan))
    second = engine.execute_plan(dataset, deepcopy(plan))

    assert _response_signature(first) == _response_signature(second)


def test_same_tabular_plan_and_data_produce_same_response() -> None:
    engine = Saida()
    dataset = build_sales_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Return selected West rows in posted_at order.",
        expected_result_name="tabular_query",
        expected_result_shape="table",
        steps=[
            PlanStep(
                step_id="tabular_query",
                tool_family="duckdb",
                action="tabular_query",
                parameters={
                    "selected_columns": ["posted_at", "revenue"],
                    "filters": {"region": "West"},
                    "sort_by": "posted_at",
                    "sort_direction": "asc",
                    "page": 1,
                    "page_size": 50,
                },
                description="Return selected West rows.",
                family="projection_field_selection",
                method_id="tabular_query",
            )
        ],
    )

    first = engine.execute_plan(dataset, deepcopy(plan))
    second = engine.execute_plan(dataset, deepcopy(plan))

    assert _response_signature(first) == _response_signature(second)


def test_same_verification_plan_and_data_produce_same_response() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Verify whether any Platform rows exist.",
        expected_result_name="row_existence",
        expected_result_shape="verification",
        steps=[
            PlanStep(
                step_id="row_existence",
                tool_family="duckdb",
                action="row_existence",
                parameters={"filters": {"team": "Platform"}},
                description="Verify whether any Platform rows exist.",
                family="validation_verification",
                method_id="row_existence",
            )
        ],
    )

    first = engine.execute_plan(dataset, deepcopy(plan))
    second = engine.execute_plan(dataset, deepcopy(plan))

    assert _response_signature(first) == _response_signature(second)


def test_row_count_plan_is_adapter_equivalent_across_duckdb_implementations() -> None:
    dataset = build_support_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Count rows where reopened_flag is no.",
        expected_result_name="row_count",
        expected_result_shape="scalar",
        steps=[
            PlanStep(
                step_id="row_count",
                tool_family="duckdb",
                action="row_count",
                parameters={"filters": {"reopened_flag": "no"}},
                description="Count rows where reopened_flag is no.",
                family="aggregation_grouping",
                method_id="row_count",
            )
        ],
    )
    baseline_engine = Saida()
    delegated_engine = Saida()
    delegated_engine.router._adapters["duckdb"] = DelegatingDuckDbAdapter()

    baseline = baseline_engine.execute_plan(dataset, deepcopy(plan))
    delegated = delegated_engine.execute_plan(dataset, deepcopy(plan))

    assert _response_signature(baseline) == _response_signature(delegated)


def test_column_count_plan_is_adapter_equivalent_across_metadata_implementations() -> None:
    dataset = build_support_dataset()
    plan = AnalysisPlan(
        task_type="descriptive",
        rationale="Count dataset columns.",
        expected_result_name="column_count",
        expected_result_shape="scalar",
        steps=[
            PlanStep(
                step_id="column_count",
                tool_family="metadata",
                action="column_count",
                parameters={},
                description="Count dataset columns.",
                family="schema_metadata_inspection",
                method_id="column_count",
            )
        ],
    )
    baseline_engine = Saida()
    delegated_engine = Saida()
    delegated_engine.router._adapters["metadata"] = DelegatingMetadataAdapter()

    baseline = baseline_engine.execute_plan(dataset, deepcopy(plan))
    delegated = delegated_engine.execute_plan(dataset, deepcopy(plan))

    assert _response_signature(baseline) == _response_signature(delegated)


def _response_signature(result: object) -> object:
    response = result.response
    return json_safe(
        {
            "result": response["result"],
            "tables": response["tables"],
            "interpretation": response["interpretation"],
            "execution": response["execution"],
            "meta": response["meta"],
        }
    )
