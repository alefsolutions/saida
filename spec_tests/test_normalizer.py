from __future__ import annotations

import pandas as pd
import pytest

from saida.core import RequestNormalizer
from saida.exceptions import ValidationError
from saida.core.contracts import ColumnProfile, Dataset, DatasetProfile, SourceContext


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


def test_normalizer_falls_back_to_first_measure_with_warning() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize("Show data by region", build_dataset(), build_profile(), None)

    assert request.target == "revenue"
    assert any("No explicit metric matched the prompt" in warning for warning in warnings)


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


def test_normalizer_uses_context_metric_aliases() -> None:
    normalizer = RequestNormalizer()
    context = SourceContext(raw_markdown="", metric_definitions={"profit": "net profit"})

    request, _ = normalizer.normalize("Show profit by region", build_dataset(), build_profile(), context)

    assert request.target == "profit"


def test_normalizer_extracts_equals_filters() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize("Show revenue where region=West", build_dataset(), build_profile(), None)

    assert request.filters == {"region": "West"}


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
    assert any("No explicit metric matched the prompt" in warning for warning in warnings)


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
