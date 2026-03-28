from __future__ import annotations

import pandas as pd
import pytest

from saida.exceptions import ValidationError
from saida.core.contracts import ColumnProfile, Dataset, DatasetProfile, SourceContext
from saida.llm import IntentProposal
from saida.plan_generation import RequestNormalizer


def build_profile() -> DatasetProfile:
    return DatasetProfile(
        dataset_name="sales",
        row_count=4,
        column_count=4,
        columns=[
            ColumnProfile(
                name="revenue",
                inferred_type="float",
                nullable=False,
                null_ratio=0.0,
                unique_count=4,
                distinct_ratio=1.0,
                sample_values=[100.0, 80.0],
                is_measure_candidate=True,
            ),
            ColumnProfile(
                name="region",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=2,
                distinct_ratio=0.5,
                sample_values=["West", "East"],
                is_dimension_candidate=True,
            ),
            ColumnProfile(
                name="segment",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=2,
                distinct_ratio=0.5,
                sample_values=["SMB", "Enterprise"],
                is_dimension_candidate=True,
            ),
            ColumnProfile(
                name="posted_at",
                inferred_type="datetime",
                nullable=False,
                null_ratio=0.0,
                unique_count=4,
                distinct_ratio=1.0,
                sample_values=["2026-03-01"],
                is_time_candidate=True,
            ),
        ],
        measure_columns=["revenue"],
        dimension_columns=["region", "segment"],
        time_columns=["posted_at"],
        identifier_columns=[],
    )


def build_dataset() -> Dataset:
    dataframe = pd.DataFrame(
        {
            "revenue": [100.0, 80.0, 60.0, 40.0],
            "region": ["West", "East", "West", "East"],
            "segment": ["SMB", "SMB", "Enterprise", "Enterprise"],
            "posted_at": ["2026-02-01", "2026-02-01", "2026-03-01", "2026-03-01"],
        }
    )
    return Dataset(name="sales", source_type="pandas", data=dataframe)


def build_statistical_profile() -> DatasetProfile:
    return DatasetProfile(
        dataset_name="tickets",
        row_count=6,
        column_count=6,
        columns=[
            ColumnProfile(
                name="resolution_hours",
                inferred_type="float",
                nullable=False,
                null_ratio=0.0,
                unique_count=6,
                distinct_ratio=1.0,
                sample_values=[2.1, 5.4],
                is_measure_candidate=True,
            ),
            ColumnProfile(
                name="csat_score",
                inferred_type="float",
                nullable=False,
                null_ratio=0.0,
                unique_count=6,
                distinct_ratio=1.0,
                sample_values=[4.2, 3.8],
                is_measure_candidate=True,
            ),
            ColumnProfile(
                name="team",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=3,
                distinct_ratio=0.5,
                sample_values=["Support", "Platform"],
                is_dimension_candidate=True,
            ),
            ColumnProfile(
                name="reopened_flag",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=2,
                distinct_ratio=0.33,
                sample_values=["yes", "no"],
                is_dimension_candidate=True,
            ),
            ColumnProfile(
                name="priority",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=3,
                distinct_ratio=0.5,
                sample_values=["Low", "Medium"],
                is_dimension_candidate=True,
            ),
            ColumnProfile(
                name="created_at",
                inferred_type="datetime",
                nullable=False,
                null_ratio=0.0,
                unique_count=6,
                distinct_ratio=1.0,
                sample_values=["2026-01-01"],
                is_time_candidate=True,
            ),
        ],
        measure_columns=["resolution_hours", "csat_score"],
        dimension_columns=["team", "reopened_flag", "priority"],
        time_columns=["created_at"],
        identifier_columns=[],
    )


def build_statistical_dataset() -> Dataset:
    dataframe = pd.DataFrame(
        {
            "resolution_hours": [2.1, 5.4, 6.8, 4.2, 7.1, 8.0],
            "csat_score": [4.7, 4.0, 3.6, 4.1, 3.5, 3.2],
            "team": ["Support", "Support", "Platform", "Platform", "Support", "Platform"],
            "reopened_flag": ["no", "no", "yes", "yes", "no", "yes"],
            "priority": ["Low", "Medium", "High", "Low", "High", "Medium"],
            "created_at": [
                "2026-01-01",
                "2026-01-02",
                "2026-01-03",
                "2026-01-04",
                "2026-01-05",
                "2026-01-06",
            ],
        }
    )
    return Dataset(name="tickets", source_type="pandas", data=dataframe)


def build_schema_profile() -> DatasetProfile:
    return DatasetProfile(
        dataset_name="support",
        row_count=4,
        column_count=5,
        columns=[
            ColumnProfile(
                name="ticket_id",
                inferred_type="string",
                nullable=False,
                null_ratio=0.0,
                unique_count=4,
                distinct_ratio=1.0,
                sample_values=["T1", "T2"],
                is_identifier_candidate=True,
                is_dimension_candidate=True,
            ),
            ColumnProfile(
                name="created_at",
                inferred_type="datetime",
                nullable=False,
                null_ratio=0.0,
                unique_count=4,
                distinct_ratio=1.0,
                sample_values=["2026-01-01"],
                is_time_candidate=True,
            ),
            ColumnProfile(
                name="resolution_hours",
                inferred_type="float",
                nullable=False,
                null_ratio=0.0,
                unique_count=4,
                distinct_ratio=1.0,
                sample_values=[4.2, 6.1],
                is_measure_candidate=True,
            ),
            ColumnProfile(
                name="priority",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=3,
                distinct_ratio=0.75,
                sample_values=["Low", "High"],
                is_dimension_candidate=True,
            ),
            ColumnProfile(
                name="csat_score",
                inferred_type="float",
                nullable=True,
                null_ratio=0.25,
                unique_count=3,
                distinct_ratio=0.75,
                sample_values=[4.8, 4.1],
                is_measure_candidate=True,
            ),
        ],
        measure_columns=["resolution_hours", "csat_score"],
        dimension_columns=["ticket_id", "priority"],
        time_columns=["created_at"],
        identifier_columns=["ticket_id"],
    )


