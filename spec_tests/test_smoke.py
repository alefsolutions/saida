from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd
import pytest

from saida import Saida
from saida.core import DatasetProfiler, SourceContextParser
from saida.core.contracts import Dataset
from saida.exceptions import ModelTrainingError
from saida.sources import CSVAdapter, JSONAdapter, PandasAdapter, SQLAdapter


def test_context_parser_extracts_metrics_and_rules() -> None:
    markdown = """
# Dataset: Sales

## Metrics
revenue = total invoice value

## Important Rules
- cancelled orders must be excluded
""".strip()

    context = SourceContextParser().parse(markdown)

    assert context.metric_definitions["revenue"] == "total invoice value"
    assert context.business_rules == ["cancelled orders must be excluded"]


def test_context_parser_supports_all_documented_sections() -> None:
    markdown = """
# Dataset: Sales

## Table Descriptions
orders: order-level sales facts

## Field Descriptions
- posted_at: posting timestamp
- customer_id: customer identifier

## Metric Definitions
revenue: total invoice value after discounts

## Business Rules
- cancelled orders must be excluded

## Caveats
- refunds arrive one day late

## Trusted Date Fields
- posted_at
- settled_at

## Preferred Identifiers
- customer_id

## Freshness Notes
- source refreshes daily
""".strip()

    context = SourceContextParser().parse(markdown)

    assert context.source_summary == "Sales"
    assert context.table_descriptions["orders"] == "order-level sales facts"
    assert context.field_descriptions["posted_at"] == "posting timestamp"
    assert context.metric_definitions["revenue"] == "total invoice value after discounts"
    assert context.business_rules == ["cancelled orders must be excluded"]
    assert context.caveats == ["refunds arrive one day late"]
    assert context.trusted_date_fields == ["posted_at", "settled_at"]
    assert context.preferred_identifiers == ["customer_id"]
    assert context.freshness_notes == ["source refreshes daily"]


def test_context_parser_extracts_field_sections() -> None:
    markdown = """
# Summary
sales dataset

## Field Descriptions
revenue = total revenue
region = sales region

## Table Descriptions
orders = order-level facts
""".strip()

    context = SourceContextParser().parse(markdown)

    assert context.source_summary == "sales dataset"
    assert context.field_descriptions["revenue"] == "total revenue"
    assert context.table_descriptions["orders"] == "order-level facts"


def test_analyze_runs_end_to_end(tmp_path: Path) -> None:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text(
        "posted_at,revenue,region\n"
        "2026-01-01,100,West\n"
        "2026-02-01,90,West\n"
        "2026-03-01,80,East\n",
        encoding="utf-8",
    )

    dataset = CSVAdapter(csv_path).load()
    dataset.context = SourceContextParser().parse(
        """
# Dataset: Sales

## Caveats
- refunds arrive one day late
""".strip()
    )
    result = Saida().analyze(dataset, "Why did revenue drop in March?")

    assert result.summary
    assert "Revenue moved from 90.00 in 2026-02 to 80.00 in 2026-03" in result.summary
    assert "Context caveat: refunds arrive one day late." in result.summary
    assert any(metric.name == "row_count" for metric in result.metrics)
    assert any(table.name == "time_trend" for table in result.tables)
    assert any(table.name == "numeric_summary" for table in result.tables)
    assert any(table.name == "period_comparison" for table in result.tables)
    assert any(table.name == "contribution_breakdown" for table in result.tables)
    assert any(table.name == "ranked_breakdown" for table in result.tables)
    assert result.artifacts["request"]["task_type_hint"] == "diagnostic"
    assert "metric_lookup" in result.artifacts
    assert "table_index" in result.artifacts
    assert "time_trend" in result.artifacts["table_index"]
    assert "trace_stages" in result.artifacts
    assert result.artifacts["profile"]["dataset_name"] == "sales"


def test_json_adapter_loads_records(tmp_path: Path) -> None:
    json_path = tmp_path / "sales.json"
    json_path.write_text('[{"revenue": 100, "region": "West"}]', encoding="utf-8")

    dataset = JSONAdapter(json_path).load()

    assert dataset.source_type == "json"
    assert list(dataset.data.columns) == ["revenue", "region"]


def test_sql_adapter_loads_query_results(tmp_path: Path) -> None:
    database_path = tmp_path / "sales.db"
    connection = sqlite3.connect(database_path)
    connection.execute("create table sales (revenue integer, region text)")
    connection.execute("insert into sales (revenue, region) values (100, 'West')")
    connection.commit()
    connection.close()

    dataset = SQLAdapter(database_path, "select revenue, region from sales").load()

    assert dataset.source_type == "sql"
    assert dataset.data.iloc[0]["revenue"] == 100


