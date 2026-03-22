from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

import pandas as pd
import pytest

from saida import Saida
from saida.core.contracts import AnalysisPlan, AnalysisRequest, Dataset


@dataclass(frozen=True, slots=True)
class ReproducibilityCase:
    case_id: str
    dataset: Dataset
    prompts: list[str]
    expected_request: dict[str, Any]
    expected_plan: dict[str, Any]
    expected_result: dict[str, Any]


def build_ticket_channel_dataset() -> Dataset:
    return Dataset(
        name="tickets",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "ticket_id": ["T1", "T2", "T3", "T4", "T5"],
                "channel": ["Email", "Phone", "Email", "Chat", "Email"],
                "priority": ["High", "High", "Low", "Low", "Medium"],
                "created_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"],
            }
        ),
    )


def build_schema_dataset() -> Dataset:
    return Dataset(
        name="support",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "ticket_id": ["T1", "T2", "T3", "T4"],
                "created_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
                "resolution_hours": [4.2, 6.1, 3.4, 8.0],
                "priority": ["Low", "Medium", "High", "Medium"],
                "csat_score": [4.8, None, 4.1, 3.9],
            }
        ),
    )


def build_column_presence_dataset() -> Dataset:
    return Dataset(
        name="support",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "created_at": ["2026-01-01", "2026-01-02"],
                "priority": ["Low", "High"],
            }
        ),
    )


def build_sales_dataset() -> Dataset:
    return Dataset(
        name="sales",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "revenue": [100.0, 120.0, 90.0, 80.0],
                "region": ["West", "West", "East", "West"],
                "posted_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            }
        ),
    )


def build_tabular_dataset() -> Dataset:
    return Dataset(
        name="tickets",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "ticket_id": ["T1", "T2", "T3"],
                "created_at": ["2026-01-01", "2026-01-02", "2026-01-03"],
                "priority": ["Low", "Medium", "High"],
                "reopened_flag": ["yes", "no", "yes"],
            }
        ),
    )


def _request_signature(request: AnalysisRequest) -> dict[str, Any]:
    options = {
        key: value
        for key, value in request.options.items()
        if key not in {"dataset", "nlp_backend", "llm_status", "candidate_capabilities"}
    }
    return {
        "prompt_family": request.prompt_family,
        "intent_name": request.intent_name,
        "task_type_hint": request.task_type_hint,
        "target": request.target,
        "aggregation": request.aggregation,
        "horizon": request.horizon,
        "filters": request.filters,
        "group_by": list(request.group_by or []),
        "time_reference": request.time_reference,
        "options": options,
    }


def _plan_signature(plan: AnalysisPlan) -> dict[str, Any]:
    return {
        "task_type": plan.task_type,
        "rationale": plan.rationale,
        "warnings": list(plan.warnings),
        "steps": [
            {
                "step_id": step.step_id,
                "tool_family": step.tool_family,
                "action": step.action,
                "parameters": step.parameters,
                "description": step.description,
            }
            for step in plan.steps
        ],
    }


def _result_signature(result: Any) -> dict[str, Any]:
    payload = result.to_response_dict()
    return {
        "result": payload["result"],
        "table_names": [table["name"] for table in payload["tables"]],
        "summary": payload["reasoning"]["deterministic_summary"],
    }


def _canonical_jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


