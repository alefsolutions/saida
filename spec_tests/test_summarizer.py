from __future__ import annotations

import pandas as pd

from saida.core.contracts import (
    AnalysisPlan,
    AnalysisRequest,
    ColumnProfile,
    DatasetProfile,
    Metric,
    SourceContext,
    TableArtifact,
)
from saida.outputs import ResultSummarizer


def build_profile() -> DatasetProfile:
    return DatasetProfile(
        dataset_name="sales",
        row_count=4,
        column_count=3,
        columns=[
            ColumnProfile(
                name="revenue",
                inferred_type="float",
                nullable=False,
                null_ratio=0.0,
                unique_count=4,
                distinct_ratio=1.0,
                sample_values=[100.0],
                is_measure_candidate=True,
            )
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


def test_summarizer_describes_share_of_total_and_freshness_note() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(question="Show revenue by region", task_type_hint="descriptive", target="revenue")
    metrics = [Metric(name="row_count", value=4), Metric(name="revenue_sum", value=400.0)]
    tables = [
        TableArtifact(
            name="time_trend",
            description="Trend.",
            dataframe=pd.DataFrame(
                {
                    "period_month": ["2026-02", "2026-03"],
                    "target_total": [180.0, 220.0],
                    "period_delta": [None, 40.0],
                }
            ),
        ),
        TableArtifact(
            name="ranked_breakdown",
            description="Ranking.",
            dataframe=pd.DataFrame({"rank": [1], "region": ["West"], "target_total": [250.0]}),
        ),
        TableArtifact(
            name="contribution_breakdown",
            description="Contribution.",
            dataframe=pd.DataFrame(
                {"region": ["West", "East"], "target_total": [250.0, 150.0], "share_of_total": [0.625, 0.375]}
            ),
        ),
        TableArtifact(
            name="anomaly_summary",
            description="Anomalies.",
            dataframe=pd.DataFrame(columns=["observation", "target_value", "z_score"]),
        ),
    ]
    context = SourceContext(raw_markdown="", freshness_notes=["source refreshes daily"])

    summary = summarizer.summarize(plan, metrics, tables, [], request, build_profile(), context)

    assert "Completed a descriptive analysis for revenue on sales." in summary
    assert "The latest period is 2026-03 with revenue at 220.00 and a period change of +40.00." in summary
    assert "Top contributor was region=West with revenue total of 250.00." in summary
    assert "Largest share of total revenue came from region=West at 62.5%." in summary
    assert "Detected 0 anomaly candidates." in summary
    assert "Context freshness note: source refreshes daily." in summary


def test_summarizer_includes_warning_text() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="diagnostic", rationale="Test.")
    request = AnalysisRequest(question="Why?", task_type_hint="diagnostic", target="revenue")

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[],
        warnings=["filter was narrow"],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "Warnings: filter was narrow." in summary


def test_summarizer_describes_period_comparison_and_top_mover() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="diagnostic", rationale="Test.")
    request = AnalysisRequest(question="Why did revenue drop?", task_type_hint="diagnostic", target="revenue")
    tables = [
        TableArtifact(
            name="period_comparison",
            description="Period comparison.",
            dataframe=pd.DataFrame(
                {
                    "period": ["2026-02", "2026-03"],
                    "target_total": [200.0, 150.0],
                    "delta": [None, -50.0],
                }
            ),
        ),
        TableArtifact(
            name="top_movers",
            description="Movers.",
            dataframe=pd.DataFrame(
                {
                    "rank": [1],
                    "region": ["West"],
                    "previous_total": [120.0],
                    "current_total": [70.0],
                    "delta": [-50.0],
                    "pct_change": [-0.4166666667],
                    "abs_delta": [50.0],
                }
            ),
        ),
    ]

    summary = summarizer.summarize(plan, [], tables, [], request, build_profile(), None)

    assert "Revenue moved from 200.00 in 2026-02 to 150.00 in 2026-03 (-25.0%)." in summary
    assert "Top mover was region=West with a -50.00 change in revenue (-41.7%)." in summary