def test_pandas_adapter_keeps_context() -> None:
    dataframe = pd.DataFrame({"revenue": [100, 120], "region": ["West", "East"]})
    adapter = PandasAdapter(
        dataframe,
        name="sales",
        context_markdown="""
# Dataset: Sales

## Metrics
revenue = total invoice value
""".strip(),
    )

    dataset = adapter.load()

    assert dataset.name == "sales"
    assert dataset.context is not None
    assert dataset.context.metric_definitions["revenue"] == "total invoice value"


def test_analyze_applies_group_and_filter_detection() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "revenue": [100, 50, 25],
            "region": ["West", "East", "West"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "Show revenue by region for West")

    grouped_tables = [table for table in result.tables if table.name == "group_breakdown"]
    assert grouped_tables
    grouped = grouped_tables[0].dataframe
    assert set(grouped["region"]) == {"West"}


def test_analyze_returns_ranked_breakdown_and_contribution_tables() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": [
                "2026-02-01",
                "2026-02-01",
                "2026-03-01",
                "2026-03-01",
            ],
            "revenue": [120, 80, 60, 40],
            "region": ["West", "East", "West", "East"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "Why did revenue drop in March by region?")

    ranked_table = next(table for table in result.tables if table.name == "ranked_breakdown")
    contribution_table = next(table for table in result.tables if table.name == "contribution_breakdown")
    grouped_period_table = next(table for table in result.tables if table.name == "grouped_period_comparison")
    mover_table = next(table for table in result.tables if table.name == "top_movers")

    assert "rank" in ranked_table.dataframe.columns
    assert "delta" in contribution_table.dataframe.columns
    assert "pct_change" in grouped_period_table.dataframe.columns
    assert "abs_delta" in mover_table.dataframe.columns
    assert not contribution_table.dataframe.empty
    assert "plan_step_ids" in result.artifacts
    assert "contribution_breakdown" in result.artifacts["plan_step_ids"]
    assert "Top contributor was region=West" in result.summary
    assert "Top mover was region=West" in result.summary


def test_analyze_returns_anomaly_summary_for_outlier_series() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": [
                "2026-01-01",
                "2026-02-01",
                "2026-03-01",
                "2026-04-01",
                "2026-05-01",
            ],
            "revenue": [100, 105, 98, 102, 300],
            "region": ["West", "West", "West", "West", "West"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "Show revenue trend")

    distribution_table = next(table for table in result.tables if table.name == "distribution_summary")
    anomaly_table = next(table for table in result.tables if table.name == "anomaly_summary")
    diagnostics_table = next(table for table in result.tables if table.name == "time_series_diagnostics")

    assert "skewness" in distribution_table.dataframe.columns
    assert len(anomaly_table.dataframe) >= 1
    assert "lag1_autocorrelation" in diagnostics_table.dataframe.columns
    assert all(table.name != "group_mean_comparison" for table in result.tables)


def test_train_forecast_and_predict_raise_not_implemented() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-01-01", "2026-02-01", "2026-03-01"],
            "sales": [100, 110, 120],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)
    engine = Saida()

    with pytest.raises(ModelTrainingError):
        engine.train(dataset, target="sales")

    with pytest.raises(ModelTrainingError):
        engine.predict(dataset, artifact_path="model.json")

    with pytest.raises(ModelTrainingError):
        engine.forecast(dataset, target="sales", horizon=2)


def test_engine_capabilities_mark_ml_as_deferred() -> None:
    capabilities = Saida().capabilities()

    assert capabilities["analyze"] is True
    assert capabilities["profile"] is True
    assert capabilities["load_context"] is True
    assert capabilities["train"] is False
    assert capabilities["predict"] is False
    assert capabilities["forecast"] is False
    assert capabilities["llm_prompting"] is False
    assert capabilities["llm_reasoning"] is False