def build_schema_dataset() -> Dataset:
    dataframe = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3", "T4"],
            "created_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            "resolution_hours": [4.2, 6.1, 3.4, 8.0],
            "priority": ["Low", "Medium", "High", "Medium"],
            "csat_score": [4.8, None, 4.1, 3.9],
        }
    )
    return Dataset(name="support", source_type="pandas", data=dataframe)


def build_tabular_profile() -> DatasetProfile:
    return DatasetProfile(
        dataset_name="tickets",
        row_count=6,
        column_count=6,
        columns=[
            ColumnProfile(
                name="ticket_id",
                inferred_type="string",
                nullable=False,
                null_ratio=0.0,
                unique_count=6,
                distinct_ratio=1.0,
                sample_values=["T1", "T2"],
                is_identifier_candidate=True,
                is_dimension_candidate=True,
            ),
            ColumnProfile(
                name="created_at",
                inferred_type="datetime",
                nullable=False,
                null_ratio=0.0,
                unique_count=6,
                distinct_ratio=1.0,
                sample_values=["2026-01-01"],
                is_time_candidate=True,
            ),
            ColumnProfile(
                name="resolution_hours",
                inferred_type="float",
                nullable=False,
                null_ratio=0.0,
                unique_count=6,
                distinct_ratio=1.0,
                sample_values=[2.1, 5.4],
                is_measure_candidate=True,
            ),
            ColumnProfile(
                name="priority",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=3,
                distinct_ratio=0.5,
                sample_values=["Low", "Medium"],
                is_dimension_candidate=True,
            ),
            ColumnProfile(
                name="team",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=2,
                distinct_ratio=0.33,
                sample_values=["Support", "Platform"],
                is_dimension_candidate=True,
            ),
            ColumnProfile(
                name="reopened_flag",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=2,
                distinct_ratio=0.33,
                sample_values=["yes", "no"],
                is_dimension_candidate=True,
            ),
        ],
        measure_columns=["resolution_hours"],
        dimension_columns=["ticket_id", "priority", "team", "reopened_flag"],
        time_columns=["created_at"],
        identifier_columns=["ticket_id"],
    )


def test_normalizer_extracts_group_by_filters_and_time_reference() -> None:
    normalizer = RequestNormalizer()
    context = SourceContext(raw_markdown="", metric_definitions={"revenue": "total revenue"})

    request, warnings = normalizer.normalize(
        "Why did revenue drop in March by region for West?",
        build_dataset(),
        build_profile(),
        context,
    )

    assert warnings == []
    assert request.task_type_hint == "diagnostic"
    assert request.target == "revenue"
    assert request.group_by == ["region"]
    assert request.filters == {"region": "West"}
    assert request.time_reference == {"type": "month_name", "value": "march", "month": "3"}


def test_normalizer_extracts_quarter_and_multiple_group_triggers() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Show revenue across region and for each segment in Q1",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.task_type_hint == "descriptive"
    assert request.group_by == ["region", "segment"]
    assert request.time_reference == {"type": "quarter", "value": "q1", "quarter": "1"}


def test_normalizer_extracts_row_count_quarter_filter_prompt() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "How many rows are in Q1?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert warnings == []
    assert request.intent_name == "row_count"
    assert request.prompt_family == "row_count"
    assert request.aggregation == "count"
    assert request.filters == {"posted_at": {"op": "quarter_eq", "value": 1, "label": "q1"}}
    assert request.time_reference == {"type": "quarter", "value": "q1", "quarter": "1"}


def test_normalizer_uses_llm_canonical_question_to_resolve_clearer_prompt_family() -> None:
    normalizer = RequestNormalizer()
    proposal = IntentProposal(
        status="ready",
        canonical_question="Count rows for Q1",
        prompt_family_hint="row_count",
        confidence=0.93,
        warnings=["llm prompt path used"],
    )

    request, warnings = normalizer.normalize_with_proposal(
        "Count total rows in dataset for Q1",
        build_dataset(),
        build_profile(),
        proposal,
        None,
    )

    assert warnings == ["llm prompt path used"]
    assert request.intent_name == "row_count"
    assert request.prompt_family == "row_count"
    assert request.aggregation == "count"
    assert request.filters == {"posted_at": {"op": "quarter_eq", "value": 1, "label": "q1"}}
    assert request.time_reference == {"type": "quarter", "value": "q1", "quarter": "1"}
    assert request.options["canonical_question"] == "Count rows for Q1"
    assert request.options["canonical_question_used"] is True
    assert request.options["prompt_family_hint"] == "row_count"
    assert request.options["llm_confidence"] == 0.93