def test_summarizer_describes_contribution_delta_branch() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="diagnostic", rationale="Test.")
    request = AnalysisRequest(question="Why did revenue drop?", task_type_hint="diagnostic", target="revenue")
    tables = [
        TableArtifact(
            name="contribution_breakdown",
            description="Contribution.",
            dataframe=pd.DataFrame(
                {
                    "region": ["East", "West"],
                    "previous_total": [100.0, 120.0],
                    "current_total": [60.0, 100.0],
                    "delta": [-40.0, -20.0],
                }
            ),
        )
    ]

    summary = summarizer.summarize(plan, [], tables, [], request, build_profile(), None)

    assert "Largest contribution change came from region=East at -40.00 revenue." in summary


def test_summarizer_describes_time_series_diagnostics() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(question="Show revenue trend", task_type_hint="descriptive", target="revenue")
    tables = [
        TableArtifact(
            name="time_series_diagnostics",
            description="Diagnostics.",
            dataframe=pd.DataFrame(
                {
                    "first_period": ["2026-01"],
                    "last_period": ["2026-03"],
                    "net_change": [30.0],
                    "change_volatility": [12.5],
                }
            ),
        )
    ]

    summary = summarizer.summarize(plan, [], tables, [], request, build_profile(), None)

    assert "Across 2026-01 to 2026-03, revenue changed by +30.00 with period-to-period volatility of 12.50." in summary


def test_summarizer_describes_time_bucket_breakdown() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Show revenue by quarter",
        intent_name="time_bucket_breakdown",
        task_type_hint="descriptive",
        target="revenue",
        options={"time_bucket": "quarter"},
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(
                name="time_bucket_breakdown",
                description="Quarter totals.",
                dataframe=pd.DataFrame({"quarter": ["2026-Q1", "2026-Q2"], "target_total": [180.0, 200.0]}),
            )
        ],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "Revenue by quarter: quarter=2026-Q1 = 180.00; quarter=2026-Q2 = 200.00." in summary


def test_summarizer_describes_time_bucket_counts_by_quarter() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="How many tickets were created by quarter?",
        intent_name="time_bucket_counts",
        task_type_hint="descriptive",
        options={"time_bucket": "quarter"},
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(
                name="time_bucket_counts",
                description="Quarter counts.",
                dataframe=pd.DataFrame({"quarter": ["2026-Q1", "2026-Q2"], "row_count": [3, 5]}),
            )
        ],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "Ticket counts by quarter: 2026-Q1 = 3; 2026-Q2 = 5." in summary


def test_summarizer_uses_dataset_label_when_target_missing() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(question="Show dataset", task_type_hint="descriptive", target=None)

    summary = summarizer.summarize(plan, [], [], [], request, build_profile(), None)

    assert "Completed a descriptive analysis for the dataset on sales." in summary