_REPRODUCIBILITY_CASES = [
    ReproducibilityCase(
        case_id="grouped-ticket-count-by-channel",
        dataset=build_ticket_channel_dataset(),
        prompts=[
            "Give me the total tickets per channel.",
            "For each channel, give me the total tickets.",
            "List each type of channels and the total tickets per channel",
            "Count tickets by channel",
        ],
        expected_request={
            "prompt_family": "grouped_entity_count",
            "intent_name": "grouped_tabular_query",
            "task_type_hint": "descriptive",
            "target": None,
            "aggregation": "count",
            "group_by": ["channel"],
            "options": {
                "intent_name": "grouped_tabular_query",
                "selected_columns": ["channel"],
                "sort_by": None,
                "sort_direction": "asc",
                "limit": None,
                "page": 1,
                "page_size": 50,
                "distinct_values": False,
            },
        },
        expected_plan={
            "task_type": "descriptive",
            "step_actions": ["grouped_tabular_query"],
            "step_parameters": [
                {
                    "target": None,
                    "group_by": ["channel"],
                    "aggregation": "count",
                    "filters": None,
                    "sort_by": None,
                    "sort_direction": "asc",
                    "limit": None,
                    "page": 1,
                    "page_size": 50,
                }
            ],
        },
        expected_result={
            "name": "grouped_tabular_query",
            "physical_shape": "recordset",
            "logical_shape": "table",
        },
    ),
    ReproducibilityCase(
        case_id="single-column-type-lookup",
        dataset=build_schema_dataset(),
        prompts=[
            "What is the data type of the created_at field in dataset?",
            "What type is created_at?",
            "What is the type of created_at?",
        ],
        expected_request={
            "prompt_family": "column_type_lookup",
            "intent_name": "column_type_inventory",
            "task_type_hint": "descriptive",
            "target": "created_at",
            "aggregation": None,
            "group_by": [],
            "options": {
                "intent_name": "column_type_inventory",
                "distinct_values": False,
            },
        },
        expected_plan={
            "task_type": "descriptive",
            "step_actions": ["column_type_inventory"],
            "step_parameters": [{"target": "created_at"}],
        },
        expected_result={
            "name": "created_at_dtype",
            "physical_shape": "scalar",
            "logical_shape": "scalar",
            "value": "datetime",
        },
    ),
    ReproducibilityCase(
        case_id="column-presence-check",
        dataset=build_column_presence_dataset(),
        prompts=[
            "Does the dataset have a created_at column?",
            "Is there a created_at field?",
            "Does this data include a created_at column?",
        ],
        expected_request={
            "prompt_family": "column_presence_check",
            "intent_name": "existence_check",
            "task_type_hint": "descriptive",
            "target": None,
            "aggregation": None,
            "group_by": [],
            "options": {
                "intent_name": "existence_check",
                "existence_mode": "column_presence_check",
                "requested_column": "created_at",
                "distinct_values": False,
            },
        },
        expected_plan={
            "task_type": "descriptive",
            "step_actions": ["column_presence_check"],
            "step_parameters": [{"requested_column": "created_at"}],
        },
        expected_result={
            "name": "column_presence_check",
            "physical_shape": "object",
            "logical_shape": "verification",
        },
    ),
    ReproducibilityCase(
        case_id="row-count",
        dataset=build_sales_dataset(),
        prompts=[
            "How many data rows do we have?",
            "What is the row count?",
            "Count rows",
        ],
        expected_request={
            "prompt_family": "row_count",
            "intent_name": "row_count",
            "task_type_hint": "descriptive",
            "target": None,
            "aggregation": "count",
            "group_by": [],
            "options": {
                "intent_name": "row_count",
                "distinct_values": False,
            },
        },
        expected_plan={
            "task_type": "descriptive",
            "step_actions": ["row_count"],
            "step_parameters": [{"filters": None}],
        },
        expected_result={
            "name": "row_count",
            "physical_shape": "scalar",
            "logical_shape": "count",
            "value": 4,
        },
    ),
    ReproducibilityCase(
        case_id="representation-ranking-most-represented",
        dataset=build_ticket_channel_dataset(),
        prompts=[
            "Which channel has the most tickets?",
            "What channel is most represented?",
            "Which channel has the highest count?",
        ],
        expected_request={
            "prompt_family": "representation_ranking",
            "intent_name": "representation_ranking",
            "task_type_hint": "descriptive",
            "target": "channel",
            "aggregation": "count",
            "group_by": ["channel"],
            "options": {
                "intent_name": "representation_ranking",
                "ranking_direction": "desc",
                "ranking_limit": 1,
                "distinct_values": False,
            },
        },
        expected_plan={
            "task_type": "descriptive",
            "step_actions": ["count_rows_by_group"],
            "step_parameters": [{"group_by": ["channel"], "filters": None, "ascending": False, "limit": 1}],
        },
        expected_result={
            "name": "group_row_counts",
            "physical_shape": "object",
            "logical_shape": "table",
            "value": {"channel": "Email", "row_count": 3},
        },
    ),
    ReproducibilityCase(
        case_id="dimension-property-check",
        dataset=build_sales_dataset(),
        prompts=[
            "Is region a dimension?",
            "Is region a grouping column?",
            "Is region a dimension column?",
        ],
        expected_request={
            "prompt_family": "column_property_check",
            "intent_name": "existence_check",
            "task_type_hint": "descriptive",
            "target": "region",
            "aggregation": None,
            "group_by": [],
            "options": {
                "intent_name": "existence_check",
                "existence_mode": "column_property_check",
                "expected_property": "dimension",
                "requested_column": "region",
                "distinct_values": False,
            },
        },
        expected_plan={
            "task_type": "descriptive",
            "step_actions": ["column_property_check"],
            "step_parameters": [{"target": "region", "expected_property": "dimension"}],
        },
        expected_result={
            "name": "column_property_check",
            "physical_shape": "object",
            "logical_shape": "verification",
        },
    ),
    ReproducibilityCase(
        case_id="time-coverage-date-range",
        dataset=build_sales_dataset(),
        prompts=[
            "What date range does the data cover?",
            "What is the date range of the dataset?",
            "From when to when does the data run?",
        ],
        expected_request={
            "prompt_family": "time_coverage",
            "intent_name": "time_coverage",
            "task_type_hint": "descriptive",
            "target": None,
            "aggregation": None,
            "group_by": [],
            "options": {
                "intent_name": "time_coverage",
                "time_coverage_mode": "date_range",
                "distinct_values": False,
            },
        },
        expected_plan={
            "task_type": "descriptive",
            "step_actions": ["time_coverage"],
            "step_parameters": [{"time_column": "posted_at", "filters": None, "mode": "date_range"}],
        },
        expected_result={
            "name": "time_coverage",
            "physical_shape": "object",
            "logical_shape": "timeseries",
        },
    ),
    ReproducibilityCase(
        case_id="tabular-query-selected-columns-and-sort",
        dataset=build_tabular_dataset(),
        prompts=[
            "Show ticket_id and priority rows sorted by created_at",
            "Display ticket_id and priority records ordered by created_at",
            "Return ticket_id and priority row data sorted by created_at",
        ],
        expected_request={
            "prompt_family": "tabular_record_retrieval",
            "intent_name": "tabular_query",
            "task_type_hint": "descriptive",
            "target": "ticket_id",
            "aggregation": None,
            "group_by": [],
            "options": {
                "intent_name": "tabular_query",
                "selected_columns": ["ticket_id", "priority", "created_at"],
                "sort_by": "created_at",
                "sort_direction": "asc",
                "limit": None,
                "page": 1,
                "page_size": 50,
                "distinct_values": False,
            },
        },
        expected_plan={
            "task_type": "descriptive",
            "step_actions": ["tabular_query"],
            "step_parameters": [
                {
                    "selected_columns": ["ticket_id", "priority", "created_at"],
                    "filters": None,
                    "sort_by": "created_at",
                    "sort_direction": "asc",
                    "limit": None,
                    "page": 1,
                    "page_size": 50,
                }
            ],
        },
        expected_result={
            "name": "tabular_query",
            "physical_shape": "recordset",
            "logical_shape": "recordset",
        },
    ),
]