def test_normalizer_rule_semantic_intent_promotes_count_total_rows_to_row_count() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "Count total rows in dataset for Q1",
        build_dataset(),
        build_profile(),
        None,
    )

    assert warnings == []
    assert request.intent_name == "row_count"
    assert request.prompt_family == "row_count"
    assert request.aggregation == "count"
    assert request.filters == {"posted_at": {"op": "quarter_eq", "value": 1, "label": "q1"}}
    assert request.time_reference == {"type": "quarter", "value": "q1", "quarter": "1"}
    assert request.options["semantic_intent"] == {
        "operation": "count",
        "object_kind": "rows",
        "expected_result_shape": "count",
        "source": "rules",
    }


def test_normalizer_rule_semantic_intent_keeps_show_rows_prompt_tabular() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "Show every row in dataset for Q1",
        build_dataset(),
        build_profile(),
        None,
    )

    assert warnings == []
    assert request.intent_name == "tabular_query"
    assert request.prompt_family == "tabular_record_retrieval"
    assert request.filters == {"posted_at": {"op": "quarter_eq", "value": 1, "label": "q1"}}
    assert request.options["semantic_intent"] == {
        "operation": "list",
        "object_kind": "rows",
        "expected_result_shape": "recordset",
        "source": "rules",
    }


def test_normalizer_uses_llm_semantic_proposal_without_canonical_question() -> None:
    normalizer = RequestNormalizer()
    proposal = IntentProposal(
        status="ready",
        operation="count",
        object_kind="distinct_values",
        object_ref="region",
        expected_result_shape="count",
        warnings=["llm prompt path used"],
    )

    request, warnings = normalizer.normalize_with_proposal(
        "Tell me about region variety",
        build_dataset(),
        build_profile(),
        proposal,
        None,
    )

    assert warnings == ["llm prompt path used"]
    assert request.intent_name == "distinct_value_count"
    assert request.prompt_family == "distinct_value_count"
    assert request.target == "region"
    assert request.options["semantic_intent"] == {
        "operation": "count",
        "object_kind": "distinct_values",
        "object_ref": "region",
        "expected_result_shape": "count",
        "source": "llm+rules",
    }


def test_normalizer_rejects_empty_question() -> None:
    normalizer = RequestNormalizer()

    with pytest.raises(ValidationError, match="question cannot be empty"):
        normalizer.normalize("", build_dataset(), build_profile(), None)


def test_normalizer_rejects_missing_target_when_no_measure_columns_exist() -> None:
    normalizer = RequestNormalizer()
    profile = build_profile()
    profile.measure_columns = []

    with pytest.raises(ValidationError, match="No target metric could be resolved"):
        normalizer.normalize("Show something interesting", build_dataset(), profile, None)


def test_normalizer_uses_first_measure_only_for_clear_exploratory_prompt() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize("Show data", build_dataset(), build_profile(), None)

    assert request.target == "revenue"
    assert request.options["target_resolution_source"] == "first_measure_fallback"
    assert request.options.get("analysis_outcome") is None
    assert any("inside exploratory metric overview" in warning for warning in warnings)


def test_normalizer_clarifies_grouped_prompt_without_metric_target() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize("Show data by region", build_dataset(), build_profile(), None)

    assert request.target is None
    assert request.group_by == ["region"]
    assert request.options["analysis_outcome"] == "clarify"
    assert "Please clarify which metric you want to analyze by region." in request.options["llm_message"]
    assert any("held for clarification" in warning for warning in warnings)


@pytest.mark.parametrize(
    ("question", "expected_intent_name"),
    [
        ("Total number of columns in the dataset", "column_count"),
        ("How many columns in the dataset?", "column_count"),
        ("How many fields does the dataset have?", "column_count"),
        ("How many numeric columns are there?", "numeric_column_count"),
        ("How many categorical columns are there?", "categorical_column_count"),
        ("How many measure columns are there?", "measure_count"),
        ("How many dimension columns are there?", "dimension_count"),
        ("How many time columns are there?", "time_column_count"),
        ("How many identifier columns are there?", "identifier_count"),
        ("How many high-cardinality columns are there?", "high_cardinality_count"),
    ],
)
def test_normalizer_resolves_supported_metadata_count_prompts(
    question: str,
    expected_intent_name: str,
) -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(question, build_schema_dataset(), build_schema_profile(), None)

    assert request.target is None
    assert request.intent_name == expected_intent_name
    assert request.prompt_family == expected_intent_name
    assert request.aggregation is None
    assert request.group_by is None
    assert request.options.get("analysis_outcome") is None
    assert warnings == []


@pytest.mark.parametrize(
    "question",
    [
        "How many unique team values are there?",
        "How many different team types are there?",
        "How many distinct team categories are there?",
    ],
)
def test_normalizer_resolves_distinct_value_count_prompts(question: str) -> None:
    normalizer = RequestNormalizer()
    dataset = build_statistical_dataset()
    profile = build_statistical_profile()

    request, warnings = normalizer.normalize(question, dataset, profile, None)

    assert request.intent_name == "distinct_value_count"
    assert request.prompt_family == "distinct_value_count"
    assert request.target == "team"
    assert request.aggregation is None
    assert request.group_by is None
    assert request.options.get("analysis_outcome") is None
    assert warnings == []


def test_normalizer_extracts_relative_time_reference() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize("Show revenue for last month", build_dataset(), build_profile(), None)

    assert request.time_reference == {"type": "relative_period", "value": "last_month"}


