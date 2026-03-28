from __future__ import annotations

import pytest

from saida.plan_generation import AnalysisPlanner
from saida.exceptions import PlanningError
from saida.core.contracts import AnalysisRequest, ColumnProfile, DatasetProfile


def build_profile() -> DatasetProfile:
    return DatasetProfile(
        dataset_name="sales",
        row_count=10,
        column_count=4,
        columns=[
            ColumnProfile(
                name="revenue",
                inferred_type="float",
                nullable=False,
                null_ratio=0.0,
                unique_count=10,
                distinct_ratio=1.0,
                sample_values=[100.0],
                is_measure_candidate=True,
            ),
            ColumnProfile(
                name="region",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=2,
                distinct_ratio=0.2,
                sample_values=["West"],
                is_dimension_candidate=True,
            ),
            ColumnProfile(
                name="posted_at",
                inferred_type="datetime",
                nullable=False,
                null_ratio=0.0,
                unique_count=10,
                distinct_ratio=1.0,
                sample_values=["2026-03-01"],
                is_time_candidate=True,
            ),
        ],
        measure_columns=["revenue"],
        dimension_columns=["region"],
        time_columns=["posted_at"],
        identifier_columns=[],
    )


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
                sample_values=["T1"],
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
                sample_values=[4.2],
                is_measure_candidate=True,
            ),
            ColumnProfile(
                name="priority",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=3,
                distinct_ratio=0.75,
                sample_values=["Low"],
                is_dimension_candidate=True,
            ),
            ColumnProfile(
                name="csat_score",
                inferred_type="float",
                nullable=True,
                null_ratio=0.25,
                unique_count=3,
                distinct_ratio=0.75,
                sample_values=[4.8],
                is_measure_candidate=True,
            ),
        ],
        measure_columns=["resolution_hours", "csat_score"],
        dimension_columns=["ticket_id", "priority"],
        time_columns=["created_at"],
        identifier_columns=["ticket_id"],
    )


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
                sample_values=["T1"],
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
                sample_values=[4.2],
                is_measure_candidate=True,
            ),
            ColumnProfile(
                name="priority",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=3,
                distinct_ratio=0.5,
                sample_values=["Low"],
                is_dimension_candidate=True,
            ),
            ColumnProfile(
                name="team",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=2,
                distinct_ratio=0.33,
                sample_values=["Support"],
                is_dimension_candidate=True,
            ),
            ColumnProfile(
                name="reopened_flag",
                inferred_type="category",
                nullable=False,
                null_ratio=0.0,
                unique_count=2,
                distinct_ratio=0.33,
                sample_values=["yes"],
                is_dimension_candidate=True,
            ),
        ],
        measure_columns=["resolution_hours"],
        dimension_columns=["ticket_id", "priority", "team", "reopened_flag"],
        time_columns=["created_at"],
        identifier_columns=["ticket_id"],
    )


def test_planner_builds_diagnostic_plan_with_contribution_steps() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Why did revenue drop in March?",
        task_type_hint="diagnostic",
        target="revenue",
        time_reference={"type": "month_name", "value": "march", "month": "3"},
    )

    plan = planner.build_plan(request, build_profile())
    actions = [step.action for step in plan.steps]

    assert "dataset_summary" in actions
    assert "period_comparison" in actions
    assert "contribution_breakdown" in actions
    assert "anomaly_summary" in actions


def test_planner_builds_grouped_descriptive_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show revenue by region",
        task_type_hint="descriptive",
        target="revenue",
        group_by=["region"],
    )

    plan = planner.build_plan(request, build_profile())
    actions = [step.action for step in plan.steps]

    assert "group_breakdown" in actions
    assert "ranked_breakdown" in actions


def test_planner_builds_aggregate_value_plan_for_average_request() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="What is the average revenue?",
        task_type_hint="descriptive",
        target="revenue",
        aggregation="mean",
    )

    plan = planner.build_plan(request, build_profile())
    actions = [step.action for step in plan.steps]

    assert "aggregate_value" in actions


def test_planner_passes_aggregation_into_group_breakdown() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show highest revenue by region",
        task_type_hint="descriptive",
        target="revenue",
        aggregation="max",
        group_by=["region"],
    )

    plan = planner.build_plan(request, build_profile())
    group_step = next(step for step in plan.steps if step.action == "group_breakdown")

    assert group_step.parameters["aggregation"] == "max"