def test_summarizer_leads_with_average_aggregation() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(question="What is the average revenue?", task_type_hint="descriptive", target="revenue", aggregation="mean")

    summary = summarizer.summarize(
        plan,
        metrics=[Metric(name="revenue_mean", value=93.375)],
        tables=[],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "Average revenue is 93.38." in summary


def test_summarizer_prioritizes_grouped_sum_aggregation_answer() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Give me the total revenue by region",
        task_type_hint="descriptive",
        target="revenue",
        aggregation="sum",
        group_by=["region"],
    )

    summary = summarizer.summarize(
        plan,
        metrics=[Metric(name="row_count", value=8), Metric(name="revenue_sum", value=747.0)],
        tables=[
            TableArtifact(
                name="group_breakdown",
                description="Grouped totals.",
                dataframe=pd.DataFrame({"region": ["West", "East"], "target_total": [397.0, 350.0]}),
            ),
            TableArtifact(
                name="time_trend",
                description="Trend.",
                dataframe=pd.DataFrame(
                    {
                        "period_month": ["2026-03", "2026-04"],
                        "target_total": [150.0, 157.0],
                        "period_delta": [None, 7.0],
                    }
                ),
            ),
        ],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "Total revenue by region: region=West = 397.00; region=East = 350.00." in summary
    assert "The latest period is 2026-04" not in summary
    assert "Top contributor was" not in summary


def test_summarizer_prioritizes_grouped_average_aggregation_answer() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Give me the average revenue by region",
        task_type_hint="descriptive",
        target="revenue",
        aggregation="mean",
        group_by=["region"],
    )

    summary = summarizer.summarize(
        plan,
        metrics=[Metric(name="row_count", value=8), Metric(name="revenue_mean", value=93.375)],
        tables=[
            TableArtifact(
                name="group_breakdown",
                description="Grouped means.",
                dataframe=pd.DataFrame({"region": ["West", "East"], "target_total": [99.25, 87.50]}),
            )
        ],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "Average revenue by region: region=West = 99.25; region=East = 87.50." in summary
    assert "Average revenue is 93.38." not in summary


def test_summarizer_leads_with_highest_aggregation() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(question="What is the highest revenue?", task_type_hint="descriptive", target="revenue", aggregation="max")

    summary = summarizer.summarize(
        plan,
        metrics=[Metric(name="revenue_max", value=120.0)],
        tables=[],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "Highest revenue is 120.00." in summary


def test_summarizer_keeps_scalar_aggregation_summary_concise() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(question="What is the average revenue?", task_type_hint="descriptive", target="revenue", aggregation="mean")

    summary = summarizer.summarize(
        plan,
        metrics=[Metric(name="row_count", value=8), Metric(name="revenue_mean", value=93.375)],
        tables=[
            TableArtifact(
                name="time_trend",
                description="Trend.",
                dataframe=pd.DataFrame(
                    {
                        "period_month": ["2026-03", "2026-04"],
                        "target_total": [150.0, 157.0],
                        "period_delta": [None, 7.0],
                    }
                ),
            )
        ],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "Average revenue is 93.38." in summary
    assert "The latest period is 2026-04" not in summary


def test_summarizer_describes_distinct_value_listing() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Give me a list of all segments",
        task_type_hint="descriptive",
        target="segment",
        options={"distinct_values": True},
    )

    summary = summarizer.summarize(
        plan,
        metrics=[Metric(name="row_count", value=8)],
        tables=[
            TableArtifact(
                name="distinct_values",
                description="Distinct values.",
                dataframe=pd.DataFrame({"segment": ["Enterprise", "SMB"], "row_count": [4, 4]}),
            )
        ],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "Available segment values: Enterprise, SMB." in summary


def test_summarizer_describes_row_count_intent() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(question="How many rows?", intent_name="row_count", task_type_hint="descriptive")

    summary = summarizer.summarize(
        plan,
        metrics=[Metric(name="row_count", value=8)],
        tables=[],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert summary == "Completed a descriptive analysis for the dataset on sales. The dataset contains 8 rows."


def test_summarizer_describes_representation_ranking() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Which segment is least represented?",
        intent_name="representation_ranking",
        task_type_hint="descriptive",
        target="segment",
        options={"ranking_direction": "asc"},
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(
                name="group_row_counts",
                description="Counts.",
                dataframe=pd.DataFrame({"segment": ["Online", "Wholesale"], "row_count": [1, 2]}),
            )
        ],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "The least represented segment is segment=Online with 1 rows." in summary


def test_summarizer_describes_column_inventory() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(question="What are the columns?", intent_name="column_inventory", task_type_hint="descriptive")

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(
                name="column_inventory",
                description="Columns.",
                dataframe=pd.DataFrame({"column_name": ["revenue", "region", "posted_at"]}),
            )
        ],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "Available columns: revenue, region, posted_at." in summary


def test_summarizer_describes_column_type_inventory() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="What are the data types of each field?",
        intent_name="column_type_inventory",
        task_type_hint="descriptive",
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(
                name="column_type_inventory",
                description="Column types.",
                dataframe=pd.DataFrame(
                    {
                        "column_name": ["ticket_id", "created_at", "csat_score"],
                        "dtype": ["string", "datetime", "float"],
                        "nullable": [False, False, True],
                    }
                ),
            )
        ],
        warnings=[],
        request=request,
        profile=build_schema_profile(),
        context=None,
    )

    assert "Column types: ticket_id (string, non-null); created_at (datetime, non-null); csat_score (float, nullable)." in summary