def test_normalizer_extracts_horizon_from_prompt() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize("Forecast revenue for 3 months", build_dataset(), build_profile(), None)

    assert request.horizon == 3
    assert request.task_type_hint == "forecasting"


def test_normalizer_extracts_average_aggregation() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize("What is the average revenue?", build_dataset(), build_profile(), None)

    assert request.target == "revenue"
    assert request.aggregation == "mean"


def test_normalizer_extracts_highest_aggregation() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize("Show highest revenue", build_dataset(), build_profile(), None)

    assert request.target == "revenue"
    assert request.aggregation == "max"


def test_normalizer_extracts_lowest_aggregation() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize("Show lowest revenue", build_dataset(), build_profile(), None)

    assert request.target == "revenue"
    assert request.aggregation == "min"


def test_normalizer_preserves_explicit_dimension_target_for_unsupported_aggregation() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize("What is the average region?", build_dataset(), build_profile(), None)

    assert request.target == "region"
    assert request.aggregation == "mean"
    assert warnings == []


def test_normalizer_preserves_explicit_time_target_for_unsupported_aggregation() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize("What is the highest posted_at?", build_dataset(), build_profile(), None)

    assert request.target == "posted_at"
    assert request.aggregation == "max"
    assert warnings == []


def test_normalizer_uses_context_metric_aliases() -> None:
    normalizer = RequestNormalizer()
    context = SourceContext(raw_markdown="", metric_definitions={"profit": "net profit"})

    request, _ = normalizer.normalize("Show profit by region", build_dataset(), build_profile(), context)

    assert request.target == "profit"


def test_normalizer_extracts_equals_filters() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize("Show revenue where region=West", build_dataset(), build_profile(), None)

    assert request.filters == {"region": "West"}


def test_normalizer_extracts_multiple_natural_filters() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize("Show revenue for West SMB", build_dataset(), build_profile(), None)

    assert request.filters == {"region": "West", "segment": "SMB"}


def test_normalizer_extracts_exclusion_filter_from_without_phrase() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize("Show revenue without West", build_dataset(), build_profile(), None)

    assert request.filters == {"region": {"op": "neq", "value": "West"}}


def test_normalizer_extracts_implied_flag_filter() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Only reopened tickets",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert request.filters == {"reopened_flag": "yes"}


def test_normalizer_extracts_implied_flag_exclusion_filter() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Exclude reopened tickets",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert request.filters == {"reopened_flag": {"op": "neq", "value": "yes"}}


def test_normalizer_extracts_year_filter() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize("Show revenue for West in 2026", build_dataset(), build_profile(), None)

    assert request.filters == {"region": "West", "posted_at": {"op": "year_eq", "value": 2026}}


def test_normalizer_extracts_month_filter() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize("Show revenue for West in March", build_dataset(), build_profile(), None)

    assert request.filters == {"region": "West", "posted_at": {"op": "month_eq", "value": 3, "label": "march"}}


def test_normalizer_extracts_year_month_filter() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize("List all rows for January 2025", build_dataset(), build_profile(), None)

    assert request.filters == {
        "posted_at": {
            "op": "year_month_eq",
            "value": "2025-01",
            "year": 2025,
            "month": 1,
            "label": "january 2025",
        }
    }


@pytest.mark.parametrize(
    ("question", "expected_filter"),
    [
        (
            "List all rows on the 15th day of every month",
            {"posted_at": {"op": "day_of_month_eq", "value": 15, "label": "day 15 of every month"}},
        ),
        (
            "List all rows on Mondays",
            {"posted_at": {"op": "weekday_eq", "value": 0, "label": "monday"}},
        ),
        (
            "List all rows on weekdays",
            {"posted_at": {"op": "weekday_in", "values": [0, 1, 2, 3, 4], "label": "weekdays"}},
        ),
        (
            "List all rows on weekends",
            {"posted_at": {"op": "weekday_in", "values": [5, 6], "label": "weekends"}},
        ),
        (
            "List all rows on the first day of every month",
            {"posted_at": {"op": "month_start", "label": "first day of every month"}},
        ),
        (
            "List all rows on the last day of every month",
            {"posted_at": {"op": "month_end", "label": "last day of every month"}},
        ),
        (
            "List all rows for Q1",
            {"posted_at": {"op": "quarter_eq", "value": 1, "label": "q1"}},
        ),
        (
            "List all rows from the last 7 days",
            {"posted_at": {"op": "recent_window", "value": 7, "unit": "day", "label": "last 7 days"}},
        ),
        (
            "List all rows on the first Monday of every month",
            {"posted_at": {"op": "nth_weekday_of_month", "weekday": 0, "occurrence": 1, "label": "first monday of every month"}},
        ),
        (
            "List all rows on the last Friday of every month",
            {"posted_at": {"op": "nth_weekday_of_month", "weekday": 4, "occurrence": "last", "label": "last friday of every month"}},
        ),
    ],
)
def test_normalizer_extracts_extended_time_filters(
    question: str,
    expected_filter: dict[str, object],
) -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(question, build_dataset(), build_profile(), None)

    assert request.intent_name == "tabular_query"
    assert request.prompt_family == "tabular_record_retrieval"
    assert request.filters == expected_filter
    assert request.options.get("analysis_outcome") is None
    assert warnings == []


