from __future__ import annotations

import pandas as pd
import pytest

from saida.adapters import DuckDBComputeEngine, StatsComputeEngine
from saida.exceptions import ComputeError


def build_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "posted_at": ["2026-02-01", "2026-02-01", "2026-03-01", "2026-03-01", "2026-04-01"],
            "revenue": [120.0, 80.0, 60.0, 40.0, 300.0],
            "region": ["West", "East", "West", "East", "West"],
            "cost": [70.0, 50.0, 40.0, 20.0, 100.0],
        }
    )


def build_statistical_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "team": ["Alpha"] * 6 + ["Beta"] * 6 + ["Gamma"] * 6,
            "segment": ["Retail", "Retail", "Wholesale", "Wholesale", "Retail", "Wholesale"] * 3,
            "region": ["North", "North", "South", "South", "North", "South"] * 3,
            "revenue": [100, 104, 98, 102, 101, 99, 135, 138, 132, 140, 136, 134, 160, 158, 162, 159, 161, 157],
            "cost": [70, 72, 69, 71, 70, 68, 88, 90, 87, 91, 89, 88, 95, 94, 96, 95, 97, 93],
            "units": [10, 11, 10, 12, 11, 10, 14, 15, 14, 15, 16, 14, 18, 17, 19, 18, 20, 17],
        }
    )


def test_duckdb_period_and_contribution_breakdown() -> None:
    engine = DuckDBComputeEngine()
    dataframe = build_dataframe()

    trend_table = engine.time_trend(
        dataframe,
        target="revenue",
        time_column="posted_at",
    )
    period_table = engine.period_comparison(
        dataframe,
        target="revenue",
        time_column="posted_at",
        time_reference={"type": "month_name", "value": "march", "month": "3"},
    )
    contribution_table = engine.contribution_breakdown(
        dataframe,
        target="revenue",
        group_by=["region"],
        time_column="posted_at",
        time_reference={"type": "month_name", "value": "march", "month": "3"},
    )

    assert "period_delta" in trend_table.dataframe.columns
    assert list(period_table.dataframe["period"]) == ["2026-02", "2026-03"]
    assert "delta" in contribution_table.dataframe.columns


def test_duckdb_distinct_values_lists_dimension_members() -> None:
    engine = DuckDBComputeEngine()
    dataframe = pd.DataFrame(
        {
            "segment": ["Retail", "Wholesale", "Retail", "Online"],
            "revenue": [100.0, 80.0, 60.0, 40.0],
        }
    )

    distinct_table = engine.distinct_values(dataframe, target="segment")

    assert distinct_table.name == "distinct_values"
    assert list(distinct_table.dataframe["segment"]) == ["Online", "Retail", "Wholesale"]
    assert list(distinct_table.dataframe["row_count"]) == [1, 2, 1]


def test_duckdb_row_count_counts_filtered_rows() -> None:
    engine = DuckDBComputeEngine()
    dataframe = pd.DataFrame({"region": ["West", "East", "West"], "revenue": [1, 2, 3]})

    metrics = engine.row_count(dataframe, filters={"region": "West"})

    assert metrics[0].name == "row_count"
    assert metrics[0].value == 2


def test_duckdb_count_rows_by_group_supports_ranking() -> None:
    engine = DuckDBComputeEngine()
    dataframe = pd.DataFrame({"segment": ["Retail", "Retail", "Wholesale", "Online"], "revenue": [1, 2, 3, 4]})

    table = engine.count_rows_by_group(dataframe, group_by=["segment"], ascending=True, limit=2)

    assert list(table.dataframe["segment"]) == ["Online", "Wholesale"]
    assert list(table.dataframe["row_count"]) == [1, 1]


def test_duckdb_time_coverage_returns_years_present() -> None:
    engine = DuckDBComputeEngine()
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2024-01-01", "2025-03-01", "2025-04-01", "2026-01-15"],
            "revenue": [10.0, 20.0, 30.0, 40.0],
        }
    )

    table = engine.time_coverage(dataframe, time_column="posted_at", mode="years_present")

    assert list(table.dataframe["year"]) == [2024, 2025, 2026]


def test_duckdb_time_coverage_returns_months_present() -> None:
    engine = DuckDBComputeEngine()
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-01-01", "2026-03-01", "2026-03-15", "2026-04-01"],
            "revenue": [10.0, 20.0, 30.0, 40.0],
        }
    )

    table = engine.time_coverage(dataframe, time_column="posted_at", mode="months_present")

    assert list(table.dataframe["month"]) == ["2026-01", "2026-03", "2026-04"]