def test_summarizer_describes_single_column_type_lookup() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="What is the data type of created_at?",
        intent_name="column_type_inventory",
        task_type_hint="descriptive",
        target="created_at",
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(
                name="column_type_inventory",
                description="Created_at type.",
                dataframe=pd.DataFrame(
                    {
                        "column_name": ["created_at"],
                        "dtype": ["datetime"],
                        "nullable": [False],
                    }
                ),
            )
        ],
        warnings=[],
        request=request,
        profile=build_schema_profile(),
        context=None,
    )

    assert "Data type for created_at is datetime (non-null)." in summary


def test_summarizer_describes_missing_value_inventory() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Which columns have missing values?",
        intent_name="missing_value_inventory",
        task_type_hint="descriptive",
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(
                name="missing_value_inventory",
                description="Missing values.",
                dataframe=pd.DataFrame({"column_name": ["csat_score"], "null_count": [1], "null_ratio": [0.25]}),
            )
        ],
        warnings=[],
        request=request,
        profile=build_schema_profile(),
        context=None,
    )

    assert "Columns with missing values: csat_score (1 nulls, 25.0%)." in summary


def test_summarizer_describes_no_missing_value_inventory() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Which columns have missing values?",
        intent_name="missing_value_inventory",
        task_type_hint="descriptive",
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[TableArtifact(name="missing_value_inventory", description="Missing values.", dataframe=pd.DataFrame())],
        warnings=[],
        request=request,
        profile=build_schema_profile(),
        context=None,
    )

    assert "No columns with missing values were detected." in summary


def test_summarizer_describes_no_identifier_inventory() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Which columns are likely identifiers?",
        intent_name="identifier_inventory",
        task_type_hint="descriptive",
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[TableArtifact(name="identifier_inventory", description="Identifiers.", dataframe=pd.DataFrame())],
        warnings=[],
        request=request,
        profile=build_schema_profile(),
        context=None,
    )

    assert "No likely identifier columns were detected." in summary


def test_summarizer_describes_high_cardinality_inventory() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Which columns have many unique values?",
        intent_name="high_cardinality_inventory",
        task_type_hint="descriptive",
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(
                name="high_cardinality_inventory",
                description="High-cardinality columns.",
                dataframe=pd.DataFrame(
                    {
                        "column_name": ["ticket_id", "created_at"],
                        "unique_count": [4, 4],
                        "distinct_ratio": [1.0, 1.0],
                    }
                ),
            )
        ],
        warnings=[],
        request=request,
        profile=build_schema_profile(),
        context=None,
    )

    assert "High-cardinality columns: ticket_id (4 unique, 100.0% distinct); created_at (4 unique, 100.0% distinct)." in summary


def test_summarizer_describes_null_check() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Does csat_score have missing values?",
        intent_name="existence_check",
        task_type_hint="descriptive",
        target="csat_score",
        options={"existence_mode": "null_check", "null_expectation": "has_nulls"},
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(
                name="null_check",
                description="Null verification.",
                dataframe=pd.DataFrame(
                    {
                        "column_name": ["csat_score"],
                        "null_expectation": ["has_nulls"],
                        "matches": [True],
                        "null_row_count": [1],
                        "non_null_row_count": [3],
                        "total_row_count": [4],
                    }
                ),
            )
        ],
        warnings=[],
        request=request,
        profile=build_schema_profile(),
        context=None,
    )

    assert "Yes, csat_score has missing values (1 null rows out of 4)." in summary


def test_summarizer_describes_threshold_check() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Are any resolution_hours above 20?",
        intent_name="existence_check",
        task_type_hint="descriptive",
        target="resolution_hours",
        options={"existence_mode": "threshold_check", "threshold_operator": "gt", "threshold_value": 20.0},
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(
                name="threshold_check",
                description="Threshold verification.",
                dataframe=pd.DataFrame(
                    {
                        "column_name": ["resolution_hours"],
                        "threshold_operator": ["gt"],
                        "threshold_value": [20.0],
                        "lower_bound": [None],
                        "upper_bound": [None],
                        "matches": [True],
                        "matching_row_count": [2],
                        "total_numeric_row_count": [6],
                    }
                ),
            )
        ],
        warnings=[],
        request=request,
        profile=build_schema_profile(),
        context=None,
    )

    assert "Yes, resolution_hours contains values above 20.00 (2 matching rows out of 6)." in summary