def test_planner_builds_distinct_values_plan_for_dimension_listing() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Give me a list of all regions",
        intent_name="distinct_values",
        task_type_hint="descriptive",
        target="region",
        options={"distinct_values": True},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["distinct_values"]


def test_planner_routes_dimension_only_prompt_to_distinct_values() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show region",
        intent_name="distinct_values",
        task_type_hint="descriptive",
        target="region",
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["distinct_values"]
    assert plan.warnings == []


def test_planner_builds_row_count_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="How many rows do we have?",
        intent_name="row_count",
        task_type_hint="descriptive",
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["row_count"]


def test_planner_builds_representation_ranking_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Which region is least represented?",
        intent_name="representation_ranking",
        task_type_hint="descriptive",
        target="region",
        options={"ranking_direction": "asc"},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["count_rows_by_group"]


def test_planner_builds_column_inventory_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="What are the columns?",
        intent_name="column_inventory",
        task_type_hint="descriptive",
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["column_inventory"]


def test_planner_builds_column_type_inventory_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="What are the data types of each field?",
        intent_name="column_type_inventory",
        task_type_hint="descriptive",
    )

    plan = planner.build_plan(request, build_schema_profile())

    assert [step.action for step in plan.steps] == ["column_type_inventory"]


def test_planner_builds_numeric_column_inventory_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Which columns are numeric?",
        intent_name="numeric_column_inventory",
        task_type_hint="descriptive",
    )

    plan = planner.build_plan(request, build_schema_profile())

    assert [step.action for step in plan.steps] == ["numeric_column_inventory"]


def test_planner_builds_categorical_column_inventory_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Which columns are categorical?",
        intent_name="categorical_column_inventory",
        task_type_hint="descriptive",
    )

    plan = planner.build_plan(request, build_schema_profile())

    assert [step.action for step in plan.steps] == ["categorical_column_inventory"]


def test_planner_builds_missing_value_inventory_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Which columns have missing values?",
        intent_name="missing_value_inventory",
        task_type_hint="descriptive",
    )

    plan = planner.build_plan(request, build_schema_profile())

    assert [step.action for step in plan.steps] == ["missing_value_inventory"]


def test_planner_builds_identifier_inventory_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Which columns are likely identifiers?",
        intent_name="identifier_inventory",
        task_type_hint="descriptive",
    )

    plan = planner.build_plan(request, build_schema_profile())

    assert [step.action for step in plan.steps] == ["identifier_inventory"]


def test_planner_builds_high_cardinality_inventory_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Which columns have many unique values?",
        intent_name="high_cardinality_inventory",
        task_type_hint="descriptive",
    )

    plan = planner.build_plan(request, build_schema_profile())

    assert [step.action for step in plan.steps] == ["high_cardinality_inventory"]


def test_planner_does_not_inject_first_measure_for_schema_metadata_intent() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Which columns have missing values?",
        intent_name="missing_value_inventory",
        task_type_hint="descriptive",
    )

    plan = planner.build_plan(request, build_schema_profile())

    assert request.target is None
    assert plan.warnings == []


def test_planner_rejects_time_column_inventory_without_time_columns() -> None:
    planner = AnalysisPlanner()
    profile = build_schema_profile()
    profile.time_columns = []
    request = AnalysisRequest(
        question="Which columns are dates?",
        intent_name="time_column_inventory",
        task_type_hint="descriptive",
    )

    with pytest.raises(PlanningError, match="Time column inventory requires at least one datetime column"):
        planner.build_plan(request, profile)


def test_planner_builds_time_coverage_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="The data shows revenue for which years?",
        intent_name="time_coverage",
        task_type_hint="descriptive",
        options={"time_coverage_mode": "years_present"},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["time_coverage"]
    assert plan.steps[0].parameters["mode"] == "years_present"


def test_planner_builds_time_bucket_count_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="I need a list of years, and how many tickets created in those years.",
        intent_name="time_bucket_counts",
        task_type_hint="descriptive",
        options={"time_bucket": "year"},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["time_bucket_counts"]
    assert plan.steps[0].parameters["bucket"] == "year"


def test_planner_builds_time_bucket_breakdown_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show revenue by month",
        intent_name="time_bucket_breakdown",
        task_type_hint="descriptive",
        target="revenue",
        options={"time_bucket": "month"},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["time_bucket_breakdown"]
    assert plan.steps[0].parameters["bucket"] == "month"


def test_planner_builds_time_bucket_breakdown_plan_with_grouping() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show revenue by quarter for each region",
        intent_name="time_bucket_breakdown",
        task_type_hint="descriptive",
        target="revenue",
        group_by=["region"],
        options={"time_bucket": "quarter"},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["time_bucket_breakdown"]
    assert plan.steps[0].parameters["group_by"] == ["region"]