def test_duckdb_time_coverage_returns_date_range() -> None:
    engine = DuckDBComputeEngine()
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-01-09", "2026-03-01", "2026-04-11"],
            "revenue": [10.0, 20.0, 30.0],
        }
    )

    table = engine.time_coverage(dataframe, time_column="posted_at", mode="date_range")

    row = table.dataframe.iloc[0]
    assert row["earliest_date"] == "2026-01-09"
    assert row["latest_date"] == "2026-04-11"
    assert row["non_null_row_count"] == 3


def test_duckdb_time_coverage_ignores_invalid_dates() -> None:
    engine = DuckDBComputeEngine()
    dataframe = pd.DataFrame(
        {
            "posted_at": ["not-a-date", "2026-03-01", None, "2027-01-01"],
            "revenue": [10.0, 20.0, 30.0, 40.0],
        }
    )

    table = engine.time_coverage(dataframe, time_column="posted_at", mode="years_present")

    assert list(table.dataframe["year"]) == [2026, 2027]


def test_duckdb_time_coverage_returns_empty_years_for_all_invalid_dates() -> None:
    engine = DuckDBComputeEngine()
    dataframe = pd.DataFrame({"posted_at": ["bad", None], "revenue": [10.0, 20.0]})

    table = engine.time_coverage(dataframe, time_column="posted_at", mode="years_present")

    assert table.dataframe.empty is True


def test_duckdb_time_coverage_rejects_unsupported_mode() -> None:
    engine = DuckDBComputeEngine()

    with pytest.raises(ComputeError, match="Unsupported time coverage mode"):
        engine.time_coverage(build_dataframe(), time_column="posted_at", mode="week_numbers")


def test_duckdb_ranked_breakdown_respects_limit() -> None:
    engine = DuckDBComputeEngine()
    dataframe = build_dataframe()

    ranked = engine.ranked_breakdown(dataframe, target="revenue", group_by=["region"], limit=1)

    assert len(ranked.dataframe) == 1
    assert ranked.dataframe.iloc[0]["rank"] == 1


def test_duckdb_grouped_period_comparison_and_top_movers() -> None:
    engine = DuckDBComputeEngine()
    dataframe = build_dataframe()

    grouped_comparison = engine.grouped_period_comparison(
        dataframe,
        target="revenue",
        group_by=["region"],
        time_column="posted_at",
        time_reference={"type": "month_name", "value": "march", "month": "3"},
    )
    movers = engine.top_movers(
        dataframe,
        target="revenue",
        group_by=["region"],
        time_column="posted_at",
        time_reference={"type": "month_name", "value": "march", "month": "3"},
        limit=2,
    )

    assert "pct_change" in grouped_comparison.dataframe.columns
    assert "abs_delta" in movers.dataframe.columns
    assert len(movers.dataframe) <= 2


def test_stats_engine_returns_correlation_and_anomalies() -> None:
    engine = StatsComputeEngine()
    dataframe = build_dataframe()

    distribution_table = engine.distribution_summary(dataframe, target="revenue")
    correlation_table = engine.correlation_matrix(dataframe, target="revenue")
    anomaly_table = engine.anomaly_summary(dataframe, target="revenue", time_column="posted_at")
    comparison_table = engine.group_mean_comparison(dataframe, target="revenue", group_column="region")
    diagnostics_table = engine.time_series_diagnostics(dataframe, target="revenue", time_column="posted_at")

    assert distribution_table is not None
    assert "skewness" in distribution_table.dataframe.columns
    assert correlation_table is not None
    assert "correlation" in correlation_table.dataframe.columns
    assert anomaly_table is not None
    assert len(anomaly_table.dataframe) >= 1
    assert comparison_table is not None
    assert "p_value" in comparison_table.dataframe.columns
    assert diagnostics_table is not None
    assert "lag1_autocorrelation" in diagnostics_table.dataframe.columns


def test_duckdb_engine_rejects_invalid_filters() -> None:
    engine = DuckDBComputeEngine()

    with pytest.raises(ComputeError, match="Filter column 'missing' does not exist"):
        engine.dataset_summary(build_dataframe(), target="revenue", filters={"missing": "West"})