def test_normalizer_routes_all_tickets_with_recurring_time_filter_to_tabular_query() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "Show all tickets created on the 1st of each month",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert request.intent_name == "tabular_query"
    assert request.prompt_family == "tabular_record_retrieval"
    assert request.filters == {"created_at": {"op": "month_start", "label": "first day of every month"}}
    assert request.options.get("analysis_outcome") is None
    assert warnings == []


def test_normalizer_does_not_convert_diagnostic_month_prompt_into_time_filter() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize("Why did revenue drop in March?", build_dataset(), build_profile(), None)

    assert request.filters is None


def test_normalizer_does_not_convert_comparison_prompt_into_time_filter() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize("Compare revenue this year to last year", build_dataset(), build_profile(), None)

    assert request.filters is None


def test_normalizer_deduplicates_group_by_matches() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize("Show revenue by region across region", build_dataset(), build_profile(), None)

    assert request.group_by == ["region"]


def test_normalizer_sets_options_payload() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize("Show revenue", build_dataset(), build_profile(), None)

    assert request.options["dataset"] == "sales"
    assert request.options["nlp_backend"] == "rules"


def test_normalizer_detects_distinct_value_listing_for_dimension_prompt() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize("Give me a list of all segments", build_dataset(), build_profile(), None)

    assert warnings == []
    assert request.target == "segment"
    assert request.options["distinct_values"] is True


def test_normalizer_detects_distinct_value_listing_for_category_phrasing() -> None:
    normalizer = RequestNormalizer()
    profile = build_profile()
    profile.dimension_columns = ["region", "segment", "priority"]
    profile.columns.append(
        ColumnProfile(
            name="priority",
            inferred_type="category",
            nullable=False,
            null_ratio=0.0,
            unique_count=4,
            distinct_ratio=1.0,
            sample_values=["Low", "Medium"],
            is_dimension_candidate=True,
        )
    )
    dataset = build_dataset()
    dataset.data["priority"] = ["Low", "Medium", "High", "Urgent"]

    request, warnings = normalizer.normalize(
        "What are the different priority categories in the data?",
        dataset,
        profile,
        None,
    )

    assert warnings == []
    assert request.intent_name == "distinct_values"
    assert request.target == "priority"
    assert request.options["distinct_values"] is True


def test_normalizer_detects_row_count_intent() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize("How many data rows do we have?", build_dataset(), build_profile(), None)

    assert warnings == []
    assert request.intent_name == "row_count"
    assert request.target is None


def test_normalizer_detects_representation_ranking_intent() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "Which segment is the least represented in sales data?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert warnings == []
    assert request.intent_name == "representation_ranking"
    assert request.target == "segment"
    assert request.group_by == ["segment"]
    assert request.aggregation == "count"
    assert request.options["ranking_direction"] == "asc"


def test_normalizer_detects_column_inventory_intent() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize("What are the columns in the sales data?", build_dataset(), build_profile(), None)

    assert warnings == []
    assert request.intent_name == "column_inventory"
    assert request.target is None


def test_normalizer_detects_column_type_inventory_intent() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "What are the data types of each field or column in the data?",
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert warnings == []
    assert request.intent_name == "column_type_inventory"
    assert request.target is None


@pytest.mark.parametrize(
    "question",
    [
        "What is the data type of the created_at field in dataset?",
        "What type is created_at?",
    ],
)
def test_normalizer_detects_single_column_type_lookup(question: str) -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        question,
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert warnings == []
    assert request.intent_name == "column_type_inventory"
    assert request.target == "created_at"


def test_normalizer_keeps_multi_column_type_request_out_of_single_column_lookup() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "What are the data types of created_at and csat_score?",
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert warnings == []
    assert request.intent_name == "column_type_inventory"
    assert request.target is None


def test_normalizer_detects_schema_prompt_as_column_type_inventory() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "What is the schema of this data?",
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert request.intent_name == "column_type_inventory"


def test_normalizer_detects_numeric_column_inventory_intent() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Which columns are numeric?",
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert request.intent_name == "numeric_column_inventory"
    assert request.target is None


def test_normalizer_detects_categorical_column_inventory_intent() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Which fields are categorical?",
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert request.intent_name == "categorical_column_inventory"


def test_normalizer_detects_time_column_inventory_for_date_fields_prompt() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Which fields are dates?",
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert request.intent_name == "time_column_inventory"


def test_normalizer_detects_missing_value_inventory_intent() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Which columns have missing values?",
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert request.intent_name == "missing_value_inventory"


def test_normalizer_detects_identifier_inventory_intent() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Which columns are likely identifiers?",
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert request.intent_name == "identifier_inventory"


def test_normalizer_detects_high_cardinality_inventory_intent() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Which columns have many unique values?",
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert request.intent_name == "high_cardinality_inventory"


def test_normalizer_does_not_force_measure_target_for_schema_metadata_prompt() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "Which columns are numeric?",
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert warnings == []
    assert request.target is None


def test_normalizer_schema_metadata_prompts_work_without_measure_columns() -> None:
    normalizer = RequestNormalizer()
    profile = build_schema_profile()
    profile.measure_columns = []

    request, warnings = normalizer.normalize(
        "Which columns have missing values?",
        build_schema_dataset(),
        profile,
        None,
    )

    assert warnings == []
    assert request.intent_name == "missing_value_inventory"
    assert request.target is None