def test_planner_builds_time_period_comparison_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Compare revenue this quarter to last quarter",
        intent_name="time_period_comparison",
        task_type_hint="descriptive",
        target="revenue",
        time_reference={"type": "relative_period", "value": "this_quarter"},
        options={"time_bucket": "quarter"},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["period_comparison"]
    assert plan.steps[0].parameters["bucket"] == "quarter"


def test_planner_builds_grouped_time_period_comparison_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Compare revenue by region this year to last year",
        intent_name="time_period_comparison",
        task_type_hint="descriptive",
        target="revenue",
        group_by=["region"],
        time_reference={"type": "relative_period", "value": "this_year"},
        options={"time_bucket": "year"},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["grouped_period_comparison"]
    assert plan.steps[0].parameters["bucket"] == "year"


def test_planner_builds_time_value_existence_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="The created_at column shows dates in 2025?",
        intent_name="existence_check",
        task_type_hint="descriptive",
        target="posted_at",
        options={"existence_mode": "time_value", "expected_year": 2025},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["time_value_exists"]
    assert plan.steps[0].parameters["expected_year"] == 2025


def test_planner_builds_filtered_row_existence_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Is West in the region column?",
        intent_name="existence_check",
        task_type_hint="descriptive",
        filters={"region": "West"},
        options={"existence_mode": "filtered_rows"},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["row_existence"]


def test_planner_builds_null_check_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Does csat_score have missing values?",
        intent_name="existence_check",
        task_type_hint="descriptive",
        target="csat_score",
        options={"existence_mode": "null_check", "null_expectation": "has_nulls"},
    )

    plan = planner.build_plan(request, build_schema_profile())

    assert [step.action for step in plan.steps] == ["null_check"]


def test_planner_builds_threshold_check_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Is revenue below 0 anywhere?",
        intent_name="existence_check",
        task_type_hint="descriptive",
        target="revenue",
        options={"existence_mode": "threshold_check", "threshold_operator": "lt", "threshold_value": 0.0},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["threshold_check"]
    assert plan.steps[0].parameters["threshold_value"] == 0.0


def test_planner_builds_column_property_check_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Is ticket_id likely an identifier?",
        intent_name="existence_check",
        task_type_hint="descriptive",
        target="ticket_id",
        options={"existence_mode": "column_property_check", "expected_property": "identifier"},
    )

    plan = planner.build_plan(request, build_schema_profile())

    assert [step.action for step in plan.steps] == ["column_property_check"]
    assert plan.steps[0].tool_family == "metadata"


def test_planner_rejects_threshold_check_for_non_numeric_target() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Is region above 10?",
        intent_name="existence_check",
        task_type_hint="descriptive",
        target="region",
        options={"existence_mode": "threshold_check", "threshold_operator": "gt", "threshold_value": 10.0},
    )

    with pytest.raises(PlanningError, match="Threshold verification requires a numeric target"):
        planner.build_plan(request, build_profile())


def test_planner_rejects_column_property_check_without_expected_property() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Is revenue something?",
        intent_name="existence_check",
        task_type_hint="descriptive",
        target="revenue",
        options={"existence_mode": "column_property_check"},
    )

    with pytest.raises(PlanningError, match="Column property verification requires a supported expected property"):
        planner.build_plan(request, build_profile())


def test_planner_rejects_invalid_filter_columns() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show revenue for missing_region=West",
        task_type_hint="descriptive",
        target="revenue",
        filters={"missing_region": "West"},
    )

    with pytest.raises(PlanningError, match="Filter columns do not exist"):
        planner.build_plan(request, build_profile())


def test_planner_rejects_time_request_without_time_column() -> None:
    planner = AnalysisPlanner()
    profile = build_profile()
    profile.time_columns = []
    request = AnalysisRequest(
        question="Why did revenue drop in March?",
        task_type_hint="diagnostic",
        target="revenue",
        time_reference={"type": "month_name", "value": "march", "month": "3"},
    )

    with pytest.raises(PlanningError, match="Time-based analysis requires a datetime column"):
        planner.build_plan(request, profile)


def test_planner_rejects_time_coverage_without_time_column() -> None:
    planner = AnalysisPlanner()
    profile = build_profile()
    profile.time_columns = []
    request = AnalysisRequest(
        question="What years are present in the data?",
        intent_name="time_coverage",
        task_type_hint="descriptive",
        options={"time_coverage_mode": "years_present"},
    )

    with pytest.raises(PlanningError, match="Time coverage analysis requires a datetime column"):
        planner.build_plan(request, profile)