def test_profiler_detects_identifiers_dimensions_and_measures() -> None:
    dataframe = pd.DataFrame(
        {
            "customer_id": ["c1", "c2", "c3", "c4"],
            "region": ["West", "West", "East", "East"],
            "revenue": [100.0, 120.0, 80.0, 90.0],
            "posted_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    profile = DatasetProfiler().profile(dataset)

    assert "customer_id" in profile.identifier_columns
    assert "region" in profile.dimension_columns
    assert "revenue" in profile.measure_columns
    assert "posted_at" in profile.time_columns


def test_profiler_does_not_treat_unique_integer_measures_as_identifiers() -> None:
    dataframe = pd.DataFrame(
        {
            "revenue": [100, 101, 102, 103],
            "posted_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    profile = DatasetProfiler().profile(dataset)

    assert "revenue" in profile.measure_columns
    assert "revenue" not in profile.identifier_columns
    assert "revenue" not in profile.dimension_columns


def test_profiler_marks_low_cardinality_strings_as_category() -> None:
    dataframe = pd.DataFrame(
        {
            "segment": ["SMB", "SMB", "Enterprise", "Enterprise", "SMB"],
            "value": [1, 2, 3, 4, 5],
        }
    )
    dataset = Dataset(name="segments", source_type="pandas", data=dataframe)

    profile = DatasetProfiler().profile(dataset)
    segment_profile = next(column for column in profile.columns if column.name == "segment")

    assert segment_profile.inferred_type == "category"
    assert segment_profile.is_dimension_candidate is True


def test_profiler_warns_on_duplicates_and_limited_readiness() -> None:
    dataframe = pd.DataFrame(
        {
            "id": [1, 1, 2],
            "flag": ["yes", "yes", "no"],
        }
    )
    dataset = Dataset(name="small", source_type="pandas", data=dataframe)

    profile = DatasetProfiler().profile(dataset)

    assert profile.duplicate_row_count == 1
    assert "Dataset contains duplicate rows." in profile.warnings
    assert profile.ml_readiness is not None
    assert profile.ml_readiness.forecasting_ready is False
    assert any("No time column" in warning for warning in profile.ml_readiness.readiness_warnings)


def test_analyze_supports_json_adapter_input(tmp_path: Path) -> None:
    json_path = tmp_path / "sales.json"
    json_path.write_text(
        '[{"posted_at": "2026-02-01", "revenue": 120, "region": "West"}, {"posted_at": "2026-03-01", "revenue": 80, "region": "East"}]',
        encoding="utf-8",
    )

    dataset = JSONAdapter(json_path).load()
    result = Saida().analyze(dataset, "Why did revenue drop in March?")

    assert result.plan.task_type == "diagnostic"
    assert any(table.name == "period_comparison" for table in result.tables)


def test_analyze_computes_average_value_for_aggregation_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-02-01", "2026-02-02", "2026-03-01", "2026-03-02"],
            "revenue": [100.0, 80.0, 60.0, 40.0],
            "region": ["West", "East", "West", "East"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "What is the average revenue?")

    assert "Average revenue is 70.00." in result.summary
    assert any(metric.name == "revenue_mean" for metric in result.metrics)


def test_analyze_prioritizes_grouped_total_answer_for_grouped_aggregation_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": [
                "2026-01-01",
                "2026-01-02",
                "2026-02-01",
                "2026-02-02",
            ],
            "revenue": [100.0, 120.0, 90.0, 80.0],
            "region": ["West", "West", "East", "East"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "Give me the total revenue by region")

    assert "Total revenue by region: region=West = 220.00; region=East = 170.00." in result.summary
    assert "The latest period is" not in result.summary
    assert any(table.name == "group_breakdown" for table in result.tables)


def test_analyze_lists_distinct_dimension_values_for_list_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            "revenue": [100.0, 120.0, 90.0, 80.0],
            "segment": ["Retail", "Wholesale", "Retail", "Online"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "Give me a list of all segments")

    assert "Available segment values: Online, Retail, Wholesale." in result.summary
    assert any(table.name == "distinct_values" for table in result.tables)
    assert result.plan.steps[0].action == "distinct_values"


def test_analyze_lists_distinct_dimension_values_for_category_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "created_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            "resolution_hours": [4.2, 6.0, 3.1, 8.4],
            "priority": ["Low", "Medium", "High", "Urgent"],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "What are the different priority categories in the data?")

    assert "Available priority values: High, Low, Medium, Urgent." in result.summary
    assert result.response["interpretation"]["intent_name"] == "distinct_values"
    assert any(table.name == "distinct_values" for table in result.tables)
    assert all(table.name != "time_trend" for table in result.tables)


def test_analyze_counts_rows_for_row_count_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "revenue": [100.0, 120.0, 90.0],
            "segment": ["Retail", "Wholesale", "Retail"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "How many data rows do we have?")

    assert result.summary.endswith("The dataset contains 3 rows.")
    assert result.response["interpretation"]["intent_name"] == "row_count"
    assert any(metric.name == "row_count" for metric in result.metrics)


def test_analyze_identifies_least_represented_group() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            "revenue": [100.0, 120.0, 90.0, 80.0],
            "segment": ["Retail", "Retail", "Wholesale", "Online"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "Which segment is the least represented in sales data?")

    assert "The least represented segment is segment=Online with 1 rows." in result.summary
    assert result.response["interpretation"]["intent_name"] == "representation_ranking"
    assert any(table.name == "group_row_counts" for table in result.tables)


def test_analyze_returns_column_inventory() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-01-01"],
            "revenue": [100.0],
            "segment": ["Retail"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "What are the columns in the sales data?")

    assert "Available columns: posted_at, revenue, segment." in result.summary
    assert result.response["interpretation"]["intent_name"] == "column_inventory"
    assert any(table.name == "column_inventory" for table in result.tables)


def test_analyze_returns_time_coverage_years() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2024-01-01", "2025-02-01", "2026-03-01", "bad-date"],
            "revenue": [90.0, 100.0, 120.0, 130.0],
            "segment": ["Retail", "Retail", "Online", "Online"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "The data shows revenue for which years?")

    assert "The data contains records for these years: 2024, 2025, 2026." in result.summary
    assert result.response["interpretation"]["intent_name"] == "time_coverage"
    assert result.response["interpretation"]["options"]["time_coverage_mode"] == "years_present"
    assert any(table.name == "time_coverage" for table in result.tables)


def test_analyze_returns_time_coverage_date_range() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-01-09", "2026-02-01", "2026-04-11"],
            "revenue": [90.0, 100.0, 120.0],
            "segment": ["Retail", "Retail", "Online"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "What date range does the sales data cover?")

    assert "The data covers 2026-01-09 to 2026-04-11." in result.summary
    assert any(table.name == "time_coverage" for table in result.tables)


def test_analyze_supports_p_value_driven_inference_workflow() -> None:
    dataframe = pd.DataFrame(
        {
            "region": ["North"] * 6 + ["South"] * 6,
            "revenue": [100, 104, 98, 102, 101, 99, 135, 138, 132, 140, 136, 134],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "Is revenue by region statistically significant?")

    assert "Welch t-test for revenue by region" in result.summary
    assert any(table.name == "significance_test" for table in result.tables)


def test_analyze_supports_natural_significance_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "region": ["North"] * 6 + ["South"] * 6,
            "revenue": [100, 104, 98, 102, 101, 99, 135, 138, 132, 140, 136, 134],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "Do regions differ in revenue?")

    assert "Welch t-test for revenue by region" in result.summary
    assert result.response["interpretation"]["options"]["statistical_test"] == "significance_inference"
    assert any(table.name == "significance_test" for table in result.tables)


def test_analyze_supports_natural_confidence_interval_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "revenue": [100.0, 103.0, 98.0, 110.0, 105.0, 107.0],
            "region": ["West", "West", "East", "East", "West", "East"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "What range are we 95% confident revenue falls in?")

    assert "confidence interval for revenue" in result.summary
    assert result.response["interpretation"]["options"]["statistical_test"] == "confidence_interval"
    assert any(table.name == "confidence_interval" for table in result.tables)


def test_analyze_supports_natural_power_analysis_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "region": ["North"] * 8 + ["South"] * 8,
            "revenue": [100, 101, 99, 102, 98, 100, 101, 99, 120, 121, 119, 123, 118, 122, 120, 121],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "Do we have enough data to detect a difference in revenue by region?")

    assert "Observed power" in result.summary
    assert result.response["interpretation"]["options"]["statistical_test"] == "power_analysis"
    assert any(table.name == "power_analysis" for table in result.tables)


def test_analyze_supports_natural_sample_size_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "region": ["North"] * 8 + ["South"] * 8,
            "revenue": [100, 101, 99, 102, 98, 100, 101, 99, 120, 121, 119, 123, 118, 122, 120, 121],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "How many rows per group do we need for revenue by region?")

    assert "Estimated sample size per group" in result.summary
    assert result.response["interpretation"]["options"]["statistical_test"] == "sample_size_estimate"
    assert any(table.name == "sample_size_estimate" for table in result.tables)