def test_normalizer_detects_time_coverage_years_intent() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "The data shows revenue for which years?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert warnings == []
    assert request.intent_name == "time_coverage"
    assert request.target is None
    assert request.options["time_coverage_mode"] == "years_present"


def test_normalizer_detects_time_coverage_months_intent() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "What months are present in the sales data?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "time_coverage"
    assert request.options["time_coverage_mode"] == "months_present"


def test_normalizer_detects_time_coverage_date_range_intent() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "What date range does the sales data cover?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "time_coverage"
    assert request.options["time_coverage_mode"] == "date_range"


def test_normalizer_detects_time_bucket_counts_by_year_intent() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "I need a list of years, and how many tickets created in those years.",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert warnings == []
    assert request.intent_name == "time_bucket_counts"
    assert request.target is None
    assert request.options["time_bucket"] == "year"


def test_normalizer_detects_time_bucket_counts_by_month_intent() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "How many tickets were created by month?",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert request.intent_name == "time_bucket_counts"
    assert request.options["time_bucket"] == "month"


def test_normalizer_detects_time_bucket_counts_by_quarter_intent() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "How many tickets were created by quarter?",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert request.intent_name == "time_bucket_counts"
    assert request.options["time_bucket"] == "quarter"


def test_normalizer_detects_time_bucket_breakdown_by_month_intent() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Show revenue by month",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "time_bucket_breakdown"
    assert request.target == "revenue"
    assert request.options["time_bucket"] == "month"


def test_normalizer_detects_time_bucket_breakdown_by_year_intent() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Show revenue by year",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "time_bucket_breakdown"
    assert request.options["time_bucket"] == "year"


def test_normalizer_detects_time_bucket_breakdown_by_quarter_intent() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Show revenue by quarter",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "time_bucket_breakdown"
    assert request.options["time_bucket"] == "quarter"


def test_normalizer_preserves_grouping_for_time_bucket_breakdown() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Show revenue by month for each region",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "time_bucket_breakdown"
    assert request.group_by == ["region"]


def test_normalizer_detects_time_period_comparison_for_this_month() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Compare revenue this month to last month",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "time_period_comparison"
    assert request.time_reference == {"type": "relative_period", "value": "this_month"}
    assert request.options["time_bucket"] == "month"


def test_normalizer_detects_time_period_comparison_for_this_quarter() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Compare revenue this quarter to last quarter",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "time_period_comparison"
    assert request.time_reference == {"type": "relative_period", "value": "this_quarter"}
    assert request.options["time_bucket"] == "quarter"


def test_normalizer_detects_time_period_comparison_for_this_year() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Compare revenue this year to last year",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "time_period_comparison"
    assert request.time_reference == {"type": "relative_period", "value": "this_year"}
    assert request.options["time_bucket"] == "year"


def test_normalizer_detects_time_value_existence_intent() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "The created_at column shows dates in 2025?",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert warnings == []
    assert request.intent_name == "existence_check"
    assert request.target == "created_at"
    assert request.options["existence_mode"] == "time_value"
    assert request.options["expected_year"] == 2025


def test_normalizer_detects_filtered_row_existence_intent() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Is West in the region column?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "existence_check"
    assert request.target is None
    assert request.filters == {"region": "West"}
    assert request.options["existence_mode"] == "filtered_rows"


def test_normalizer_detects_null_check_for_missing_values() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Does csat_score have missing values?",
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert request.intent_name == "existence_check"
    assert request.target == "csat_score"
    assert request.options["existence_mode"] == "null_check"
    assert request.options["null_expectation"] == "has_nulls"


def test_normalizer_detects_complete_check() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Is csat_score complete?",
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert request.intent_name == "existence_check"
    assert request.target == "csat_score"
    assert request.options["existence_mode"] == "null_check"
    assert request.options["null_expectation"] == "no_nulls"


def test_normalizer_detects_threshold_check_above() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Are any resolution hours above 20?",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert request.intent_name == "existence_check"
    assert request.target == "resolution_hours"
    assert request.options["existence_mode"] == "threshold_check"
    assert request.options["threshold_operator"] == "gt"
    assert request.options["threshold_value"] == 20.0


def test_normalizer_detects_threshold_check_below() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Is revenue below 0 anywhere?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "existence_check"
    assert request.target == "revenue"
    assert request.options["existence_mode"] == "threshold_check"
    assert request.options["threshold_operator"] == "lt"
    assert request.options["threshold_value"] == 0.0


def test_normalizer_detects_threshold_check_between() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Does csat_score fall between 3 and 5?",
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert request.intent_name == "existence_check"
    assert request.target == "csat_score"
    assert request.options["existence_mode"] == "threshold_check"
    assert request.options["threshold_operator"] == "between"
    assert request.options["lower_bound"] == 3.0
    assert request.options["upper_bound"] == 5.0


def test_normalizer_detects_numeric_property_check() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Is revenue numeric?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "existence_check"
    assert request.target == "revenue"
    assert request.options["existence_mode"] == "column_property_check"
    assert request.options["expected_property"] == "numeric"


def test_normalizer_detects_datetime_property_check() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Is created_at a datetime field?",
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert request.intent_name == "existence_check"
    assert request.target == "created_at"
    assert request.options["existence_mode"] == "column_property_check"
    assert request.options["expected_property"] == "datetime"