def test_summarizer_describes_column_property_check() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Is ticket_id likely an identifier?",
        intent_name="existence_check",
        task_type_hint="descriptive",
        target="ticket_id",
        options={"existence_mode": "column_property_check", "expected_property": "identifier"},
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(
                name="column_property_check",
                description="Property verification.",
                dataframe=pd.DataFrame(
                    {
                        "column_name": ["ticket_id"],
                        "expected_property": ["identifier"],
                        "matches": [True],
                        "dtype": ["string"],
                    }
                ),
            )
        ],
        warnings=[],
        request=request,
        profile=build_schema_profile(),
        context=None,
    )

    assert "Yes, ticket_id is likely an identifier." in summary


def test_summarizer_describes_negative_complete_check() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Is csat_score complete?",
        intent_name="existence_check",
        task_type_hint="descriptive",
        target="csat_score",
        options={"existence_mode": "null_check", "null_expectation": "no_nulls"},
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(
                name="null_check",
                description="Null verification.",
                dataframe=pd.DataFrame(
                    {
                        "column_name": ["csat_score"],
                        "null_expectation": ["no_nulls"],
                        "matches": [False],
                        "null_row_count": [1],
                        "non_null_row_count": [3],
                        "total_row_count": [4],
                    }
                ),
            )
        ],
        warnings=[],
        request=request,
        profile=build_schema_profile(),
        context=None,
    )

    assert "No, csat_score is not complete (1 null rows out of 4)." in summary


def test_summarizer_lists_top_ranked_row_values() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Show top 3 revenue values",
        intent_name="row_ranking",
        task_type_hint="descriptive",
        target="revenue",
        options={"ranking_limit": 3, "ranking_direction": "desc"},
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(
                name="ranked_rows",
                description="Top rows.",
                dataframe=pd.DataFrame(
                    {
                        "rank": [1, 2, 3],
                        "revenue": [300.0, 120.0, 80.0],
                        "region": ["West", "East", "North"],
                    }
                ),
            )
        ],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "Top 3 revenue values: #1 300.00 (region=West); #2 120.00 (region=East); #3 80.00 (region=North)." in summary


def test_summarizer_lists_bottom_ranked_row_values() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Show bottom 2 revenue values",
        intent_name="row_ranking",
        task_type_hint="descriptive",
        target="revenue",
        options={"ranking_limit": 2, "ranking_direction": "asc"},
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(
                name="ranked_rows",
                description="Bottom rows.",
                dataframe=pd.DataFrame({"rank": [1, 2], "revenue": [40.0, 60.0], "region": ["East", "West"]}),
            )
        ],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "Bottom 2 revenue values: #1 40.00 (region=East); #2 60.00 (region=West)." in summary


def test_summarizer_lists_top_ranked_groups() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Show top 2 revenue by region",
        intent_name="group_ranking",
        task_type_hint="descriptive",
        target="revenue",
        group_by=["region"],
        options={"ranking_limit": 2, "ranking_direction": "desc"},
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(
                name="ranked_breakdown",
                description="Top groups.",
                dataframe=pd.DataFrame({"rank": [1, 2], "region": ["West", "East"], "target_total": [397.0, 350.0]}),
            )
        ],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "Top 2 revenue groups: #1 region=West = 397.00; #2 region=East = 350.00." in summary


def test_summarizer_lists_bottom_ranked_groups() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Show bottom 1 revenue by region",
        intent_name="group_ranking",
        task_type_hint="descriptive",
        target="revenue",
        group_by=["region"],
        options={"ranking_limit": 1, "ranking_direction": "asc"},
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(
                name="ranked_breakdown",
                description="Bottom groups.",
                dataframe=pd.DataFrame({"rank": [1], "region": ["East"], "target_total": [350.0]}),
            )
        ],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "Bottom 1 revenue groups: #1 region=East = 350.00." in summary