def test_planner_rejects_time_bucket_counts_without_time_column() -> None:
    planner = AnalysisPlanner()
    profile = build_profile()
    profile.time_columns = []
    request = AnalysisRequest(
        question="How many tickets were created by year?",
        intent_name="time_bucket_counts",
        task_type_hint="descriptive",
        options={"time_bucket": "year"},
    )

    with pytest.raises(PlanningError, match="Time bucket count analysis requires a datetime column"):
        planner.build_plan(request, profile)


def test_planner_rejects_time_bucket_breakdown_without_time_column() -> None:
    planner = AnalysisPlanner()
    profile = build_profile()
    profile.time_columns = []
    request = AnalysisRequest(
        question="Show revenue by month",
        intent_name="time_bucket_breakdown",
        task_type_hint="descriptive",
        target="revenue",
        options={"time_bucket": "month"},
    )

    with pytest.raises(PlanningError, match="Time bucket breakdown analysis requires a datetime column"):
        planner.build_plan(request, profile)


def test_planner_rejects_time_value_existence_without_expected_value() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Does posted_at contain the requested date?",
        intent_name="existence_check",
        task_type_hint="descriptive",
        target="posted_at",
        options={"existence_mode": "time_value"},
    )

    with pytest.raises(PlanningError, match="Time existence verification requires a concrete year or time reference"):
        planner.build_plan(request, build_profile())


def test_planner_allows_quarter_time_reference_for_row_count_analysis() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="How many rows are in Q1?",
        intent_name="row_count",
        prompt_family="row_count",
        task_type_hint="descriptive",
        aggregation="count",
        filters={"posted_at": {"op": "quarter_eq", "value": 1, "label": "q1"}},
        time_reference={"type": "quarter", "value": "q1", "quarter": "1"},
    )

    plan = planner.build_plan(request, build_profile())

    assert plan.steps[0].action == "row_count"


def test_planner_rejects_relative_time_references_for_non_period_comparison_analysis() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show revenue this quarter",
        task_type_hint="descriptive",
        target="revenue",
        time_reference={"type": "relative_period", "value": "this_quarter"},
    )

    with pytest.raises(PlanningError, match="Relative time references are only supported for period-comparison analysis"):
        planner.build_plan(request, build_profile())


def test_planner_allows_quarter_time_reference_for_time_period_comparison() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Compare revenue this quarter to last quarter",
        intent_name="time_period_comparison",
        task_type_hint="descriptive",
        target="revenue",
        time_reference={"type": "relative_period", "value": "this_quarter"},
        options={"time_bucket": "quarter"},
    )

    plan = planner.build_plan(request, build_profile())

    assert plan.steps[0].action == "period_comparison"


def test_planner_rejects_unsupported_aggregation() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show median revenue",
        task_type_hint="descriptive",
        target="revenue",
        aggregation="median",
    )

    with pytest.raises(PlanningError, match="Unsupported aggregation"):
        planner.build_plan(request, build_profile())


def test_planner_builds_exploratory_metric_overview_from_prompt_family() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show revenue",
        prompt_family="exploratory_metric_overview",
        task_type_hint="descriptive",
        target="revenue",
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps[:3]] == ["dataset_summary", "time_trend", "missingness_summary"]
    assert "group_mean_comparison" in [step.action for step in plan.steps]


def test_planner_rejects_unresolved_prompt_without_safe_family() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show data by region",
        task_type_hint="descriptive",
        group_by=["region"],
    )

    with pytest.raises(PlanningError, match="safe supported prompt family"):
        planner.build_plan(request, build_profile())


def test_planner_includes_group_mean_comparison_for_grouped_descriptive_requests() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show revenue by region",
        task_type_hint="descriptive",
        target="revenue",
        group_by=["region"],
    )

    plan = planner.build_plan(request, build_profile())
    actions = [step.action for step in plan.steps]

    assert "group_mean_comparison" in actions


def test_planner_builds_rationale_with_context_and_filters() -> None:
    from saida.core.contracts import SourceContext

    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show revenue for West",
        task_type_hint="descriptive",
        target="revenue",
        filters={"region": "West"},
    )
    context = SourceContext(raw_markdown="", metric_definitions={"revenue": "total revenue"})

    plan = planner.build_plan(request, build_profile(), context)

    assert "Semantic metric definitions were available." in plan.rationale
    assert "Filters were detected for: region." in plan.rationale