def test_duckdb_engine_rejects_filters_that_remove_all_rows() -> None:
    engine = DuckDBComputeEngine()

    with pytest.raises(ComputeError, match="Filters removed all rows"):
        engine.dataset_summary(build_dataframe(), target="revenue", filters={"region": "North"})


def test_stats_engine_rejects_missing_target_columns() -> None:
    engine = StatsComputeEngine()

    with pytest.raises(ComputeError, match="Target column 'profit' does not exist"):
        engine.distribution_summary(build_dataframe(), target="profit")


def test_duckdb_dataset_summary_returns_core_metrics() -> None:
    engine = DuckDBComputeEngine()

    metrics, tables = engine.dataset_summary(build_dataframe(), target="revenue")
    metric_lookup = {metric.name: metric.value for metric in metrics}

    assert metric_lookup["row_count"] == 5
    assert metric_lookup["column_count"] == 4
    assert metric_lookup["revenue_sum"] == 600.0
    assert tables[0].name == "dataset_preview"


def test_duckdb_aggregate_value_returns_mean_metric() -> None:
    engine = DuckDBComputeEngine()

    metrics = engine.aggregate_value(build_dataframe(), target="revenue", aggregation="mean")

    assert metrics[0].name == "revenue_mean"
    assert metrics[0].value == 120.0


def test_duckdb_aggregate_value_returns_max_metric() -> None:
    engine = DuckDBComputeEngine()

    metrics = engine.aggregate_value(build_dataframe(), target="revenue", aggregation="max")

    assert metrics[0].name == "revenue_max"
    assert metrics[0].value == 300.0


def test_duckdb_group_breakdown_supports_mean_aggregation() -> None:
    engine = DuckDBComputeEngine()

    table = engine.group_breakdown(build_dataframe(), target="revenue", group_by=["region"], aggregation="mean")

    assert list(table.dataframe["target_total"]) == [160.0, 60.0]


def test_duckdb_period_comparison_supports_mean_aggregation() -> None:
    engine = DuckDBComputeEngine()

    table = engine.period_comparison(
        build_dataframe(),
        target="revenue",
        time_column="posted_at",
        time_reference={"type": "month_name", "value": "march", "month": "3"},
        aggregation="mean",
    )

    assert list(table.dataframe["target_total"]) == [100.0, 50.0]


def test_duckdb_group_breakdown_orders_by_target_total() -> None:
    engine = DuckDBComputeEngine()

    table = engine.group_breakdown(build_dataframe(), target="revenue", group_by=["region"])

    assert list(table.dataframe["region"]) == ["West", "East"]


def test_duckdb_contribution_breakdown_without_time_returns_share_of_total() -> None:
    engine = DuckDBComputeEngine()

    table = engine.contribution_breakdown(build_dataframe(), target="revenue", group_by=["region"])

    assert "share_of_total" in table.dataframe.columns
    assert pytest.approx(float(table.dataframe["share_of_total"].sum()), 0.0001) == 1.0


def test_duckdb_period_comparison_returns_empty_for_unmatched_month() -> None:
    engine = DuckDBComputeEngine()

    table = engine.period_comparison(
        build_dataframe(),
        target="revenue",
        time_column="posted_at",
        time_reference={"type": "month_name", "value": "january", "month": "1"},
    )

    assert table.dataframe.empty is True


def test_duckdb_time_trend_respects_filters() -> None:
    engine = DuckDBComputeEngine()

    table = engine.time_trend(build_dataframe(), target="revenue", time_column="posted_at", filters={"region": "West"})

    assert list(table.dataframe["target_total"]) == [120.0, 60.0, 300.0]


def test_duckdb_ranked_rows_returns_top_n_numeric_rows() -> None:
    engine = DuckDBComputeEngine()

    table = engine.ranked_rows(build_dataframe(), target="revenue", limit=3)

    assert list(table.dataframe["rank"]) == [1, 2, 3]
    assert list(table.dataframe["revenue"]) == [300.0, 120.0, 80.0]


def test_duckdb_ranked_rows_returns_bottom_n_numeric_rows() -> None:
    engine = DuckDBComputeEngine()

    table = engine.ranked_rows(build_dataframe(), target="revenue", ascending=True, limit=2)

    assert list(table.dataframe["revenue"]) == [40.0, 60.0]


def test_duckdb_ranked_rows_keeps_original_columns() -> None:
    engine = DuckDBComputeEngine()

    table = engine.ranked_rows(build_dataframe(), target="revenue", limit=1)

    assert "region" in table.dataframe.columns
    assert "posted_at" in table.dataframe.columns