def test_summarizer_uses_available_row_count_when_ranking_limit_exceeds_results() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Show top 5 revenue values",
        intent_name="row_ranking",
        task_type_hint="descriptive",
        target="revenue",
        options={"ranking_limit": 5, "ranking_direction": "desc"},
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[TableArtifact(name="ranked_rows", description="Top rows.", dataframe=pd.DataFrame({"rank": [1], "revenue": [300.0]}))],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "Top 1 revenue values: #1 300.00." in summary


def test_summarizer_row_ranking_skips_generic_trend_summary() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Show top 3 revenue values",
        intent_name="row_ranking",
        task_type_hint="descriptive",
        target="revenue",
        options={"ranking_limit": 3, "ranking_direction": "desc"},
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(name="ranked_rows", description="Top rows.", dataframe=pd.DataFrame({"rank": [1], "revenue": [300.0]})),
            TableArtifact(
                name="time_trend",
                description="Trend.",
                dataframe=pd.DataFrame({"period_month": ["2026-04"], "target_total": [300.0], "period_delta": [None]}),
            ),
        ],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "The latest period is" not in summary


def test_summarizer_group_ranking_skips_generic_top_contributor_summary() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Show top 2 revenue by region",
        intent_name="group_ranking",
        task_type_hint="descriptive",
        target="revenue",
        group_by=["region"],
        options={"ranking_limit": 2, "ranking_direction": "desc"},
    )

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[
            TableArtifact(
                name="ranked_breakdown",
                description="Top groups.",
                dataframe=pd.DataFrame({"rank": [1, 2], "region": ["West", "East"], "target_total": [397.0, 350.0]}),
            ),
            TableArtifact(
                name="group_breakdown",
                description="Groups.",
                dataframe=pd.DataFrame({"region": ["West", "East"], "target_total": [397.0, 350.0]}),
            ),
        ],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "Top contributor was" not in summary


def test_summarizer_includes_context_note_with_ranked_rows() -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Test.")
    request = AnalysisRequest(
        question="Show top 1 revenue values",
        intent_name="row_ranking",
        task_type_hint="descriptive",
        target="revenue",
        options={"ranking_limit": 1, "ranking_direction": "desc"},
    )
    context = SourceContext(raw_markdown="", caveats=["values are illustrative only"])

    summary = summarizer.summarize(
        plan,
        metrics=[],
        tables=[TableArtifact(name="ranked_rows", description="Top rows.", dataframe=pd.DataFrame({"rank": [1], "revenue": [300.0]}))],
        warnings=[],
        request=request,
        profile=build_profile(),
        context=context,
    )

    assert "Context caveat: values are illustrative only." in summary


import pytest


_SUMMARIZER_CASES = [
    (
        index,
        [
            TableArtifact(
                name="time_trend",
                description="Trend.",
                dataframe=pd.DataFrame(
                    {
                        "period_month": ["2026-02", "2026-03"],
                        "target_total": [float(index), float(index + 5)],
                        "period_delta": [None, 5.0],
                    }
                ),
            )
        ],
    )
    for index in range(1, 94)
]


@pytest.mark.parametrize(("case_id", "tables"), _SUMMARIZER_CASES)
def test_summarizer_handles_many_trend_only_cases(case_id: int, tables: list[TableArtifact]) -> None:
    summarizer = ResultSummarizer()
    plan = AnalysisPlan(task_type="descriptive", rationale="Synthetic.")
    request = AnalysisRequest(question=f"Show revenue trend {case_id}", task_type_hint="descriptive", target="revenue")

    summary = summarizer.summarize(
        plan,
        metrics=[Metric(name="row_count", value=2), Metric(name="revenue_sum", value=float(case_id + case_id + 5))],
        tables=tables,
        warnings=[],
        request=request,
        profile=build_profile(),
        context=None,
    )

    assert "Completed a descriptive analysis for revenue on sales." in summary
    assert "The latest period is 2026-03 with revenue at" in summary
