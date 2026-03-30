from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd
import pytest

from saida import PromptAnalysisFrontend, Saida
from saida.sources import DatasetProfiler, SourceContextParser
from saida.core.contracts import Dataset
from saida.exceptions import ModelTrainingError
from saida.sources import CSVAdapter, JSONAdapter, PandasAdapter, SQLAdapter
from tests.helpers.result_helpers import normalized_result_value, result_row_count


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
    result = PromptAnalysisFrontend().analyze(dataset, "Why did revenue drop in March?")

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

    result = PromptAnalysisFrontend().analyze(dataset, "Show revenue by region for West")

    grouped_tables = [table for table in result.tables if table.name == "group_breakdown"]
    assert grouped_tables
    grouped = grouped_tables[0].dataframe
    assert set(grouped["region"]) == {"West"}


def test_analyze_applies_implied_flag_filter() -> None:
    dataframe = pd.DataFrame(
        {
            "resolution_hours": [2.1, 5.4, 6.8, 4.2],
            "reopened_flag": ["yes", "no", "yes", "no"],
            "priority": ["Low", "Low", "High", "High"],
        }
    )
    dataset = Dataset(name="tickets", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "How many rows for reopened tickets?")

    assert any(metric.name == "row_count" and metric.value == 2 for metric in result.metrics)


def test_analyze_applies_exclusion_filter() -> None:
    dataframe = pd.DataFrame(
        {
            "resolution_hours": [2.1, 5.4, 6.8, 4.2],
            "reopened_flag": ["yes", "no", "yes", "no"],
            "priority": ["Low", "Low", "High", "High"],
        }
    )
    dataset = Dataset(name="tickets", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "How many rows excluding reopened tickets?")

    assert any(metric.name == "row_count" and metric.value == 2 for metric in result.metrics)


def test_analyze_applies_year_filter() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2025-01-01", "2026-02-01", "2026-03-01"],
            "revenue": [100.0, 120.0, 80.0],
            "region": ["West", "West", "East"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "What is the total revenue for West in 2026?")

    assert any(metric.name == "revenue_sum" and metric.value == 120.0 for metric in result.metrics)


def test_analyze_applies_month_filter() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-02-01", "2026-03-01", "2026-03-15"],
            "revenue": [100.0, 120.0, 80.0],
            "region": ["West", "West", "East"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "What is the total revenue for West in March?")

    assert any(metric.name == "revenue_sum" and metric.value == 120.0 for metric in result.metrics)