def test_duckdb_ranked_rows_respects_filters() -> None:
    engine = DuckDBComputeEngine()

    table = engine.ranked_rows(build_dataframe(), target="revenue", filters={"region": "West"}, limit=2)

    assert list(table.dataframe["revenue"]) == [300.0, 120.0]


def test_duckdb_ranked_rows_handles_limit_larger_than_dataset() -> None:
    engine = DuckDBComputeEngine()

    table = engine.ranked_rows(build_dataframe(), target="revenue", limit=99)

    assert len(table.dataframe) == 5


def test_duckdb_ranked_rows_rejects_non_numeric_target() -> None:
    engine = DuckDBComputeEngine()

    with pytest.raises(ComputeError, match="has no numeric values for row ranking"):
        engine.ranked_rows(build_dataframe(), target="region", limit=3)


def test_duckdb_ranked_breakdown_supports_bottom_n_ordering() -> None:
    engine = DuckDBComputeEngine()

    table = engine.ranked_breakdown(build_dataframe(), target="revenue", group_by=["region"], limit=1, ascending=True)

    assert list(table.dataframe["region"]) == ["East"]
    assert list(table.dataframe["target_total"]) == [120.0]


def test_duckdb_ranked_breakdown_handles_limit_larger_than_group_count() -> None:
    engine = DuckDBComputeEngine()

    table = engine.ranked_breakdown(build_dataframe(), target="revenue", group_by=["region"], limit=10)

    assert len(table.dataframe) == 2


def test_duckdb_ranked_rows_preserves_descending_order_on_ties_by_dataframe_order() -> None:
    engine = DuckDBComputeEngine()
    dataframe = pd.DataFrame(
        {
            "revenue": [100.0, 100.0, 90.0],
            "region": ["West", "East", "North"],
        }
    )

    table = engine.ranked_rows(dataframe, target="revenue", limit=2)

    assert list(table.dataframe["region"]) == ["West", "East"]


def test_duckdb_ranked_rows_supports_single_row_dataset() -> None:
    engine = DuckDBComputeEngine()
    dataframe = pd.DataFrame({"revenue": [42.0], "region": ["West"]})

    table = engine.ranked_rows(dataframe, target="revenue", limit=5)

    assert list(table.dataframe["rank"]) == [1]
    assert list(table.dataframe["revenue"]) == [42.0]


def test_duckdb_top_movers_returns_empty_when_month_missing() -> None:
    engine = DuckDBComputeEngine()

    table = engine.top_movers(
        build_dataframe(),
        target="revenue",
        group_by=["region"],
        time_column="posted_at",
        time_reference={"type": "month_name", "value": "january", "month": "1"},
    )

    assert table.dataframe.empty is True


def test_stats_numeric_summary_handles_non_numeric_frame() -> None:
    engine = StatsComputeEngine()
    dataframe = pd.DataFrame({"region": ["West", "East"]})

    table = engine.numeric_summary(dataframe)

    assert list(table.dataframe.columns) == ["column", "count", "mean", "std", "min", "max"]
    assert table.dataframe.empty is True


def test_stats_correlation_returns_none_for_single_numeric_column() -> None:
    engine = StatsComputeEngine()
    dataframe = pd.DataFrame({"revenue": [100.0, 120.0, 90.0], "region": ["West", "East", "West"]})

    table = engine.correlation_matrix(dataframe, target="revenue")

    assert table is None


def test_stats_anomaly_summary_returns_none_for_constant_series() -> None:
    engine = StatsComputeEngine()
    dataframe = pd.DataFrame({"revenue": [100.0, 100.0, 100.0], "posted_at": ["2026-01-01", "2026-02-01", "2026-03-01"]})

    table = engine.anomaly_summary(dataframe, target="revenue", time_column="posted_at")

    assert table is None


def test_stats_time_series_diagnostics_returns_none_for_short_history() -> None:
    engine = StatsComputeEngine()
    dataframe = pd.DataFrame({"revenue": [100.0, 90.0], "posted_at": ["2026-01-01", "2026-02-01"]})

    table = engine.time_series_diagnostics(dataframe, target="revenue", time_column="posted_at")

    assert table is None


def test_stats_group_mean_comparison_rejects_same_group_and_target() -> None:
    engine = StatsComputeEngine()

    with pytest.raises(ComputeError, match="different from the target"):
        engine.group_mean_comparison(build_dataframe(), target="revenue", group_column="revenue")


