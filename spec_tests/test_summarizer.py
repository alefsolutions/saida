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
