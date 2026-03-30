from __future__ import annotations

from pathlib import Path
import re

import pandas as pd
import pytest

from saida import PromptAnalysisFrontend
from saida.core import Dataset
from saida.core.contracts import AnalysisRequest
from saida.plan_generation import (
    AnalysisPlanner,
    build_default_prompt_family_catalog,
    build_prompt_plan_contract,
    derive_prompt_family,
)


def build_support_dataset() -> Dataset:
    return Dataset(
        name="support",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "ticket_id": ["T1", "T2", "T3", "T4", "T5"],
                "created_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"],
                "channel": ["Email", "Phone", "Email", "Chat", "Email"],
                "priority": ["High", "High", "Low", "Low", "Medium"],
                "team": ["Support", "Platform", "Support", "Payments", "Infrastructure"],
                "resolution_hours": [4.2, 6.1, 3.4, 8.0, 5.5],
            }
        ),
    )


@pytest.mark.parametrize(
    ("analysis_request", "expected_family"),
    [
        (
            AnalysisRequest(
                question="Give me the total tickets per channel.",
                intent_name="grouped_tabular_query",
                task_type_hint="descriptive",
                aggregation="count",
                group_by=["channel"],
                options={"intent_name": "grouped_tabular_query"},
            ),
            "grouped_entity_count",
        ),
        (
            AnalysisRequest(
                question="What is the data type of created_at?",
                intent_name="column_type_inventory",
                task_type_hint="descriptive",
                target="created_at",
            ),
            "column_type_lookup",
        ),
        (
            AnalysisRequest(
                question="Does the dataset have a created_at column?",
                intent_name="existence_check",
                task_type_hint="descriptive",
                options={"existence_mode": "column_presence_check", "requested_column": "created_at"},
            ),
            "column_presence_check",
        ),
        (
            AnalysisRequest(
                question="How many fields does the dataset have?",
                intent_name="column_count",
                task_type_hint="descriptive",
            ),
            "column_count",
        ),
        (
            AnalysisRequest(
                question="How many unique team values are there?",
                intent_name="distinct_value_count",
                task_type_hint="descriptive",
                target="team",
            ),
            "distinct_value_count",
        ),
        (
            AnalysisRequest(
                question="Which channel has the most tickets?",
                intent_name="representation_ranking",
                task_type_hint="descriptive",
                target="channel",
                aggregation="count",
                group_by=["channel"],
                options={"ranking_limit": 1, "ranking_direction": "desc"},
            ),
            "representation_ranking",
        ),
        (
            AnalysisRequest(
                question="Show the latest rows.",
                intent_name="tabular_query",
                task_type_hint="descriptive",
                options={"page": 1, "page_size": 50},
            ),
            "tabular_record_retrieval",
        ),
        (
            AnalysisRequest(
                question="Show revenue by region.",
                task_type_hint="descriptive",
                target="resolution_hours",
                group_by=["channel"],
            ),
            "exploratory_metric_overview",
        ),
    ],
    ids=[
        "grouped-entity-count",
        "column-type-lookup",
        "column-presence-check",
        "column-count",
        "distinct-value-count",
        "representation-ranking",
        "tabular-record-retrieval",
        "exploratory-metric-overview",
    ],
)
def test_derive_prompt_family_from_request_matrix(
    analysis_request: AnalysisRequest,
    expected_family: str,
) -> None:
    assert derive_prompt_family(analysis_request) == expected_family


def test_prompt_family_catalog_markdown_snapshot_matches_live_catalog() -> None:
    catalog = build_default_prompt_family_catalog()
    catalog_path = Path(__file__).resolve().parents[3] / "docs" / "reference" / "prompt-family-catalog.md"
    content = catalog_path.read_text(encoding="utf-8")
    normalized_lines = [
        line
        for line in content.splitlines()
        if not line.startswith("![SAIDA Banner]")
        and not line.startswith("[![Version]")
        and not line.startswith("[![License]")
        and not line.startswith("[![Python]")
    ]
    body = "\n".join(normalized_lines).strip() + "\n"
    body = re.sub(r"\n{3,}", "\n\n", body)
    expected = re.sub(r"\n{3,}", "\n\n", catalog.to_markdown())

    assert body == expected


