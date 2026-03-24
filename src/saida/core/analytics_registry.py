"""Canonical analytics family and method registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AnalyticsAvailability = Literal["implemented", "partial", "planned"]


@dataclass(slots=True)
class AnalyticsMethodSpec:
    """Describe one canonical analytics method."""

    method_id: str
    family_id: str
    label: str
    description: str
    required_inputs: tuple[str, ...] = ()
    allowed_configs: tuple[str, ...] = ()
    output_shapes: tuple[str, ...] = ()
    dependency_rules: tuple[str, ...] = ()
    default_tool_family: str | None = None
    availability: AnalyticsAvailability = "implemented"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "family_id": self.family_id,
            "label": self.label,
            "description": self.description,
            "required_inputs": list(self.required_inputs),
            "allowed_configs": list(self.allowed_configs),
            "output_shapes": list(self.output_shapes),
            "dependency_rules": list(self.dependency_rules),
            "default_tool_family": self.default_tool_family,
            "availability": self.availability,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class AnalyticsFamilySpec:
    """Describe one analytics family grouping."""

    family_id: str
    label: str
    description: str
    availability: AnalyticsAvailability = "implemented"
    method_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "family_id": self.family_id,
            "label": self.label,
            "description": self.description,
            "availability": self.availability,
            "method_ids": list(self.method_ids),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class AnalyticsRegistry:
    """Registry of canonical analytics families and methods."""

    families: dict[str, AnalyticsFamilySpec] = field(default_factory=dict)
    methods: dict[str, AnalyticsMethodSpec] = field(default_factory=dict)

    def add_family(self, family: AnalyticsFamilySpec) -> None:
        self.families[family.family_id] = family

    def add_method(self, method: AnalyticsMethodSpec) -> None:
        family = self.families.get(method.family_id)
        if family is None:
            raise ValueError(f"Unknown analytics family for method {method.method_id!r}: {method.family_id!r}")
        self.methods[method.method_id] = method
        if method.method_id not in family.method_ids:
            family.method_ids.append(method.method_id)

    def get_family(self, family_id: str | None) -> AnalyticsFamilySpec | None:
        if family_id is None:
            return None
        return self.families.get(family_id)

    def get_method(self, method_id: str | None) -> AnalyticsMethodSpec | None:
        if method_id is None:
            return None
        return self.methods.get(method_id)

    def methods_for_family(self, family_id: str) -> list[AnalyticsMethodSpec]:
        family = self.get_family(family_id)
        if family is None:
            return []
        return [self.methods[method_id] for method_id in family.method_ids if method_id in self.methods]

    def family_for_method(self, method_id: str | None) -> str | None:
        method = self.get_method(method_id)
        return method.family_id if method is not None else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "families": {family_id: family.to_dict() for family_id, family in self.families.items()},
            "methods": {method_id: method.to_dict() for method_id, method in self.methods.items()},
        }


def build_default_analytics_registry() -> AnalyticsRegistry:
    """Build the live analytics family and method registry."""

    registry = AnalyticsRegistry()

    for family in [
        AnalyticsFamilySpec("selection_filtering", "Selection / Filtering", "Dataset subset selection and row scoping.", availability="planned"),
        AnalyticsFamilySpec("projection_field_selection", "Projection / Field Selection", "Row retrieval with explicit field selection."),
        AnalyticsFamilySpec("transformation", "Transformation", "Value or schema transformation workflows.", availability="planned"),
        AnalyticsFamilySpec("joining", "Joining", "Join-based analytical workflows across datasets.", availability="planned"),
        AnalyticsFamilySpec("aggregation_grouping", "Aggregation / Grouping", "Counts, aggregates, grouped tables, and grouped metric summaries."),
        AnalyticsFamilySpec("ranking", "Ranking", "Top-N, bottom-N, and ordered leaderboard workflows."),
        AnalyticsFamilySpec("validation_verification", "Validation / Verification", "Verification checks against rows, columns, thresholds, and time values."),
        AnalyticsFamilySpec("schema_metadata_inspection", "Schema / Metadata Inspection", "Schema inventories and dataset profile inspection."),
        AnalyticsFamilySpec("distinct_cardinality_analysis", "Distinct / Cardinality Analysis", "Distinct listings and distinct cardinality workflows."),
        AnalyticsFamilySpec("time_series_time_bucketing", "Time-Series / Time Bucketing", "Time coverage, bucketing, and time trend workflows."),
        AnalyticsFamilySpec("period_comparison", "Period Comparison", "Period-over-period comparison and contribution workflows."),
        AnalyticsFamilySpec("statistical_inference", "Statistical Inference", "Inferential and significance workflows."),
        AnalyticsFamilySpec("diagnostic_workflows", "Diagnostic Workflows", "Exploratory summaries, anomaly scans, and correlation diagnostics."),
        AnalyticsFamilySpec("predictive_forecasting", "Predictive / Forecasting", "Forecasting workflows.", availability="partial"),
        AnalyticsFamilySpec("output_preparation", "Output Preparation", "Output shaping and delivery workflows.", availability="planned"),
    ]:
        registry.add_family(family)

    _register_methods(
        registry,
        "projection_field_selection",
        (
            ("tabular_query", "Tabular Query", "Return filtered rows with optional selected columns and pagination.", ("dataset",), ("selected_columns", "filters", "sort_by", "sort_direction", "limit", "page", "page_size"), ("recordset",), "duckdb"),
        ),
    )
    _register_methods(
        registry,
        "aggregation_grouping",
        (
            ("row_count", "Row Count", "Count rows in the dataset or a filtered slice.", ("dataset",), ("filters",), ("scalar",), "duckdb"),
            ("count_rows_by_group", "Grouped Row Count", "Count rows by grouping dimensions.", ("dataset", "group_by"), ("filters", "ascending", "limit"), ("table",), "duckdb"),
            ("aggregate_value", "Aggregate Value", "Aggregate a target metric to a scalar value.", ("dataset", "target", "aggregation"), ("filters",), ("scalar",), "duckdb"),
            ("group_breakdown", "Group Breakdown", "Aggregate a metric by grouping dimensions.", ("dataset", "target", "group_by"), ("aggregation", "filters"), ("table",), "duckdb"),
            ("grouped_tabular_query", "Grouped Tabular Query", "Return grouped aggregated tables with sorting and pagination.", ("dataset", "group_by"), ("target", "aggregation", "filters", "sort_by", "sort_direction", "limit", "page", "page_size"), ("table",), "duckdb"),
        ),
    )
    _register_methods(
        registry,
        "ranking",
        (
            ("ranked_rows", "Ranked Rows", "Rank individual rows by a metric.", ("dataset", "target"), ("filters", "ascending", "limit"), ("table",), "duckdb"),
            ("ranked_breakdown", "Ranked Breakdown", "Rank grouped metric aggregates.", ("dataset", "target", "group_by"), ("aggregation", "filters", "ascending", "limit"), ("table",), "duckdb"),
        ),
    )
    _register_methods(
        registry,
        "validation_verification",
        (
            ("row_existence", "Row Existence", "Verify whether any rows satisfy the requested filters.", ("dataset",), ("filters",), ("verification",), "duckdb"),
            ("time_value_exists", "Time Value Exists", "Verify whether a time value exists in the dataset.", ("dataset", "time_column"), ("expected_year", "time_reference", "filters"), ("verification",), "duckdb"),
            ("null_check", "Null Check", "Verify null expectations for a target column.", ("dataset", "target"), ("null_expectation", "filters"), ("verification",), "duckdb"),
            ("threshold_check", "Threshold Check", "Verify a threshold condition for a target metric.", ("dataset", "target"), ("threshold_operator", "threshold_value", "lower_bound", "upper_bound", "filters"), ("verification",), "duckdb"),
            ("column_property_check", "Column Property Check", "Verify whether a column matches a schema property.", ("dataset", "target"), ("expected_property",), ("verification",), "metadata"),
            ("column_presence_check", "Column Presence Check", "Verify whether a requested column exists in the schema.", ("dataset",), ("requested_column",), ("verification",), "metadata"),
        ),
    )
    _register_methods(
        registry,
        "schema_metadata_inspection",
        (
            ("column_count", "Column Count", "Count dataset columns.", ("dataset",), (), ("scalar",), "metadata"),
            ("column_inventory", "Column Inventory", "List dataset columns.", ("dataset",), (), ("table",), "metadata"),
            ("column_type_inventory", "Column Type Inventory", "List schema types and roles.", ("dataset",), ("target",), ("table",), "metadata"),
            ("numeric_column_inventory", "Numeric Column Inventory", "List numeric columns.", ("dataset",), (), ("table",), "metadata"),
            ("numeric_column_count", "Numeric Column Count", "Count numeric columns.", ("dataset",), (), ("scalar",), "metadata"),
            ("categorical_column_inventory", "Categorical Column Inventory", "List categorical columns.", ("dataset",), (), ("table",), "metadata"),
            ("categorical_column_count", "Categorical Column Count", "Count categorical columns.", ("dataset",), (), ("scalar",), "metadata"),
            ("measure_inventory", "Measure Inventory", "List measure columns.", ("dataset",), (), ("table",), "metadata"),
            ("measure_count", "Measure Count", "Count measure columns.", ("dataset",), (), ("scalar",), "metadata"),
            ("dimension_inventory", "Dimension Inventory", "List dimension columns.", ("dataset",), (), ("table",), "metadata"),
            ("dimension_count", "Dimension Count", "Count dimension columns.", ("dataset",), (), ("scalar",), "metadata"),
            ("time_column_inventory", "Time Column Inventory", "List detected time columns.", ("dataset",), (), ("table",), "metadata"),
            ("time_column_count", "Time Column Count", "Count detected time columns.", ("dataset",), (), ("scalar",), "metadata"),
            ("missing_value_inventory", "Missing Value Inventory", "List columns with missing values.", ("dataset",), (), ("table",), "metadata"),
            ("identifier_inventory", "Identifier Inventory", "List identifier-like columns.", ("dataset",), (), ("table",), "metadata"),
            ("identifier_count", "Identifier Count", "Count identifier-like columns.", ("dataset",), (), ("scalar",), "metadata"),
            ("high_cardinality_inventory", "High Cardinality Inventory", "List high-cardinality columns.", ("dataset",), (), ("table",), "metadata"),
            ("high_cardinality_count", "High Cardinality Count", "Count high-cardinality columns.", ("dataset",), (), ("scalar",), "metadata"),
        ),
    )
    _register_methods(
        registry,
        "distinct_cardinality_analysis",
        (
            ("distinct_values", "Distinct Values", "List distinct values for a dimension column.", ("dataset", "target"), ("filters",), ("table",), "duckdb"),
            ("distinct_value_count", "Distinct Value Count", "Count distinct values for a dimension column.", ("dataset", "target"), ("filters",), ("scalar",), "duckdb"),
        ),
    )
    _register_methods(
        registry,
        "time_series_time_bucketing",
        (
            ("time_coverage", "Time Coverage", "Describe the time coverage of a time field.", ("dataset", "time_column"), ("mode", "filters"), ("table",), "duckdb"),
            ("time_bucket_counts", "Time Bucket Counts", "Count rows by time bucket.", ("dataset", "time_column"), ("bucket", "filters"), ("table",), "duckdb"),
            ("time_bucket_breakdown", "Time Bucket Breakdown", "Aggregate a target metric across time buckets.", ("dataset", "target", "time_column"), ("bucket", "aggregation", "group_by", "filters"), ("table",), "duckdb"),
            ("time_trend", "Time Trend", "Aggregate a target metric over time.", ("dataset", "target", "time_column"), ("aggregation", "filters"), ("timeseries",), "duckdb"),
        ),
    )
    _register_methods(
        registry,
        "period_comparison",
        (
            ("period_comparison", "Period Comparison", "Compare a metric across adjacent time periods.", ("dataset", "target", "time_column", "time_reference"), ("bucket", "aggregation", "filters"), ("timeseries",), "duckdb"),
            ("grouped_period_comparison", "Grouped Period Comparison", "Compare grouped metric totals across periods.", ("dataset", "target", "group_by", "time_column", "time_reference"), ("bucket", "aggregation", "filters"), ("timeseries",), "duckdb"),
            ("top_movers", "Top Movers", "Identify the largest period-over-period movers.", ("dataset", "target", "group_by", "time_column", "time_reference"), ("aggregation", "filters", "limit"), ("table",), "duckdb"),
            ("contribution_breakdown", "Contribution Breakdown", "Estimate grouped contribution to changes over time.", ("dataset", "target", "group_by"), ("time_column", "time_reference", "aggregation", "filters"), ("table",), "duckdb"),
        ),
    )
    _register_methods(
        registry,
        "statistical_inference",
        (
            ("significance_inference", "Significance Inference", "Run a significance test over a metric and grouping column.", ("dataset", "target", "group_by"), ("alpha",), ("statistical_test",), "stats"),
            ("t_test", "T-Test", "Run a t-test over a metric and grouping column.", ("dataset", "target", "group_by"), ("alpha",), ("statistical_test",), "stats"),
            ("chi_square", "Chi-Square", "Run a chi-square test between categorical columns.", ("dataset",), ("comparison_columns", "alpha"), ("statistical_test",), "stats"),
            ("anova", "ANOVA", "Run an ANOVA test over a metric and grouping column.", ("dataset", "target", "group_by"), ("alpha",), ("statistical_test",), "stats"),
            ("mann_whitney", "Mann-Whitney", "Run a Mann-Whitney test over a metric and grouping column.", ("dataset", "target", "group_by"), ("alpha",), ("statistical_test",), "stats"),
            ("confidence_interval", "Confidence Interval", "Compute a confidence interval for a metric.", ("dataset", "target"), ("confidence_level",), ("statistical_test",), "stats"),
            ("regression_significance", "Regression Significance", "Run regression significance against a target and feature columns.", ("dataset", "target"), ("feature_columns", "alpha"), ("statistical_test",), "stats"),
            ("power_analysis", "Power Analysis", "Estimate observed power for a grouped comparison.", ("dataset", "target", "group_by"), ("alpha",), ("statistical_test",), "stats"),
            ("sample_size_estimate", "Sample Size Estimate", "Estimate required sample size for a grouped comparison.", ("dataset", "target", "group_by"), ("alpha", "desired_power"), ("statistical_test",), "stats"),
        ),
    )
    _register_methods(
        registry,
        "diagnostic_workflows",
        (
            ("dataset_summary", "Dataset Summary", "Summarize a metric and related baseline tables.", ("dataset",), ("target", "filters"), ("table", "scalar"), "duckdb"),
            ("missingness_summary", "Missingness Summary", "Summarize dataset missingness.", ("dataset",), (), ("table",), "stats"),
            ("numeric_summary", "Numeric Summary", "Summarize numeric columns.", ("dataset",), (), ("table",), "stats"),
            ("distribution_summary", "Distribution Summary", "Summarize the distribution of a target metric.", ("dataset", "target"), (), ("table",), "stats"),
            ("target_correlation", "Target Correlation", "Correlate a target metric with numeric peers.", ("dataset",), ("target",), ("table",), "stats"),
            ("anomaly_summary", "Anomaly Summary", "Flag anomaly candidates for a metric.", ("dataset", "target"), ("time_column",), ("table",), "stats"),
            ("time_series_diagnostics", "Time Series Diagnostics", "Run diagnostics for a metric over time.", ("dataset", "target", "time_column"), (), ("table",), "stats"),
            ("group_mean_comparison", "Group Mean Comparison", "Compare group means for a metric.", ("dataset", "target"), ("group_column",), ("table",), "stats"),
        ),
    )
    _register_methods(
        registry,
        "predictive_forecasting",
        (
            ("forecast", "Forecast", "Generate a forecast for a target metric.", ("dataset", "target"), ("horizon",), ("forecast_result",), "ml"),
        ),
    )
    return registry


def _register_methods(
    registry: AnalyticsRegistry,
    family_id: str,
    definitions: tuple[tuple[str, str, str, tuple[str, ...], tuple[str, ...], tuple[str, ...], str | None], ...],
) -> None:
    for method_id, label, description, required_inputs, allowed_configs, output_shapes, tool_family in definitions:
        registry.add_method(
            AnalyticsMethodSpec(
                method_id=method_id,
                family_id=family_id,
                label=label,
                description=description,
                required_inputs=required_inputs,
                allowed_configs=allowed_configs,
                output_shapes=output_shapes,
                default_tool_family=tool_family,
            )
        )


_DEFAULT_ANALYTICS_REGISTRY: AnalyticsRegistry | None = None


def get_analytics_registry() -> AnalyticsRegistry:
    global _DEFAULT_ANALYTICS_REGISTRY
    if _DEFAULT_ANALYTICS_REGISTRY is None:
        _DEFAULT_ANALYTICS_REGISTRY = build_default_analytics_registry()
    return _DEFAULT_ANALYTICS_REGISTRY
