from __future__ import annotations

import pandas as pd

from saida.core.contracts import ColumnProfile, Dataset, DatasetProfile
from saida.llm import IntentProposal
from saida.plan_generation import PromptEntityExtractor, RequestNormalizer


def build_collision_profile() -> DatasetProfile:
    return DatasetProfile(
        dataset_name="sales_collision",
        row_count=3,
        column_count=7,
        columns=[
            ColumnProfile(
                name="total_sales",
                inferred_type="float",
                nullable=False,
                null_ratio=0.0,
                unique_count=3,
                distinct_ratio=1.0,
                sample_values=[100.0, 80.0],
                is_measure_candidate=True,
            ),
            ColumnProfile(
                name="average_order_value",
                inferred_type="float",
                nullable=False,
                null_ratio=0.0,
                unique_count=3,
                distinct_ratio=1.0,
                sample_values=[55.0, 72.0],
                is_measure_candidate=True,
            ),
            ColumnProfile(
                name="mean_score",
                inferred_type="float",
                nullable=False,
                null_ratio=0.0,
                unique_count=3,
                distinct_ratio=1.0,
                sample_values=[0.8, 0.6],
                is_measure_candidate=True,
            ),
            ColumnProfile(
                name="count_flag",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=2,
                distinct_ratio=0.67,
                sample_values=["yes", "no"],
                is_dimension_candidate=True,
            ),
            ColumnProfile(
                name="measure_score",
                inferred_type="float",
                nullable=False,
                null_ratio=0.0,
                unique_count=3,
                distinct_ratio=1.0,
                sample_values=[0.5, 0.7],
                is_measure_candidate=True,
            ),
            ColumnProfile(
                name="country",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=2,
                distinct_ratio=0.67,
                sample_values=["Australia", "Japan"],
                is_dimension_candidate=True,
            ),
            ColumnProfile(
                name="order_date",
                inferred_type="datetime",
                nullable=False,
                null_ratio=0.0,
                unique_count=3,
                distinct_ratio=1.0,
                sample_values=["2026-01-01"],
                is_time_candidate=True,
            ),
        ],
        measure_columns=["total_sales", "average_order_value", "mean_score", "measure_score"],
        dimension_columns=["count_flag", "country"],
        time_columns=["order_date"],
        identifier_columns=[],
    )


def build_collision_dataset() -> Dataset:
    return Dataset(
        name="sales_collision",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "total_sales": [100.0, 80.0, 60.0],
                "average_order_value": [50.0, 40.0, 30.0],
                "mean_score": [0.8, 0.7, 0.6],
                "count_flag": ["yes", "no", "yes"],
                "measure_score": [0.1, 0.2, 0.3],
                "country": ["Australia", "Japan", "Australia"],
                "order_date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            }
        ),
    )


def test_prompt_entity_extractor_masks_field_name_before_intent_detection() -> None:
    extractor = PromptEntityExtractor()

    extracted = extractor.extract("Does the dataset contain a total_sales column?", build_collision_profile())

    assert extracted.ordered_columns == ["total_sales"]
    assert extracted.masked_question == "Does the dataset contain a [ENTITY] column?"


def test_prompt_entity_extractor_resolves_spaced_alias_for_snake_case_field() -> None:
    extractor = PromptEntityExtractor()

    extracted = extractor.extract("Show average order value by country.", build_collision_profile())

    assert extracted.ordered_columns == ["average_order_value", "country"]
    assert extracted.masked_question == "Show [ENTITY] by [ENTITY]."


def test_intent_resolver_does_not_treat_total_sales_as_count_language() -> None:
    normalizer = RequestNormalizer()
    profile = build_collision_profile()
    surface = normalizer.extract_prompt_entities("Does the dataset contain a total_sales column?", profile)

    assert normalizer.intent_resolver.extract_aggregation(surface) is None
    assert normalizer.intent_resolver.contains_unsafe_count_language(surface) is False


def test_intent_resolver_keeps_real_aggregation_when_requested_outside_field_name() -> None:
    normalizer = RequestNormalizer()
    profile = build_collision_profile()
    surface = normalizer.extract_prompt_entities("What is the average average_order_value?", profile)

    assert normalizer.intent_resolver.extract_aggregation(surface) == "mean"