@pytest.mark.parametrize(
    "family_id",
    [
        "row_count",
        "column_count",
        "column_type_lookup",
        "column_presence_check",
        "distinct_value_count",
        "distinct_value_listing",
        "numeric_column_count",
        "categorical_column_count",
        "measure_count",
        "dimension_count",
        "time_column_count",
        "identifier_count",
        "high_cardinality_count",
        "grouped_entity_count",
        "representation_ranking",
    ],
)
def test_high_volume_prompt_families_use_template_plan_compilation(family_id: str) -> None:
    catalog = build_default_prompt_family_catalog()
    family_spec = catalog.get(family_id)

    assert family_spec is not None
    assert family_spec.plan_steps
    assert family_spec.to_dict()["plan_compilation"] == "template"


def test_tabular_record_retrieval_uses_graph_planning_instead_of_inline_template_steps() -> None:
    catalog = build_default_prompt_family_catalog()
    family_spec = catalog.get("tabular_record_retrieval")

    assert family_spec is not None
    assert family_spec.plan_steps == ()
    assert family_spec.to_dict()["plan_compilation"] == "manual"
    assert family_spec.allowed_plan_actions == ("filter_frame", "sort_frame", "limit_frame", "select_columns", "tabular_query")


@pytest.mark.parametrize(
    "family_id",
    [
        "row_count",
        "column_count",
        "column_type_lookup",
        "column_presence_check",
        "distinct_value_count",
        "distinct_value_listing",
        "numeric_column_count",
        "categorical_column_count",
        "measure_count",
        "dimension_count",
        "time_column_count",
        "identifier_count",
        "high_cardinality_count",
        "grouped_entity_count",
        "representation_ranking",
        "tabular_record_retrieval",
    ],
)
def test_high_volume_prompt_families_use_template_result_shaping(family_id: str) -> None:
    catalog = build_default_prompt_family_catalog()
    family_spec = catalog.get(family_id)

    assert family_spec is not None
    assert family_spec.primary_result is not None
    assert family_spec.to_dict()["result_compilation"] == "template"


def test_prompt_plan_contract_exposes_prompt_family_and_family_spec() -> None:
    engine = PromptAnalysisFrontend()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    request = AnalysisRequest(
        question="Give me the total tickets per channel.",
        intent_name="grouped_tabular_query",
        task_type_hint="descriptive",
        aggregation="count",
        group_by=["channel"],
        options={"intent_name": "grouped_tabular_query"},
    )

    contract = build_prompt_plan_contract(request, profile)

    assert contract.prompt_family == "grouped_entity_count"
    assert contract.family_spec is not None
    assert contract.family_spec["family_id"] == "grouped_entity_count"
    assert not any(issue.code == "prompt_family_request_invariant" for issue in contract.validation_issues)


def test_prompt_plan_contract_flags_prompt_family_request_mismatch() -> None:
    engine = PromptAnalysisFrontend()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    request = AnalysisRequest(
        question="What are the columns?",
        prompt_family="grouped_entity_count",
        intent_name="column_inventory",
        task_type_hint="descriptive",
        options={"intent_name": "column_inventory"},
    )

    contract = build_prompt_plan_contract(request, profile)

    mismatch_messages = [
        issue.message
        for issue in contract.validation_issues
        if issue.code == "prompt_family_request_invariant"
    ]
    assert mismatch_messages
    assert "Expected intent_name" in mismatch_messages[0]


@pytest.mark.parametrize(
    ("question", "expected_family"),
    [
        ("Give me the total tickets per channel.", "grouped_entity_count"),
        ("What is the data type of the created_at field?", "column_type_lookup"),
        ("Does the dataset have a created_at column?", "column_presence_check"),
        ("How many columns are in the dataset?", "column_count"),
        ("How many unique team values are there?", "distinct_value_count"),
        ("How many high-cardinality columns are there?", "high_cardinality_count"),
        ("Which channel has the most tickets?", "representation_ranking"),
        ("List all team values.", "distinct_value_listing"),
        ("Show resolution_hours by channel.", "exploratory_metric_overview"),
    ],
    ids=[
        "grouped-entity-count",
        "column-type-lookup",
        "column-presence-check",
        "column-count",
        "distinct-value-count",
        "high-cardinality-count",
        "representation-ranking",
        "distinct-value-listing",
        "exploratory-metric-overview",
    ],
)
def test_engine_response_exposes_prompt_family_end_to_end(question: str, expected_family: str) -> None:
    engine = PromptAnalysisFrontend()
    dataset = build_support_dataset()

    result = engine.analyze(dataset, question)

    interpretation = result.response["interpretation"]
    prompt_contract = interpretation["prompt_contract"]

    assert interpretation["prompt_family"] == expected_family
    assert result.response["meta"]["prompt_family"] == expected_family
    assert prompt_contract["prompt_family"] == expected_family
    assert prompt_contract["family_spec"]["family_id"] == expected_family