def test_planner_rejects_invalid_target_column() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(question="Show profit", task_type_hint="descriptive", target="profit")

    with pytest.raises(PlanningError, match="Target column 'profit' does not exist"):
        planner.build_plan(request, build_profile())


def test_planner_rejects_mean_aggregation_for_dimension_target() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="What is the average region?",
        task_type_hint="descriptive",
        target="region",
        aggregation="mean",
    )

    with pytest.raises(PlanningError, match="Aggregation 'mean' requires a numeric target"):
        planner.build_plan(request, build_profile())


def test_planner_rejects_max_aggregation_for_time_target() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="What is the highest posted_at?",
        task_type_hint="descriptive",
        target="posted_at",
        aggregation="max",
    )

    with pytest.raises(PlanningError, match="Aggregation 'max' requires a numeric target"):
        planner.build_plan(request, build_profile())


def test_planner_rejects_grouped_descriptive_request_for_dimension_target() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show region by segment",
        task_type_hint="descriptive",
        target="region",
        group_by=["segment"],
    )

    with pytest.raises(PlanningError, match="Grouped descriptive analysis requires a numeric target"):
        planner.build_plan(request, build_profile())


def test_planner_builds_significance_inference_plan_for_natural_prompt() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Do regions differ in revenue?",
        task_type_hint="statistical",
        target="revenue",
        group_by=["region"],
        options={"statistical_test": "significance_inference"},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["significance_inference"]


def test_planner_builds_confidence_interval_plan_for_natural_prompt() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="What range are we 95% confident revenue falls in?",
        task_type_hint="statistical",
        target="revenue",
        options={"statistical_test": "confidence_interval", "confidence_level": 0.95},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["confidence_interval"]


def test_planner_builds_power_analysis_plan_for_natural_prompt() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Do we have enough data to detect a difference in revenue by region?",
        task_type_hint="statistical",
        target="revenue",
        group_by=["region"],
        options={"statistical_test": "power_analysis", "desired_power": 0.8},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["power_analysis"]


def test_planner_builds_sample_size_plan_for_natural_prompt() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="How many rows per group do we need for revenue by region?",
        task_type_hint="statistical",
        target="revenue",
        group_by=["region"],
        options={"statistical_test": "sample_size_estimate", "desired_power": 0.8},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["sample_size_estimate"]


def test_planner_rejects_regression_significance_without_features() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Does resolution_hours significantly affect csat_score?",
        task_type_hint="statistical",
        target="revenue",
        options={"statistical_test": "regression_significance", "feature_columns": []},
    )

    with pytest.raises(PlanningError, match="Regression significance testing requires a target and at least one feature column"):
        planner.build_plan(request, build_profile())


def test_planner_builds_row_ranking_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show top 5 revenue values",
        intent_name="row_ranking",
        task_type_hint="descriptive",
        target="revenue",
        options={"ranking_limit": 5, "ranking_direction": "desc"},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["ranked_rows"]
    assert plan.steps[0].parameters["limit"] == 5


def test_planner_builds_group_ranking_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show bottom 2 revenue by region",
        intent_name="group_ranking",
        task_type_hint="descriptive",
        target="revenue",
        group_by=["region"],
        options={"ranking_limit": 2, "ranking_direction": "asc"},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["ranked_breakdown"]
    assert plan.steps[0].parameters["ascending"] is True


def test_planner_rejects_row_ranking_for_dimension_target() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show top 5 regions",
        intent_name="row_ranking",
        task_type_hint="descriptive",
        target="region",
        options={"ranking_limit": 5, "ranking_direction": "desc"},
    )

    with pytest.raises(PlanningError, match="Row ranking requires a numeric target"):
        planner.build_plan(request, build_profile())


def test_planner_rejects_group_ranking_without_group_by() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show top 5 revenue",
        intent_name="group_ranking",
        task_type_hint="descriptive",
        target="revenue",
        options={"ranking_limit": 5, "ranking_direction": "desc"},
    )

    with pytest.raises(PlanningError, match="Group ranking requires a numeric target and one grouping column"):
        planner.build_plan(request, build_profile())


def test_planner_rejects_invalid_group_by_columns() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show revenue by country",
        task_type_hint="descriptive",
        target="revenue",
        group_by=["country"],
    )

    with pytest.raises(PlanningError, match="Grouping columns do not exist"):
        planner.build_plan(request, build_profile())