def test_analyze_applies_multiple_natural_filters() -> None:
    dataframe = pd.DataFrame(
        {
            "revenue": [100.0, 120.0, 80.0, 70.0],
            "region": ["West", "West", "East", "West"],
            "segment": ["SMB", "Enterprise", "SMB", "SMB"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "What is the total revenue for West SMB?")

    assert any(metric.name == "revenue_sum" and metric.value == 170.0 for metric in result.metrics)


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

    result = PromptAnalysisFrontend().analyze(dataset, "Why did revenue drop in March by region?")

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

    result = PromptAnalysisFrontend().analyze(dataset, "Show revenue trend")

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

    assert capabilities["profile"] is True
    assert capabilities["load_context"] is True
    assert capabilities["train"] is False
    assert capabilities["predict"] is False
    assert capabilities["forecast"] is False
    assert capabilities["llm_summary"] is False
    assert "analyze" not in capabilities
    assert "plan" not in capabilities


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
    result = PromptAnalysisFrontend().analyze(dataset, "Why did revenue drop in March?")

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

    result = PromptAnalysisFrontend().analyze(dataset, "What is the average revenue?")

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

    result = PromptAnalysisFrontend().analyze(dataset, "Give me the total revenue by region")

    assert "Total revenue by region:" in result.summary
    assert "region=West = 220.00" in result.summary
    assert "region=East = 170.00" in result.summary
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

    result = PromptAnalysisFrontend().analyze(dataset, "Give me a list of all segments")

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

    result = PromptAnalysisFrontend().analyze(dataset, "What are the different priority categories in the data?")

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

    result = PromptAnalysisFrontend().analyze(dataset, "How many data rows do we have?")

    assert result.summary.endswith("The dataset contains 3 rows.")
    assert result.response["interpretation"]["intent_name"] == "row_count"
    assert any(metric.name == "row_count" for metric in result.metrics)


def test_analyze_keeps_clear_open_ended_metric_prompt_on_exploratory_family() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-01-01", "2026-02-01", "2026-03-01"],
            "revenue": [100.0, 120.0, 90.0],
            "region": ["West", "West", "East"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Show revenue")

    assert result.response["status"] == "ok"
    assert result.response["interpretation"]["prompt_family"] == "exploratory_metric_overview"
    assert result.response["result"]["name"] == "summary_metrics"


@pytest.mark.parametrize(
    "question",
    [
        "Total number of columns in the dataset",
        "How many columns in the dataset?",
        "How many fields does the dataset have?",
    ],
)
def test_analyze_returns_column_count_for_metadata_count_prompt(question: str) -> None:
    dataframe = pd.DataFrame(
        {
            "created_at": ["2026-01-01", "2026-01-02"],
            "team": ["Support", "Platform"],
            "priority": ["High", "Low"],
            "channel": ["Email", "Phone"],
            "product_area": ["Billing", "Core"],
            "resolution_hours": [4.2, 6.1],
            "csat_score": [4.8, 4.1],
            "reopened_flag": ["no", "yes"],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, question)

    assert result.response["status"] == "ok"
    assert result.response["result"]["name"] == "column_count"
    assert result.response["result"]["logical_shape"] == "scalar"
    assert normalized_result_value(result.response["result"]) == 8
    assert result.response["interpretation"]["target"] is None
    assert result.response["interpretation"]["intent_name"] == "column_count"
    assert result.response["interpretation"]["prompt_family"] == "column_count"
    assert "The dataset has 8 columns." in result.summary
    assert any(table.name == "column_count" for table in result.tables)


@pytest.mark.parametrize(
    "question",
    [
        "How many unique team values are there?",
        "How many different team types are there in the dataset?",
        "How many distinct team categories are there?",
    ],
)
def test_analyze_returns_distinct_value_count_for_dimension_count_prompt(question: str) -> None:
    dataframe = pd.DataFrame(
        {
            "created_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            "resolution_hours": [4.2, 6.0, 3.1, 8.4],
            "team": ["Support", "Platform", "Support", "Infrastructure"],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, question)

    assert result.response["status"] == "ok"
    assert result.response["interpretation"]["intent_name"] == "distinct_value_count"
    assert result.response["interpretation"]["prompt_family"] == "distinct_value_count"
    assert result.response["interpretation"]["target"] == "team"
    assert result.response["result"]["name"] == "distinct_value_count"
    assert result.response["result"]["logical_shape"] == "scalar"
    assert normalized_result_value(result.response["result"]) == 3
    assert "The column team has 3 distinct values." in result.summary
    assert any(table.name == "distinct_values" for table in result.tables)


def test_analyze_returns_high_cardinality_count_without_row_existence_fallback() -> None:
    dataframe = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3", "T4"],
            "created_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            "resolution_hours": [4.2, 6.1, 3.4, 8.0],
            "team": ["Support", "Platform", "Support", "Payments"],
            "priority": ["Low", "Medium", "High", "Medium"],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "How many high-cardinality columns are there?")

    assert result.response["status"] == "ok"
    assert result.response["interpretation"]["intent_name"] == "high_cardinality_count"
    assert result.response["interpretation"]["prompt_family"] == "high_cardinality_count"
    assert result.response["result"]["name"] == "high_cardinality_count"
    assert result.response["result"]["logical_shape"] == "scalar"
    assert normalized_result_value(result.response["result"]) == 3
    assert "The dataset has 3 high-cardinality columns." in result.summary
    assert any(table.name == "high_cardinality_count" for table in result.tables)
    assert all(table.name != "row_existence" for table in result.tables)


def test_analyze_identifies_least_represented_group() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            "revenue": [100.0, 120.0, 90.0, 80.0],
            "segment": ["Retail", "Retail", "Wholesale", "Online"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Which segment is the least represented in sales data?")

    assert "The least represented segment is segment=Online with 1 rows." in result.summary
    assert result.response["interpretation"]["intent_name"] == "representation_ranking"
    assert any(table.name == "count_rows_by_group" for table in result.tables)


def test_analyze_identifies_most_represented_group_with_singular_result() -> None:
    dataframe = pd.DataFrame(
        {
            "channel": ["Email", "Phone", "Email", "Chat", "Email"],
            "priority": ["High", "High", "Low", "Low", "Medium"],
        }
    )
    dataset = Dataset(name="tickets", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Which channel has the most tickets?")

    assert "The most represented channel is channel=Email with 3 rows." in result.summary
    assert result.response["interpretation"]["intent_name"] == "representation_ranking"
    assert result.response["interpretation"]["target"] == "channel"
    assert result.response["result"]["physical_shape"] == "recordset"
    assert result.response["result"]["logical_shape"] == "table"
    assert normalized_result_value(result.response["result"])["channel"] == "Email"
    assert normalized_result_value(result.response["result"])["row_count"] == 3
    assert any(table.name == "count_rows_by_group" for table in result.tables)


def test_analyze_returns_column_inventory() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-01-01"],
            "revenue": [100.0],
            "segment": ["Retail"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "What are the columns in the sales data?")

    assert "Available columns: posted_at, revenue, segment." in result.summary
    assert result.response["interpretation"]["intent_name"] == "column_inventory"
    assert result.response["result"]["name"] == "column_inventory"
    assert result.response["result"]["logical_shape"] == "table"
    assert result_row_count(result.response["result"]) == 3
    assert any(table.name == "column_inventory" for table in result.tables)


def test_analyze_returns_column_type_inventory() -> None:
    dataframe = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3", "T4"],
            "created_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            "resolution_hours": [4.2, 6.1, 3.4, 8.0],
            "priority": ["Low", "Medium", "High", "Medium"],
            "csat_score": [4.8, None, 4.1, 3.9],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "What are the data types of each field or column in the data?")

    assert result.response["interpretation"]["intent_name"] == "column_type_inventory"
    assert "Column types:" in result.summary
    assert any(table.name == "column_type_inventory" for table in result.tables)


@pytest.mark.parametrize(
    ("question", "expected_target"),
    [
        ("What is the data type of the created_at field in dataset?", "created_at"),
        ("What type is created_at?", "created_at"),
    ],
)
def test_analyze_returns_single_column_type_lookup(question: str, expected_target: str) -> None:
    dataframe = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3", "T4"],
            "created_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            "resolution_hours": [4.2, 6.1, 3.4, 8.0],
            "priority": ["Low", "Medium", "High", "Medium"],
            "csat_score": [4.8, None, 4.1, 3.9],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, question)

    assert result.response["interpretation"]["intent_name"] == "column_type_inventory"
    assert result.response["interpretation"]["target"] == expected_target
    assert result.response["result"]["name"] == "column_type_inventory"
    assert result.response["result"]["physical_shape"] == "recordset"
    assert normalized_result_value(result.response["result"])["dtype"] == "datetime"
    assert "created_at" in result.summary
    table = next(table for table in result.tables if table.name == "column_type_inventory")
    assert len(table.dataframe) == 1
    assert list(table.dataframe["column_name"]) == ["created_at"]


def test_analyze_keeps_multi_column_type_request_as_inventory_table() -> None:
    dataframe = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3", "T4"],
            "created_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            "resolution_hours": [4.2, 6.1, 3.4, 8.0],
            "priority": ["Low", "Medium", "High", "Medium"],
            "csat_score": [4.8, None, 4.1, 3.9],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "What are the data types of created_at and csat_score?")

    assert result.response["interpretation"]["intent_name"] == "column_type_inventory"
    assert result.response["interpretation"]["target"] is None
    assert result.response["result"]["name"] == "column_type_inventory"
    table = next(table for table in result.tables if table.name == "column_type_inventory")
    assert len(table.dataframe) == 5


def test_analyze_returns_numeric_column_inventory() -> None:
    dataframe = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3", "T4"],
            "created_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            "resolution_hours": [4.2, 6.1, 3.4, 8.0],
            "priority": ["Low", "Medium", "High", "Medium"],
            "csat_score": [4.8, None, 4.1, 3.9],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Which columns are numeric?")

    assert result.response["interpretation"]["intent_name"] == "numeric_column_inventory"
    assert "Numeric columns: resolution_hours, csat_score." in result.summary
    assert any(table.name == "numeric_column_inventory" for table in result.tables)


def test_analyze_returns_categorical_column_inventory() -> None:
    dataframe = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3", "T4"],
            "priority": ["Low", "Medium", "High", "Medium"],
            "reopened_flag": ["no", "yes", "no", "no"],
            "resolution_hours": [4.2, 6.1, 3.4, 8.0],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Which fields are categorical?")

    assert result.response["interpretation"]["intent_name"] == "categorical_column_inventory"
    assert "Categorical columns:" in result.summary
    assert any(table.name == "categorical_column_inventory" for table in result.tables)


def test_analyze_returns_missing_value_inventory() -> None:
    dataframe = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3", "T4"],
            "resolution_hours": [4.2, 6.1, 3.4, 8.0],
            "csat_score": [4.8, None, 4.1, 3.9],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Which columns have missing values?")

    assert result.response["interpretation"]["intent_name"] == "missing_value_inventory"
    assert "Columns with missing values: csat_score (1 nulls, 25.0%)." in result.summary
    assert any(table.name == "missing_value_inventory" for table in result.tables)


def test_analyze_returns_no_identifier_inventory_when_none_detected() -> None:
    dataframe = pd.DataFrame(
        {
            "priority": ["Low", "Medium", "High", "Medium"],
            "resolution_hours": [4.2, 6.1, 3.4, 8.0],
            "csat_score": [4.8, 4.4, 4.1, 3.9],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Which columns are likely identifiers?")

    assert result.response["interpretation"]["intent_name"] == "identifier_inventory"
    assert "No likely identifier columns were detected." in result.summary
    assert any(table.name == "identifier_inventory" for table in result.tables)


def test_analyze_returns_identifier_inventory_when_present() -> None:
    dataframe = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3", "T4"],
            "priority": ["Low", "Medium", "High", "Medium"],
            "resolution_hours": [4.2, 6.1, 3.4, 8.0],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Which columns are likely identifiers?")

    assert result.response["interpretation"]["intent_name"] == "identifier_inventory"
    assert "Likely identifier columns: ticket_id." in result.summary
    assert any(table.name == "identifier_inventory" for table in result.tables)


def test_analyze_returns_high_cardinality_inventory() -> None:
    dataframe = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3", "T4"],
            "created_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            "priority": ["Low", "Medium", "High", "Medium"],
            "resolution_hours": [4.2, 6.1, 3.4, 8.0],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Which columns have many unique values?")

    assert result.response["interpretation"]["intent_name"] == "high_cardinality_inventory"
    assert "High-cardinality columns:" in result.summary
    assert any(table.name == "high_cardinality_inventory" for table in result.tables)


def test_analyze_returns_time_coverage_years() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2024-01-01", "2025-02-01", "2026-03-01", "bad-date"],
            "revenue": [90.0, 100.0, 120.0, 130.0],
            "segment": ["Retail", "Retail", "Online", "Online"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "The data shows revenue for which years?")

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

    result = PromptAnalysisFrontend().analyze(dataset, "What date range does the sales data cover?")

    assert "The data covers 2026-01-09 to 2026-04-11." in result.summary
    assert any(table.name == "time_coverage" for table in result.tables)


def test_analyze_returns_time_bucket_counts_by_year() -> None:
    dataframe = pd.DataFrame(
        {
            "created_at": [
                "2024-01-01",
                "2025-01-02",
                "2025-02-03",
                "2026-03-04",
                "bad-date",
            ],
            "team": ["Support", "Support", "Platform", "Platform", "Support"],
            "resolution_hours": [4.2, 6.0, 3.1, 8.4, 5.0],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "I need a list of years, and how many tickets created in those years.")

    assert "Ticket counts by year: 2024 = 1; 2025 = 2; 2026 = 1." in result.summary
    assert result.response["interpretation"]["intent_name"] == "time_bucket_counts"
    assert result.response["interpretation"]["options"]["time_bucket"] == "year"
    assert any(table.name == "time_bucket_counts" for table in result.tables)


def test_analyze_returns_time_bucket_counts_by_quarter() -> None:
    dataframe = pd.DataFrame(
        {
            "created_at": [
                "2025-01-01",
                "2025-02-03",
                "2025-07-04",
                "2026-01-02",
                "2026-05-06",
            ],
            "team": ["Support", "Support", "Platform", "Platform", "Support"],
            "resolution_hours": [4.2, 6.0, 3.1, 8.4, 5.0],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "How many tickets were created by quarter?")

    assert "Ticket counts by quarter:" in result.summary
    assert result.response["interpretation"]["intent_name"] == "time_bucket_counts"
    assert result.response["interpretation"]["options"]["time_bucket"] == "quarter"
    assert any(table.name == "time_bucket_counts" for table in result.tables)


def test_analyze_returns_time_bucket_breakdown_by_month() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-01-01", "2026-01-15", "2026-02-01", "2026-03-01"],
            "revenue": [100.0, 80.0, 60.0, 40.0],
            "region": ["West", "East", "West", "East"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Show revenue by month")

    assert "Revenue by month:" in result.summary
    assert result.response["interpretation"]["intent_name"] == "time_bucket_breakdown"
    assert result.response["interpretation"]["options"]["time_bucket"] == "month"
    assert any(table.name == "time_bucket_breakdown" for table in result.tables)


def test_analyze_returns_time_bucket_breakdown_by_quarter() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": [
                "2025-01-01",
                "2025-04-01",
                "2025-07-01",
                "2025-10-01",
                "2026-01-01",
                "2026-04-01",
            ],
            "revenue": [100.0, 120.0, 140.0, 160.0, 180.0, 200.0],
            "region": ["West", "East", "West", "East", "West", "East"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Show revenue by quarter")

    assert "Revenue by quarter:" in result.summary
    assert result.response["interpretation"]["options"]["time_bucket"] == "quarter"
    assert any(table.name == "time_bucket_breakdown" for table in result.tables)


def test_analyze_supports_time_period_comparison_by_quarter() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": [
                "2025-01-01",
                "2025-04-01",
                "2025-07-01",
                "2025-10-01",
                "2026-01-01",
                "2026-04-01",
                "2026-07-01",
                "2026-10-01",
            ],
            "revenue": [100.0, 120.0, 140.0, 160.0, 180.0, 200.0, 220.0, 240.0],
            "region": ["West", "East", "West", "East", "West", "East", "West", "East"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Compare revenue this quarter to last quarter")

    assert "Revenue moved from 220.00 in 2026-Q3 to 240.00 in 2026-Q4" in result.summary
    assert result.response["interpretation"]["intent_name"] == "time_period_comparison"
    assert result.response["interpretation"]["options"]["time_bucket"] == "quarter"
    assert any(table.name == "period_comparison" for table in result.tables)


def test_analyze_supports_time_period_comparison_by_year() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": [
                "2025-01-01",
                "2025-04-01",
                "2025-07-01",
                "2025-10-01",
                "2026-01-01",
                "2026-04-01",
                "2026-07-01",
                "2026-10-01",
            ],
            "revenue": [100.0, 120.0, 140.0, 160.0, 180.0, 200.0, 220.0, 240.0],
            "region": ["West", "East", "West", "East", "West", "East", "West", "East"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Compare revenue this year to last year")

    assert "Revenue moved from 520.00 in 2025 to 840.00 in 2026" in result.summary
    assert result.response["interpretation"]["intent_name"] == "time_period_comparison"
    assert result.response["interpretation"]["options"]["time_bucket"] == "year"
    assert any(table.name == "period_comparison" for table in result.tables)


def test_analyze_returns_yes_for_time_value_existence_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "created_at": ["2025-01-01", "2025-01-02", "2025-03-04"],
            "team": ["Support", "Support", "Platform"],
            "resolution_hours": [4.2, 6.0, 3.1],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "The created_at column shows dates in 2025?")

    assert "Yes, created_at contains dates in 2025" in result.summary
    assert result.response["interpretation"]["intent_name"] == "existence_check"
    assert result.response["interpretation"]["options"]["existence_mode"] == "time_value"
    assert any(table.name == "time_value_exists" for table in result.tables)


def test_analyze_returns_no_for_filtered_row_existence_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "revenue": [100.0, 120.0, 90.0],
            "region": ["West", "West", "East"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Is North in the region column?")

    assert "No, the dataset does not contain rows matching region=North." in result.summary
    assert result.response["interpretation"]["intent_name"] == "existence_check"
    assert result.response["interpretation"]["options"]["existence_mode"] == "filtered_rows"
    assert any(table.name == "row_existence" for table in result.tables)


def test_analyze_returns_yes_for_missing_value_verification_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3", "T4"],
            "csat_score": [4.8, None, 4.1, 3.9],
            "priority": ["Low", "Medium", "High", "Medium"],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Does csat_score have missing values?")

    assert "Yes, csat_score has missing values" in result.summary
    assert result.response["interpretation"]["options"]["existence_mode"] == "null_check"
    assert any(table.name == "null_check" for table in result.tables)


def test_analyze_returns_no_for_incomplete_column_check() -> None:
    dataframe = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3", "T4"],
            "csat_score": [4.8, None, 4.1, 3.9],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Is csat_score complete?")

    assert "No, csat_score is not complete" in result.summary
    assert result.response["interpretation"]["options"]["existence_mode"] == "null_check"
    assert any(table.name == "null_check" for table in result.tables)


def test_analyze_returns_yes_for_threshold_verification_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "resolution_hours": [4.0, 21.5, 19.0],
            "team": ["Support", "Platform", "Support"],
        }
    )
    dataset = Dataset(name="tickets", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Are any resolution hours above 20?")

    assert "Yes, resolution_hours contains values above 20.00" in result.summary
    assert result.response["interpretation"]["options"]["existence_mode"] == "threshold_check"
    assert any(table.name == "threshold_check" for table in result.tables)


def test_analyze_returns_yes_for_numeric_property_check() -> None:
    dataframe = pd.DataFrame(
        {
            "revenue": [100.0, 120.0],
            "region": ["West", "East"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Is revenue numeric?")

    assert "Yes, revenue is a numeric column." in result.summary
    assert result.response["interpretation"]["options"]["existence_mode"] == "column_property_check"
    assert any(table.name == "column_property_check" for table in result.tables)


def test_analyze_returns_yes_for_datetime_property_check() -> None:
    dataframe = pd.DataFrame(
        {
            "created_at": ["2026-01-01", "2026-01-02"],
            "priority": ["Low", "High"],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Is created_at a datetime field?")

    assert "Yes, created_at is a datetime column." in result.summary
    assert result.response["interpretation"]["options"]["existence_mode"] == "column_property_check"
    assert any(table.name == "column_property_check" for table in result.tables)


def test_analyze_returns_yes_for_identifier_property_check() -> None:
    dataframe = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3", "T4"],
            "priority": ["Low", "Medium", "High", "Medium"],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Is ticket_id likely an identifier?")

    assert "Yes, ticket_id is likely an identifier." in result.summary
    assert result.response["interpretation"]["options"]["existence_mode"] == "column_property_check"
    assert any(table.name == "column_property_check" for table in result.tables)


def test_analyze_returns_yes_for_dimension_property_check() -> None:
    dataframe = pd.DataFrame(
        {
            "revenue": [100.0, 120.0],
            "region": ["West", "East"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Is region a dimension?")

    assert "Yes, region is a dimension column." in result.summary
    assert result.response["interpretation"]["options"]["existence_mode"] == "column_property_check"
    assert result.response["interpretation"]["options"]["expected_property"] == "dimension"
    assert any(table.name == "column_property_check" for table in result.tables)


def test_analyze_returns_no_for_missing_dimension_property_check() -> None:
    dataframe = pd.DataFrame(
        {
            "created_at": ["2026-01-01", "2026-01-02"],
            "priority": ["Low", "High"],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Is region a dimension?")

    assert "No, the dataset does not contain a column named region." in result.summary
    assert result.response["interpretation"]["options"]["existence_mode"] == "column_property_check"
    assert result.response["interpretation"]["options"]["expected_property"] == "dimension"
    assert any(table.name == "column_property_check" for table in result.tables)


def test_analyze_returns_yes_for_measure_property_check() -> None:
    dataframe = pd.DataFrame(
        {
            "revenue": [100.0, 120.0],
            "region": ["West", "East"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Is revenue a measure?")

    assert "Yes, revenue is a measure column." in result.summary
    assert result.response["interpretation"]["options"]["existence_mode"] == "column_property_check"
    assert result.response["interpretation"]["options"]["expected_property"] == "measure"
    assert any(table.name == "column_property_check" for table in result.tables)


def test_analyze_returns_yes_for_column_presence_check() -> None:
    dataframe = pd.DataFrame(
        {
            "created_at": ["2026-01-01", "2026-01-02"],
            "priority": ["Low", "High"],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Does the dataset have a created_at column?")

    assert "Yes, the dataset contains the created_at column." in result.summary
    assert result.response["interpretation"]["options"]["existence_mode"] == "column_presence_check"
    assert result.response["interpretation"]["options"]["requested_column"] == "created_at"
    assert any(table.name == "column_presence_check" for table in result.tables)


def test_analyze_returns_no_for_missing_column_presence_check() -> None:
    dataframe = pd.DataFrame(
        {
            "created_at": ["2026-01-01", "2026-01-02"],
            "priority": ["Low", "High"],
        }
    )
    dataset = Dataset(name="support", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Does the dataset have a ticket_id column?")

    assert "No, the dataset does not contain a column named ticket_id." in result.summary
    assert result.response["interpretation"]["options"]["existence_mode"] == "column_presence_check"
    assert result.response["interpretation"]["options"]["requested_column"] == "ticket_id"
    assert any(table.name == "column_presence_check" for table in result.tables)


def test_analyze_returns_yes_for_column_presence_check_when_field_name_contains_total_keyword() -> None:
    dataframe = pd.DataFrame(
        {
            "total_sales": [120.0, 85.0],
            "country": ["Australia", "Japan"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Does the dataset contain a total_sales column?")

    assert "Yes, the dataset contains the total_sales column." in result.summary
    assert result.response["interpretation"]["options"]["existence_mode"] == "column_presence_check"
    assert result.response["interpretation"]["options"]["requested_column"] == "total_sales"
    assert result.response["result"]["name"] == "column_presence_check"


def test_analyze_returns_no_for_high_cardinality_property_check() -> None:
    dataframe = pd.DataFrame(
        {
            "region": ["West", "West", "East", "East"],
            "revenue": [100.0, 120.0, 90.0, 80.0],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Is region high cardinality?")

    assert "No, region is not high cardinality" in result.summary
    assert result.response["interpretation"]["options"]["existence_mode"] == "column_property_check"
    assert result.response["interpretation"]["options"]["expected_property"] == "high_cardinality"
    assert any(table.name == "column_property_check" for table in result.tables)


def test_analyze_supports_p_value_driven_inference_workflow() -> None:
    dataframe = pd.DataFrame(
        {
            "region": ["North"] * 6 + ["South"] * 6,
            "revenue": [100, 104, 98, 102, 101, 99, 135, 138, 132, 140, 136, 134],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Is revenue by region statistically significant?")

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

    result = PromptAnalysisFrontend().analyze(dataset, "Do regions differ in revenue?")

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

    result = PromptAnalysisFrontend().analyze(dataset, "What range are we 95% confident revenue falls in?")

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

    result = PromptAnalysisFrontend().analyze(dataset, "Do we have enough data to detect a difference in revenue by region?")

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

    result = PromptAnalysisFrontend().analyze(dataset, "How many rows per group do we need for revenue by region?")

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

    result = PromptAnalysisFrontend().analyze(dataset, "Does resolution_hours significantly affect csat_score?")

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

    result = PromptAnalysisFrontend().analyze(dataset, "What is the top 5 longest hours of resolution?")

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

    result = PromptAnalysisFrontend().analyze(dataset, "Show bottom 2 revenue by region")

    assert result.response["interpretation"]["intent_name"] == "group_ranking"
    assert "Bottom 2 revenue groups" in result.summary
    assert any(table.name == "ranked_breakdown" for table in result.tables)


def test_analyze_supports_grouped_entity_count_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "channel": ["Email", "Phone", "Email", "Chat"],
            "priority": ["High", "High", "Low", "Low"],
        }
    )
    dataset = Dataset(name="tickets", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Give me a list of total tickets per channel.")

    assert result.response["interpretation"]["intent_name"] == "grouped_tabular_query"
    assert result.response["interpretation"]["options"]["intent_name"] == "grouped_tabular_query"
    assert result.response["interpretation"]["target"] is None
    assert result.response["interpretation"]["aggregation"] == "count"
    assert result.response["interpretation"]["prompt_contract"]["status"] == "supported_and_data_feasible"
    assert any(table.name == "grouped_tabular_query" for table in result.tables)


def test_analyze_rejects_dimension_mean_prompt_instead_of_falling_back() -> None:
    dataframe = pd.DataFrame(
        {
            "revenue": [120.0, 80.0],
            "region": ["West", "East"],
            "posted_at": ["2026-02-01", "2026-03-01"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    with pytest.raises(Exception):
        PromptAnalysisFrontend().analyze(dataset, "What is the average region?")


def test_analyze_rejects_time_max_prompt_instead_of_falling_back() -> None:
    dataframe = pd.DataFrame(
        {
            "revenue": [120.0, 80.0],
            "region": ["West", "East"],
            "posted_at": ["2026-02-01", "2026-03-01"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    with pytest.raises(Exception):
        PromptAnalysisFrontend().analyze(dataset, "What is the highest posted_at?")


def test_analyze_time_coverage_rejects_datasets_without_time_columns() -> None:
    dataframe = pd.DataFrame({"revenue": [90.0, 100.0], "segment": ["Retail", "Online"]})
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    with pytest.raises(Exception):
        PromptAnalysisFrontend().analyze(dataset, "Which years are present in the sales data?")


def test_analyze_supports_sql_adapter_input(tmp_path: Path) -> None:
    database_path = tmp_path / "sales.db"
    connection = sqlite3.connect(database_path)
    connection.execute("create table sales (posted_at text, revenue integer, region text)")
    connection.execute("insert into sales values ('2026-02-01', 120, 'West')")
    connection.execute("insert into sales values ('2026-03-01', 80, 'East')")
    connection.commit()
    connection.close()

    dataset = SQLAdapter(database_path, "select posted_at, revenue, region from sales").load()
    result = PromptAnalysisFrontend().analyze(dataset, "Why did revenue drop in March?")

    assert result.summary
    assert any(metric.name == "revenue_sum" for metric in result.metrics)


def test_analyze_supports_quarter_prompt_now() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-01-01", "2026-02-01", "2026-03-01"],
            "revenue": [100, 110, 120],
            "region": ["West", "West", "East"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Compare revenue this quarter to last quarter")

    assert result.response["interpretation"]["intent_name"] == "time_period_comparison"


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


def test_analyze_returns_filtered_row_table_for_reopened_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3", "T4"],
            "created_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            "priority": ["Low", "Medium", "High", "Medium"],
            "team": ["Support", "Support", "Platform", "Platform"],
            "reopened_flag": ["yes", "no", "yes", "no"],
        }
    )
    dataset = Dataset(name="tickets", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Give me the list of all rows in dataset that have their tickets marked as reopened.")

    table = next(table for table in result.tables if table.name == "tabular_query")
    assert result.response["interpretation"]["intent_name"] == "tabular_query"
    assert result.response["result"]["logical_shape"] == "recordset"
    assert result.response["result"]["metadata"]["pagination"]["total_rows"] == 2
    assert len(table.dataframe) == 2
    assert set(table.dataframe["reopened_flag"]) == {"yes"}


def test_analyze_returns_selected_columns_for_tabular_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3"],
            "created_at": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "priority": ["Low", "Medium", "High"],
            "reopened_flag": ["yes", "no", "yes"],
        }
    )
    dataset = Dataset(name="tickets", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Show ticket_id and priority rows sorted by created_at")

    table = next(table for table in result.tables if table.name == "tabular_query")
    assert list(table.dataframe.columns) == ["ticket_id", "priority", "created_at"]
    response_table = next(table_entry for table_entry in result.response["tables"] if table_entry["name"] == "tabular_query")
    assert response_table["result"]["pagination"]["total_rows"] == 3


def test_analyze_returns_grouped_tabular_query_for_table_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "posted_at": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "revenue": [100.0, 80.0, 60.0],
            "region": ["West", "East", "West"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Show revenue by region as table")

    table = next(table for table in result.tables if table.name == "grouped_tabular_query")
    assert result.response["interpretation"]["intent_name"] == "grouped_tabular_query"
    assert result.response["result"]["logical_shape"] == "table"
    assert "target_total" in table.dataframe.columns


def test_analyze_returns_paginated_tabular_query() -> None:
    dataframe = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3", "T4"],
            "created_at": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
            "priority": ["Low", "Medium", "High", "Medium"],
        }
    )
    dataset = Dataset(name="tickets", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Return first 3 rows page 2 page size 2 sorted by created_at")

    table = next(table for table in result.tables if table.name == "tabular_query")
    assert list(table.dataframe["ticket_id"]) == ["T3"]
    assert result.response["result"]["metadata"]["pagination"]["page"] == 2
    assert result.response["result"]["metadata"]["pagination"]["total_rows"] == 3


def test_analyze_returns_latest_five_rows_as_limited_recordset() -> None:
    dataframe = pd.DataFrame(
        {
            "order_id": [f"ORD-{index:03d}" for index in range(1, 9)],
            "order_date": [
                "2026-01-01",
                "2026-01-02",
                "2026-01-03",
                "2026-01-04",
                "2026-01-05",
                "2026-01-06",
                "2026-01-07",
                "2026-01-08",
            ],
            "country": ["A", "B", "C", "D", "E", "F", "G", "H"],
            "total_sales": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Show the latest 5 rows.")

    table = next(table for table in result.tables if table.name == "tabular_query")
    assert result.response["interpretation"]["intent_name"] == "tabular_query"
    assert list(table.dataframe["order_id"]) == ["ORD-008", "ORD-007", "ORD-006", "ORD-005", "ORD-004"]
    assert len(table.dataframe) == 5
    assert result.response["result"]["metadata"]["pagination"]["total_rows"] == 5
    assert list(table.dataframe.columns) == ["order_id", "order_date", "country", "total_sales"]


def test_analyze_counts_rows_for_numeric_threshold_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "order_id": [f"ORD-{index:03d}" for index in range(1, 9)],
            "total_sales": [10.0, 20.0, 30.0, 40.0, 410.0, 460.0, 500.0, 80.0],
            "country": ["A", "B", "C", "D", "E", "F", "G", "H"],
        }
    )
    dataset = Dataset(name="sales", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "How many rows have total_sales greater than 400?")

    assert result.response["interpretation"]["intent_name"] == "row_count"
    assert result.response["interpretation"]["filters"] == {"total_sales": {"op": "gt", "value": 400.0}}
    assert result.response["result"]["value"] == 3


def _build_recurring_time_filter_dataset() -> Dataset:
    dataframe = pd.DataFrame(
        {
            "ticket_id": [f"T{index}" for index in range(1, 17)],
            "created_at": [
                "2026-01-01",
                "2026-01-03",
                "2026-01-05",
                "2026-01-15",
                "2026-01-30",
                "2026-01-31",
                "2026-02-01",
                "2026-02-02",
                "2026-02-15",
                "2026-02-27",
                "2026-02-28",
                "2026-03-01",
                "2026-03-02",
                "2026-03-15",
                "2026-03-27",
                "2026-03-31",
            ],
            "priority": [
                "Low",
                "Low",
                "Medium",
                "High",
                "Medium",
                "Low",
                "Low",
                "Medium",
                "High",
                "Medium",
                "Low",
                "Low",
                "Medium",
                "High",
                "Medium",
                "Low",
            ],
        }
    )
    return Dataset(name="tickets", source_type="pandas", data=dataframe)


def _build_recent_window_dataset() -> Dataset:
    dataframe = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3", "T4"],
            "created_at": ["2026-03-01", "2026-03-31", "2026-04-24", "2026-04-30"],
            "priority": ["Low", "Medium", "High", "Low"],
        }
    )
    return Dataset(name="tickets", source_type="pandas", data=dataframe)


@pytest.mark.parametrize(
    ("question", "expected_total_rows"),
    [
        ("List all rows on the 15th day of every month", 3),
        ("List all rows on Mondays", 3),
        ("List all rows on weekdays", 9),
        ("List all rows on the first day of every month", 3),
        ("List all rows on the last day of every month", 3),
        ("List all rows on the first Monday of every month", 3),
        ("List all rows on the last Friday of every month", 3),
        ("List all rows for Q1", 16),
        ("Show all tickets created on the 1st of each month", 3),
    ],
)
def test_analyze_supports_extended_recurring_time_filters(
    question: str,
    expected_total_rows: int,
) -> None:
    dataset = _build_recurring_time_filter_dataset()

    result = PromptAnalysisFrontend().analyze(dataset, question)

    table = next(table for table in result.tables if table.name == "tabular_query")
    assert result.response["status"] == "ok"
    assert result.response["interpretation"]["intent_name"] == "tabular_query"
    assert result.response["interpretation"]["prompt_family"] == "tabular_record_retrieval"
    assert result.response["result"]["metadata"]["pagination"]["total_rows"] == expected_total_rows
    assert len(table.dataframe) == expected_total_rows


def test_analyze_supports_recent_window_time_filter() -> None:
    dataset = _build_recent_window_dataset()

    result = PromptAnalysisFrontend().analyze(dataset, "List all rows from the last 7 days")

    table = next(table for table in result.tables if table.name == "tabular_query")
    assert result.response["status"] == "ok"
    assert result.response["interpretation"]["intent_name"] == "tabular_query"
    assert result.response["interpretation"]["prompt_family"] == "tabular_record_retrieval"
    assert result.response["result"]["metadata"]["pagination"]["total_rows"] == 2
    assert list(table.dataframe["ticket_id"]) == ["T3", "T4"]


@pytest.mark.parametrize(
    "question",
    [
        "How many rows are in Q1?",
        "Count rows for quarter 1",
        "What is the row count for the first quarter?",
    ],
)
def test_analyze_supports_row_count_for_quarter_filtered_prompt(question: str) -> None:
    dataset = _build_recurring_time_filter_dataset()

    result = PromptAnalysisFrontend().analyze(dataset, question)

    assert result.response["status"] == "ok"
    assert result.response["interpretation"]["intent_name"] == "row_count"
    assert result.response["interpretation"]["prompt_family"] == "row_count"
    assert result.response["interpretation"]["filters"] == {"created_at": {"op": "quarter_eq", "value": 1, "label": "q1"}}
    assert result.response["result"]["name"] == "row_count"
    assert result.response["result"]["value"] == 16


def test_analyze_keeps_distinct_values_for_dimension_listing_prompt() -> None:
    dataframe = pd.DataFrame(
        {
            "priority": ["Low", "Medium", "High", "Medium"],
            "reopened_flag": ["yes", "no", "yes", "no"],
        }
    )
    dataset = Dataset(name="tickets", source_type="pandas", data=dataframe)

    result = PromptAnalysisFrontend().analyze(dataset, "Give me a list of all priority values")

    assert result.response["interpretation"]["intent_name"] == "distinct_values"
    assert any(table.name == "distinct_values" for table in result.tables)


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

    result = PromptAnalysisFrontend().analyze(dataset, question)

    assert result.plan.task_type == "diagnostic"
    assert any(table.name == "period_comparison" for table in result.tables)
    assert result.artifacts["profile"]["dataset_name"] == f"sales_{case_id}"