def test_normalizer_prefers_column_presence_check_for_total_sales_field_name() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "Does the dataset contain a total_sales column?",
        build_collision_dataset(),
        build_collision_profile(),
        None,
    )

    assert warnings == []
    assert request.intent_name == "existence_check"
    assert request.options["existence_mode"] == "column_presence_check"
    assert request.options["requested_column"] == "total_sales"


def test_normalizer_keeps_property_keywords_inside_field_names_from_becoming_property_checks() -> None:
    normalizer = RequestNormalizer()

    request, _ = normalizer.normalize(
        "Does the dataset contain a measure_score column?",
        build_collision_dataset(),
        build_collision_profile(),
        None,
    )

    assert request.intent_name == "existence_check"
    assert request.options["existence_mode"] == "column_presence_check"
    assert request.options["requested_column"] == "measure_score"


def test_normalizer_routes_grouped_metric_prompt_to_grouped_tabular_query() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "Show total total_sales by country as table.",
        build_collision_dataset(),
        build_collision_profile(),
        None,
    )

    assert warnings == []
    assert request.intent_name == "grouped_tabular_query"
    assert request.prompt_family == "grouped_metric_table"
    assert request.target == "total_sales"
    assert request.aggregation == "sum"
    assert request.group_by == ["country"]


def test_normalizer_routes_grouped_row_count_prompt_to_grouped_entity_count() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "Count rows by country.",
        build_collision_dataset(),
        build_collision_profile(),
        None,
    )

    assert warnings == []
    assert request.intent_name == "grouped_tabular_query"
    assert request.prompt_family == "grouped_entity_count"
    assert request.target is None
    assert request.aggregation == "count"
    assert request.group_by == ["country"]


def test_normalizer_routes_time_bucket_row_count_prompt_to_time_bucket_counts() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "Count rows by month.",
        build_collision_dataset(),
        build_collision_profile(),
        None,
    )

    assert warnings == []
    assert request.intent_name == "time_bucket_counts"
    assert request.prompt_family == "time_bucket_counts"
    assert request.target is None
    assert request.aggregation is None
    assert request.options["time_bucket"] == "month"


def test_normalizer_routes_plural_dimension_group_ranking_prompt() -> None:
    normalizer = RequestNormalizer()

    request, warnings = normalizer.normalize(
        "Show the top 3 countries by total total_sales.",
        build_collision_dataset(),
        build_collision_profile(),
        None,
    )

    assert warnings == []
    assert request.intent_name == "group_ranking"
    assert request.target == "total_sales"
    assert request.group_by == ["country"]
    assert request.options["ranking_direction"] == "desc"
    assert request.options["ranking_limit"] == 3


def test_normalizer_with_llm_rewrite_preserves_time_bucket_breakdown() -> None:
    normalizer = RequestNormalizer()
    proposal = IntentProposal(
        status="ready",
        canonical_question="Show total total_sales grouped by month from order_date.",
        confidence=1.0,
        target="total_sales",
        aggregation="sum",
        operation="sum",
        object_kind="measure",
        object_ref="total_sales",
        expected_result_shape="table",
        candidate_capabilities=["aggregation", "time_buckets", "trend", "tabular"],
    )

    request, warnings = normalizer.normalize_with_proposal(
        "Show total total_sales by month.",
        build_collision_dataset(),
        build_collision_profile(),
        proposal,
        None,
    )

    assert warnings == []
    assert request.intent_name == "time_bucket_breakdown"
    assert request.prompt_family == "time_bucket_breakdown"
    assert request.target == "total_sales"
    assert request.aggregation is None
    assert request.options["time_bucket"] == "month"


def test_normalizer_with_llm_rewrite_preserves_grouped_metric_intent() -> None:
    normalizer = RequestNormalizer()
    proposal = IntentProposal(
        status="ready",
        canonical_question="Show total total_sales grouped by country in a table.",
        confidence=1.0,
        target="total_sales",
        aggregation="sum",
        operation="sum",
        object_kind="measure",
        object_ref="total_sales",
        expected_result_shape="table",
        candidate_capabilities=["aggregation", "segmentation", "tabular"],
    )

    request, warnings = normalizer.normalize_with_proposal(
        "Show total total_sales by country as table.",
        build_collision_dataset(),
        build_collision_profile(),
        proposal,
        None,
    )

    assert warnings == []
    assert request.intent_name == "grouped_tabular_query"
    assert request.prompt_family == "grouped_metric_table"
    assert request.target == "total_sales"
    assert request.aggregation == "sum"
    assert request.group_by == ["country"]