def test_analyze_supports_natural_regression_significance_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "resolution_hours": [2.1, 5.4, 6.8, 4.2, 7.1, 8.0, 2.5, 3.0],
            "csat_score": [4.7, 4.0, 3.6, 4.1, 3.5, 3.2, 4.5, 4.3],
            "team": ["Support", "Support", "Platform", "Platform", "Support", "Platform", "Support", "Platform"],
        }
    )
    dataset = Dataset(name="tickets", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "Does resolution_hours significantly affect csat_score?")

    assert "Regression significance" in result.summary
    assert result.response["interpretation"]["target"] == "csat_score"
    assert result.response["interpretation"]["options"]["feature_columns"] == ["resolution_hours"]
    assert any(table.name == "regression_significance" for table in result.tables)


def test_analyze_supports_ranked_row_retrieval_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "resolution_hours": [22.05, 18.40, 14.20, 10.10, 8.35, 7.10],
            "team": ["Support", "Platform", "Support", "Payments", "Platform", "Support"],
            "priority": ["Urgent", "High", "Medium", "Low", "High", "Low"],
        }
    )
    dataset = Dataset(name="support_tickets_500", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "What is the top 5 longest hours of resolution?")

    assert result.response["interpretation"]["intent_name"] == "row_ranking"
    assert result.response["interpretation"]["target"] == "resolution_hours"
    assert "Top 5 resolution hours values" in result.summary
    assert any(table.name == "ranked_rows" for table in result.tables)