@pytest.mark.parametrize("case", _REPRODUCIBILITY_CASES, ids=[case.case_id for case in _REPRODUCIBILITY_CASES])
def test_prompt_paraphrases_reproduce_same_request_plan_and_result(case: ReproducibilityCase) -> None:
    engine = Saida()
    profile = engine.profile(case.dataset)

    baseline_request_signature: dict[str, Any] | None = None
    baseline_plan_signature: dict[str, Any] | None = None
    baseline_result_signature: dict[str, Any] | None = None

    for prompt in case.prompts:
        request, warnings = engine.canonicalizer.normalize(prompt, case.dataset, profile, case.dataset.context)
        plan = engine.plan_builder.build_plan(request, profile, case.dataset.context)
        result = engine.analyze(case.dataset, prompt)

        assert warnings == []

        request_signature = _canonical_jsonable(_request_signature(request))
        plan_signature = _canonical_jsonable(_plan_signature(plan))
        result_signature = _canonical_jsonable(_result_signature(result))

        if baseline_request_signature is None:
            baseline_request_signature = request_signature
            baseline_plan_signature = plan_signature
            baseline_result_signature = result_signature
        else:
            assert request_signature == baseline_request_signature
            assert plan_signature == baseline_plan_signature
            assert result_signature == baseline_result_signature

    assert baseline_request_signature is not None
    assert baseline_plan_signature is not None
    assert baseline_result_signature is not None

    assert baseline_request_signature["intent_name"] == case.expected_request["intent_name"]
    assert baseline_request_signature["task_type_hint"] == case.expected_request["task_type_hint"]
    assert baseline_request_signature["target"] == case.expected_request["target"]
    assert baseline_request_signature["aggregation"] == case.expected_request["aggregation"]
    assert baseline_request_signature["group_by"] == case.expected_request["group_by"]
    assert baseline_request_signature["options"] == case.expected_request["options"]

    assert baseline_plan_signature["task_type"] == case.expected_plan["task_type"]
    assert [step["action"] for step in baseline_plan_signature["steps"]] == case.expected_plan["step_actions"]
    assert [step["parameters"] for step in baseline_plan_signature["steps"]] == case.expected_plan["step_parameters"]

    assert baseline_result_signature["result"]["name"] == case.expected_result["name"]
    assert baseline_result_signature["result"]["physical_shape"] == case.expected_result["physical_shape"]
    assert baseline_result_signature["result"]["logical_shape"] == case.expected_result["logical_shape"]
    if "value" in case.expected_result:
        assert baseline_result_signature["result"]["value"] == case.expected_result["value"]