def test_normalizer_detects_identifier_property_check() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Is ticket_id likely an identifier?",
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert request.intent_name == "existence_check"
    assert request.target == "ticket_id"
    assert request.options["existence_mode"] == "column_property_check"
    assert request.options["expected_property"] == "identifier"


def test_normalizer_detects_dimension_property_check() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Is region a dimension?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "existence_check"
    assert request.target == "region"
    assert request.options["existence_mode"] == "column_property_check"
    assert request.options["expected_property"] == "dimension"


def test_normalizer_detects_missing_column_dimension_property_check() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Is territory a dimension?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "existence_check"
    assert request.target == "territory"
    assert request.options["existence_mode"] == "column_property_check"
    assert request.options["expected_property"] == "dimension"


def test_normalizer_detects_measure_property_check() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Is revenue a measure?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "existence_check"
    assert request.target == "revenue"
    assert request.options["existence_mode"] == "column_property_check"
    assert request.options["expected_property"] == "measure"


def test_normalizer_detects_high_cardinality_property_check() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Is ticket_id high cardinality?",
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert request.intent_name == "existence_check"
    assert request.target == "ticket_id"
    assert request.options["existence_mode"] == "column_property_check"
    assert request.options["expected_property"] == "high_cardinality"


@pytest.mark.parametrize(
    ("question", "expected_requested_column"),
    [
        ("Does the dataset have a created_at column?", "created_at"),
        ("Is there a missing_field column?", "missing_field"),
    ],
)
def test_normalizer_detects_column_presence_check(question: str, expected_requested_column: str) -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        question,
        build_schema_dataset(),
        build_schema_profile(),
        None,
    )

    assert request.intent_name == "existence_check"
    assert request.target is None
    assert request.options["existence_mode"] == "column_presence_check"
    assert request.options["requested_column"] == expected_requested_column


def test_normalizer_detects_representation_ranking_for_most_entity_prompt() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Which region has the most sales?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "representation_ranking"
    assert request.target == "region"
    assert request.options["ranking_direction"] == "desc"
    assert request.options["ranking_limit"] == 1


def test_normalizer_detects_natural_significance_prompt() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "Do regions differ in revenue?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert warnings == []
    assert request.task_type_hint == "statistical"
    assert request.target == "revenue"
    assert request.group_by == ["region"]
    assert request.options["statistical_test"] == "significance_inference"


def test_normalizer_detects_significant_difference_prompt() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Is there a significant difference in revenue by region?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.target == "revenue"
    assert request.group_by == ["region"]
    assert request.options["statistical_test"] == "significance_inference"


def test_normalizer_detects_natural_confidence_range_prompt() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "What range are we 95% confident revenue falls in?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.task_type_hint == "statistical"
    assert request.target == "revenue"
    assert request.options["statistical_test"] == "confidence_interval"
    assert request.options["confidence_level"] == 0.95


def test_normalizer_defaults_confidence_interval_level_when_missing() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "What confidence range do we have for revenue?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.options["statistical_test"] == "confidence_interval"
    assert request.options["confidence_level"] == 0.95


def test_normalizer_detects_natural_power_analysis_prompt() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Do we have enough data to detect a difference in revenue by region?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.task_type_hint == "statistical"
    assert request.target == "revenue"
    assert request.group_by == ["region"]
    assert request.options["statistical_test"] == "power_analysis"


def test_normalizer_extracts_desired_power_from_natural_prompt() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Do we have enough data to detect a difference in revenue by region at 90% power?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.options["statistical_test"] == "power_analysis"
    assert request.options["desired_power"] == 0.90


def test_normalizer_detects_natural_sample_size_prompt() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "How many rows per group do we need for revenue by region?",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.task_type_hint == "statistical"
    assert request.target == "revenue"
    assert request.group_by == ["region"]
    assert request.options["statistical_test"] == "sample_size_estimate"


def test_normalizer_extracts_regression_columns_from_natural_prompt() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "Does resolution_hours significantly affect csat_score?",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert warnings == []
    assert request.task_type_hint == "statistical"
    assert request.target == "csat_score"
    assert request.group_by is None
    assert request.options["statistical_test"] == "regression_significance"
    assert request.options["feature_columns"] == ["resolution_hours"]


def test_normalizer_extracts_regression_columns_in_prompt_order() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Does csat_score significantly affect resolution_hours?",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert request.target == "resolution_hours"
    assert request.options["feature_columns"] == ["csat_score"]


def test_normalizer_does_not_force_statistical_mode_for_open_ended_factor_prompt() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "Which factors significantly affect customer satisfaction?",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert request.task_type_hint == "statistical"
    assert request.options.get("statistical_test") is None
    assert request.options["analysis_outcome"] == "clarify"
    assert "Please clarify which metric you want to analyze." in request.options["llm_message"]
    assert any("held for clarification" in warning for warning in warnings)


def test_normalizer_detects_top_n_row_ranking_intent() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "Show top 5 revenue values",
        build_dataset(),
        build_profile(),
        None,
    )

    assert warnings == []
    assert request.intent_name == "row_ranking"
    assert request.target == "revenue"
    assert request.options["ranking_direction"] == "desc"
    assert request.options["ranking_limit"] == 5