def test_stats_t_test_returns_significance_payload() -> None:
    engine = StatsComputeEngine()

    table = engine.t_test(build_statistical_dataframe(), target="revenue", group_column="region")

    assert table.name == "t_test"
    assert "p_value" in table.dataframe.columns
    assert "is_significant" in table.dataframe.columns


def test_stats_chi_square_test_returns_independence_result() -> None:
    engine = StatsComputeEngine()

    table = engine.chi_square_test(build_statistical_dataframe(), left_column="segment", right_column="region")

    assert table.name == "chi_square_test"
    assert table.dataframe.iloc[0]["degrees_of_freedom"] >= 1


def test_stats_anova_test_returns_group_significance() -> None:
    engine = StatsComputeEngine()

    table = engine.anova_test(build_statistical_dataframe(), target="revenue", group_column="team")

    assert table.name == "anova_test"
    assert table.dataframe.iloc[0]["group_count"] == 3


def test_stats_mann_whitney_test_returns_non_parametric_result() -> None:
    engine = StatsComputeEngine()

    table = engine.mann_whitney_test(build_statistical_dataframe(), target="revenue", group_column="region")

    assert table.name == "mann_whitney_test"
    assert "p_value" in table.dataframe.columns


def test_stats_confidence_interval_returns_bounds() -> None:
    engine = StatsComputeEngine()

    table = engine.confidence_interval(build_statistical_dataframe(), target="revenue", confidence_level=0.95)

    assert table.name == "confidence_interval"
    assert table.dataframe.iloc[0]["lower_bound"] < table.dataframe.iloc[0]["upper_bound"]


def test_stats_regression_significance_returns_coefficients() -> None:
    engine = StatsComputeEngine()

    table = engine.regression_significance(
        build_statistical_dataframe(),
        target="revenue",
        feature_columns=["cost", "units"],
    )

    assert table.name == "regression_significance"
    assert set(table.dataframe["parameter"]) >= {"const", "cost", "units"}


def test_stats_power_analysis_returns_power_estimate() -> None:
    engine = StatsComputeEngine()

    table = engine.power_analysis(build_statistical_dataframe(), target="revenue", group_column="region")

    assert table.name == "power_analysis"
    assert 0.0 <= table.dataframe.iloc[0]["power"] <= 1.0


def test_stats_sample_size_estimate_returns_required_group_size() -> None:
    engine = StatsComputeEngine()

    table = engine.sample_size_estimate(
        build_statistical_dataframe(),
        target="revenue",
        group_column="region",
        desired_power=0.9,
    )

    assert table.name == "sample_size_estimate"
    assert table.dataframe.iloc[0]["required_sample_size_per_group"] > 0


def test_stats_power_analysis_rejects_zero_effect_size() -> None:
    engine = StatsComputeEngine()
    dataframe = pd.DataFrame({"region": ["North"] * 4 + ["South"] * 4, "revenue": [100, 100, 100, 100, 100, 100, 100, 100]})

    with pytest.raises(ComputeError, match="non-zero observed effect size"):
        engine.power_analysis(dataframe, target="revenue", group_column="region")


_DUCKDB_SUMMARY_CASES = [
    (
        index,
        pd.DataFrame(
            {
                "posted_at": ["2026-02-01", "2026-03-01", "2026-04-01"],
                "revenue": [float(index), float(index + 10), float(index + 20)],
                "region": ["West", "East", "West"],
            }
        ),
    )
    for index in range(1, 84)
]


@pytest.mark.parametrize(("case_id", "dataframe"), _DUCKDB_SUMMARY_CASES)
def test_duckdb_and_stats_handle_many_small_cases(case_id: int, dataframe: pd.DataFrame) -> None:
    duckdb_engine = DuckDBComputeEngine()
    stats_engine = StatsComputeEngine()

    metrics, tables = duckdb_engine.dataset_summary(dataframe, target="revenue")
    trend = duckdb_engine.time_trend(dataframe, target="revenue", time_column="posted_at")
    distribution = stats_engine.distribution_summary(dataframe, target="revenue")

    assert any(metric.name == "revenue_sum" for metric in metrics)
    assert tables[0].name == "dataset_preview"
    assert len(trend.dataframe) == 3
    assert distribution is not None
    assert distribution.dataframe.iloc[0]["count"] == 3