def test_planner_builds_grouped_entity_count_plan_from_prompt_family_only() -> None:
    planner = AnalysisPlanner()
    engine = PromptAnalysisFrontend()
    profile = engine.profile(build_support_dataset())
    request = AnalysisRequest(
        question="Give me the total tickets per channel.",
        prompt_family="grouped_entity_count",
        task_type_hint="descriptive",
        aggregation="count",
        group_by=["channel"],
        options={"page": 1, "page_size": 50, "sort_direction": "asc"},
    )

    plan = planner.build_plan(request, profile)

    assert request.intent_name is None
    assert [step.action for step in plan.steps] == ["group_frame", "aggregate_frame", "sort_frame"]
    assert plan.steps[0].parameters["group_by"] == ["channel"]
    assert plan.steps[1].parameters["aggregation"] == "count"


def test_planner_builds_column_type_lookup_plan_from_prompt_family_only() -> None:
    planner = AnalysisPlanner()
    engine = PromptAnalysisFrontend()
    profile = engine.profile(build_support_dataset())
    request = AnalysisRequest(
        question="What is the data type of created_at?",
        prompt_family="column_type_lookup",
        task_type_hint="descriptive",
        target="created_at",
    )

    plan = planner.build_plan(request, profile)

    assert request.intent_name is None
    assert [step.action for step in plan.steps] == ["column_type_inventory"]
    assert plan.steps[0].parameters == {"target": "created_at"}


def test_planner_builds_column_presence_plan_from_contract_using_prompt_family() -> None:
    planner = AnalysisPlanner()
    engine = PromptAnalysisFrontend()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    request = AnalysisRequest(
        question="Does the dataset have a created_at column?",
        prompt_family="column_presence_check",
        task_type_hint="descriptive",
        options={"requested_column": "created_at"},
    )
    contract = build_prompt_plan_contract(request, profile)

    plan = planner.build_plan_from_contract(contract, request, profile)

    assert [step.action for step in plan.steps] == ["column_presence_check"]
    assert plan.steps[0].parameters == {"requested_column": "created_at"}


def test_template_family_spec_can_compile_grouped_entity_count_steps() -> None:
    catalog = build_default_prompt_family_catalog()
    family_spec = catalog.get("grouped_entity_count")
    request = AnalysisRequest(
        question="Give me the total tickets per channel.",
        prompt_family="grouped_entity_count",
        task_type_hint="descriptive",
        aggregation="count",
        group_by=["channel"],
        options={"sort_direction": "asc", "page": 1, "page_size": 50},
    )
    engine = PromptAnalysisFrontend()
    profile = engine.profile(build_support_dataset())

    compiled_steps = family_spec.compile_steps(request, profile) if family_spec is not None else []

    assert [step.action for step in compiled_steps] == ["grouped_tabular_query"]
    assert compiled_steps[0].parameters["aggregation"] == "count"
    assert compiled_steps[0].parameters["group_by"] == ["channel"]


def test_prompt_plan_contract_exposes_source_materialization_request() -> None:
    engine = PromptAnalysisFrontend()
    dataset = build_support_dataset()
    dataset.source_type = "sqlite"
    profile = engine.profile(dataset)
    request = AnalysisRequest(
        question="Give me the total tickets per channel.",
        prompt_family="grouped_entity_count",
        intent_name="grouped_tabular_query",
        task_type_hint="descriptive",
        aggregation="count",
        group_by=["channel"],
        options={
            "source_materialization_request": {
                "source_type": "sqlite",
                "mode": "grouped_table",
                "required_columns": ["channel"],
                "preferred_base_table": None,
                "candidate_measure_columns": [],
                "candidate_dimension_columns": ["channel"],
                "candidate_time_columns": [],
                "reasons": ["group_by"],
            }
        },
    )

    contract = build_prompt_plan_contract(request, profile)

    assert contract.source_materialization_request is not None
    assert contract.source_materialization_request["source_type"] == "sqlite"
    assert contract.source_materialization_request["required_columns"] == ["channel"]