def test_normalizer_detects_bottom_n_row_ranking_intent() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Show bottom 3 revenue values",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "row_ranking"
    assert request.options["ranking_direction"] == "asc"
    assert request.options["ranking_limit"] == 3


def test_normalizer_detects_top_n_group_ranking_intent() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Show top 4 revenue by region",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "group_ranking"
    assert request.target == "revenue"
    assert request.group_by == ["region"]
    assert request.options["ranking_limit"] == 4


def test_normalizer_detects_bottom_n_group_ranking_intent() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Show bottom 2 revenue by region",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "group_ranking"
    assert request.options["ranking_direction"] == "asc"
    assert request.options["ranking_limit"] == 2


def test_normalizer_detects_word_number_in_ranking_request() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Show top five revenue values",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "row_ranking"
    assert request.options["ranking_limit"] == 5


def test_normalizer_resolves_tokenized_target_for_row_ranking() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "What is the top 5 longest hours of resolution?",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert warnings == []
    assert request.intent_name == "row_ranking"
    assert request.target == "resolution_hours"
    assert request.options["ranking_limit"] == 5


def test_normalizer_does_not_override_distinct_values_with_top_keyword_without_limit() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Show top priority categories",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert request.intent_name == "distinct_values"
    assert request.target == "priority" or request.target is not None


def test_normalizer_leaves_highest_aggregation_as_scalar_request() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Show highest revenue",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name is None
    assert request.aggregation == "max"


_NORMALIZER_QUESTION_CASES = [
    (
        f"Show revenue by region for West in march case {index}",
        "descriptive",
        "revenue",
        ["region"],
    )
    for index in range(1, 45)
] + [
    (
        f"Why did revenue drop in March by region case {index}",
        "diagnostic",
        "revenue",
        ["region"],
    )
    for index in range(45, 89)
]


@pytest.mark.parametrize(("question", "task_type", "expected_target", "expected_group_by"), _NORMALIZER_QUESTION_CASES)
def test_normalizer_handles_many_supported_question_shapes(
    question: str,
    task_type: str,
    expected_target: str,
    expected_group_by: list[str],
) -> None:
    normalizer = RequestNormalizer()
    request, _ = normalizer.normalize(question, build_dataset(), build_profile(), None)

    assert request.task_type_hint == task_type
    assert request.target == expected_target
    assert request.group_by == expected_group_by


def test_normalizer_detects_filtered_row_tabular_query() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Give me the list of all rows in dataset that have their tickets marked as reopened.",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert request.intent_name == "tabular_query"
    assert request.filters == {"reopened_flag": "yes"}
    assert request.options["selected_columns"] == []


def test_normalizer_detects_tabular_query_with_selected_columns() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Show ticket_id and priority sorted by created_at descending",
        build_schema_dataset(),
        build_tabular_profile(),
        None,
    )

    assert request.intent_name == "tabular_query"
    assert request.options["selected_columns"] == ["ticket_id", "priority", "created_at"]
    assert request.options["sort_by"] == "created_at"
    assert request.options["sort_direction"] == "desc"


def test_normalizer_detects_tabular_limit_and_pagination() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Return first 5 rows page 2 page size 2 sorted by created_at",
        build_schema_dataset(),
        build_tabular_profile(),
        None,
    )

    assert request.intent_name == "tabular_query"
    assert request.options["limit"] == 5
    assert request.options["page"] == 2
    assert request.options["page_size"] == 2
    assert request.options["sort_by"] == "created_at"


def test_normalizer_detects_grouped_tabular_query() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Show revenue by region as table",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name == "grouped_tabular_query"
    assert request.target == "revenue"
    assert request.group_by == ["region"]
    assert request.aggregation == "sum"


def test_normalizer_detects_grouped_count_table_query_without_target() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Show a table of tickets by team",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert request.intent_name == "grouped_tabular_query"
    assert request.group_by == ["team"]
    assert request.target is None
    assert request.aggregation == "count"


def test_normalizer_keeps_distinct_values_prompt_out_of_tabular_query() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Give me a list of all priorities",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert request.intent_name == "distinct_values"


def test_normalizer_keeps_non_table_group_prompt_out_of_grouped_tabular_query() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Show revenue by region",
        build_dataset(),
        build_profile(),
        None,
    )

    assert request.intent_name is None


def test_normalizer_detects_latest_rows_sorting() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "List the latest rows for reopened tickets",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert request.intent_name == "tabular_query"
    assert request.options["sort_by"] == "created_at"
    assert request.options["sort_direction"] == "desc"


def test_normalizer_defaults_tabular_page_size_from_limit() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Show first 3 rows sorted by created_at",
        build_schema_dataset(),
        build_tabular_profile(),
        None,
    )

    assert request.intent_name == "tabular_query"
    assert request.options["limit"] == 3
    assert request.options["page_size"] == 3


def test_normalizer_uses_empty_selected_columns_for_all_rows_prompt() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Show all rows sorted by created_at",
        build_schema_dataset(),
        build_tabular_profile(),
        None,
    )

    assert request.intent_name == "tabular_query"
    assert request.options["selected_columns"] == []


def test_normalizer_detects_dataset_slice_request_with_limit() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Give me 20 tickets from the data set",
        build_statistical_dataset(),
        build_statistical_profile(),
        None,
    )

    assert request.intent_name == "tabular_query"
    assert request.options["limit"] == 20
    assert request.options["selected_columns"] == []