def test_analyze_supports_group_ranking_summary_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "revenue": [120.0, 80.0, 60.0, 40.0, 300.0],
            "region": ["West", "East", "West", "East", "West"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, "Show bottom 2 revenue by region")

    assert result.response["interpretation"]["intent_name"] == "group_ranking"
    assert "Bottom 2 revenue groups" in result.summary
    assert any(table.name == "ranked_breakdown" for table in result.tables)


def test_analyze_time_coverage_rejects_datasets_without_time_columns() -> None:
    dataframe = pd.DataFrame({"revenue": [90.0, 100.0], "segment": ["Retail", "Online"]})
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    with pytest.raises(Exception):
        Saida().analyze(dataset, "Which years are present in the sales data?")


def test_analyze_supports_sql_adapter_input(tmp_path: Path) -> None:
    database_path = tmp_path / "sales.db"
    connection = sqlite3.connect(database_path)
    connection.execute("create table sales (posted_at text, revenue integer, region text)")
    connection.execute("insert into sales values ('2026-02-01', 120, 'West')")
    connection.execute("insert into sales values ('2026-03-01', 80, 'East')")
    connection.commit()
    connection.close()

    dataset = SQLAdapter(database_path, "select posted_at, revenue, region from sales").load()
    result = Saida().analyze(dataset, "Why did revenue drop in March?")

    assert result.summary
    assert any(metric.name == "revenue_sum" for metric in result.metrics)


def test_analyze_rejects_quarter_prompt_until_supported() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-01-01", "2026-02-01", "2026-03-01"],
            "revenue": [100, 110, 120],
            "region": ["West", "West", "East"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    with pytest.raises(Exception):
        Saida().analyze(dataset, "Show revenue in Q1")


def test_profiler_warns_when_no_measures_or_time_columns_detected() -> None:
    dataframe = pd.DataFrame({"region": ["West", "East"], "segment": ["SMB", "Enterprise"]})
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    profile = DatasetProfiler().profile(dataset)

    assert "No measure columns were detected." in profile.warnings
    assert "No datetime columns detected." in profile.warnings


def test_profiler_detects_time_column_when_most_values_are_valid_dates() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2024-01-01", "2025-02-01", "2026-03-01", "bad-date"],
            "revenue": [90.0, 100.0, 120.0, 130.0],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    profile = DatasetProfiler().profile(dataset)

    assert "posted_at" in profile.time_columns


_SMOKE_ANALYZE_CASES = [
    (
        index,
        pd.DataFrame(
            {
                "posted_at": ["2026-02-01", "2026-03-01", "2026-04-01"],
                "revenue": [float(index + 20), float(index + 10), float(index + 5)],
                "region": ["West", "East", "West"],
            }
        ),
        "Why did revenue drop in March?",
    )
    for index in range(1, 84)
]


@pytest.mark.parametrize(("case_id", "dataframe", "question"), _SMOKE_ANALYZE_CASES)
def test_smoke_many_end_to_end_analysis_cases(case_id: int, dataframe: pd.DataFrame, question: str) -> None:
    dataset = Dataset(name=f"sales_{case_id}", source_type="pandas", data=dataframe)

    result = Saida().analyze(dataset, question)

    assert result.plan.task_type == "diagnostic"
    assert any(table.name == "period_comparison" for table in result.tables)
    assert result.artifacts["profile"]["dataset_name"] == f"sales_{case_id}"