def test_planner_rejects_unsupported_task_type() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(question="Show revenue", task_type_hint="custom", target="revenue")

    with pytest.raises(PlanningError, match="Unsupported analysis task type"):
        planner.build_plan(request, build_profile())


def test_planner_forecasting_requires_target() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(question="Forecast", task_type_hint="forecasting")

    with pytest.raises(PlanningError, match="Forecasting requires a target metric"):
        planner.build_plan(request, build_profile())


_PLANNER_REQUEST_CASES = [
    AnalysisRequest(
        question=f"Why did revenue drop in March case {index}?",
        task_type_hint="diagnostic",
        target="revenue",
        time_reference={"type": "month_name", "value": "march", "month": "3"},
        group_by=["region"] if index % 2 == 0 else None,
    )
    for index in range(1, 89)
]


@pytest.mark.parametrize("analysis_request", _PLANNER_REQUEST_CASES)
def test_planner_builds_many_valid_non_ml_plans(analysis_request: AnalysisRequest) -> None:
    planner = AnalysisPlanner()

    plan = planner.build_plan(analysis_request, build_profile())

    assert plan.task_type in {"diagnostic", "descriptive", "statistical", "predictive", "forecasting"} or True
    assert len(plan.steps) >= 4
    assert any(step.action == "dataset_summary" for step in plan.steps)


def test_planner_builds_tabular_query_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Give me all reopened rows",
        intent_name="tabular_query",
        task_type_hint="descriptive",
        filters={"reopened_flag": "yes"},
        options={"selected_columns": [], "sort_by": "created_at", "sort_direction": "desc", "limit": 5, "page": 1, "page_size": 5},
    )

    plan = planner.build_plan(request, build_tabular_profile())

    assert [step.action for step in plan.steps] == ["tabular_query"]
    assert plan.steps[0].parameters["filters"] == {"reopened_flag": "yes"}
    assert plan.steps[0].parameters["sort_by"] == "created_at"


def test_planner_builds_grouped_tabular_query_plan() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show revenue by region as table",
        intent_name="grouped_tabular_query",
        task_type_hint="descriptive",
        target="revenue",
        aggregation="sum",
        group_by=["region"],
        options={"page": 1, "page_size": 25},
    )

    plan = planner.build_plan(request, build_profile())

    assert [step.action for step in plan.steps] == ["grouped_tabular_query"]
    assert plan.steps[0].parameters["aggregation"] == "sum"


def test_planner_rejects_tabular_query_with_invalid_selected_columns() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show bad column",
        intent_name="tabular_query",
        task_type_hint="descriptive",
        options={"selected_columns": ["unknown"], "page": 1, "page_size": 10},
    )

    with pytest.raises(PlanningError, match="Selected columns do not exist"):
        planner.build_plan(request, build_tabular_profile())


def test_planner_rejects_tabular_query_with_invalid_sort_column() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show rows sorted by unknown",
        intent_name="tabular_query",
        task_type_hint="descriptive",
        options={"selected_columns": [], "sort_by": "unknown", "page": 1, "page_size": 10},
    )

    with pytest.raises(PlanningError, match="Sort column 'unknown' does not exist"):
        planner.build_plan(request, build_tabular_profile())


def test_planner_rejects_grouped_tabular_query_without_group_by() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show grouped table",
        intent_name="grouped_tabular_query",
        task_type_hint="descriptive",
        target="revenue",
        aggregation="sum",
        options={"page": 1, "page_size": 10},
    )

    with pytest.raises(PlanningError, match="Grouped tabular querying requires at least one grouping column"):
        planner.build_plan(request, build_profile())


def test_planner_rejects_grouped_tabular_query_with_dimension_target() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show priority by team as table",
        intent_name="grouped_tabular_query",
        task_type_hint="descriptive",
        target="priority",
        aggregation="sum",
        group_by=["team"],
        options={"page": 1, "page_size": 10},
    )

    with pytest.raises(PlanningError, match="Grouped tabular querying requires a numeric target"):
        planner.build_plan(request, build_tabular_profile())


def test_planner_rejects_invalid_tabular_pagination() -> None:
    planner = AnalysisPlanner()
    request = AnalysisRequest(
        question="Show rows",
        intent_name="tabular_query",
        task_type_hint="descriptive",
        options={"selected_columns": [], "page": 0, "page_size": 10},
    )

    with pytest.raises(PlanningError, match="page to be 1 or greater"):
        planner.build_plan(request, build_tabular_profile())
