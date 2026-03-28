"""Canonical analytics family, method, and concept registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AnalyticsAvailability = Literal["implemented", "partial", "planned"]
AnalyticsConceptCategory = Literal["domain", "pattern", "constraint", "primitive"]
AnalyticsRelation = Literal[
    "specializes",
    "requires",
    "uses",
    "compatible_with",
    "incompatible_with",
    "implies",
]


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
class AnalyticsConceptSpec:
    """Describe a higher-level analytics concept backed by the registry."""

    concept_id: str
    category: AnalyticsConceptCategory
    label: str
    description: str
    availability: AnalyticsAvailability = "implemented"
    planner_actions: list[str] = field(default_factory=list)
    required_parameters: list[str] = field(default_factory=list)
    result_shapes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "category": self.category,
            "label": self.label,
            "description": self.description,
            "availability": self.availability,
            "planner_actions": list(self.planner_actions),
            "required_parameters": list(self.required_parameters),
            "result_shapes": list(self.result_shapes),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class AnalyticsRelationSpec:
    """Typed relationship between analytics concepts, families, or methods."""

    source: str
    relation: AnalyticsRelation
    target: str
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "relation": self.relation,
            "target": self.target,
            "detail": self.detail,
        }


@dataclass(slots=True)
class AnalyticsRegistry:
    """Registry of canonical analytics families, methods, and concepts."""

    families: dict[str, AnalyticsFamilySpec] = field(default_factory=dict)
    methods: dict[str, AnalyticsMethodSpec] = field(default_factory=dict)
    concepts: dict[str, AnalyticsConceptSpec] = field(default_factory=dict)
    relations: list[AnalyticsRelationSpec] = field(default_factory=list)

    def add_family(self, family: AnalyticsFamilySpec) -> None:
        self.families[family.family_id] = family

    def add_method(self, method: AnalyticsMethodSpec) -> None:
        family = self.families.get(method.family_id)
        if family is None:
            raise ValueError(f"Unknown analytics family for method {method.method_id!r}: {method.family_id!r}")
        self.methods[method.method_id] = method
        if method.method_id not in family.method_ids:
            family.method_ids.append(method.method_id)

    def add_concept(self, concept: AnalyticsConceptSpec) -> None:
        self.concepts[concept.concept_id] = concept

    def add_relation(self, relation: AnalyticsRelationSpec) -> None:
        if not self.has_entity(relation.source):
            raise ValueError(f"Unknown analytics relation source: {relation.source}")
        if not self.has_entity(relation.target):
            raise ValueError(f"Unknown analytics relation target: {relation.target}")
        self.relations.append(relation)

    def get_family(self, family_id: str | None) -> AnalyticsFamilySpec | None:
        if family_id is None:
            return None
        return self.families.get(family_id)

    def get_method(self, method_id: str | None) -> AnalyticsMethodSpec | None:
        if method_id is None:
            return None
        return self.methods.get(method_id)

    def get_concept(self, concept_id: str | None) -> AnalyticsConceptSpec | None:
        if concept_id is None:
            return None
        return self.concepts.get(concept_id)

    def methods_for_family(self, family_id: str) -> list[AnalyticsMethodSpec]:
        family = self.get_family(family_id)
        if family is None:
            return []
        return [self.methods[method_id] for method_id in family.method_ids if method_id in self.methods]

    def family_for_method(self, method_id: str | None) -> str | None:
        method = self.get_method(method_id)
        return method.family_id if method is not None else None

    def relations_from(
        self,
        entity_id: str,
        relation: AnalyticsRelation | None = None,
    ) -> list[AnalyticsRelationSpec]:
        return [
            edge
            for edge in self.relations
            if edge.source == entity_id and (relation is None or edge.relation == relation)
        ]

    def relations_to(
        self,
        entity_id: str,
        relation: AnalyticsRelation | None = None,
    ) -> list[AnalyticsRelationSpec]:
        return [
            edge
            for edge in self.relations
            if edge.target == entity_id and (relation is None or edge.relation == relation)
        ]

    def related(self, entity_id: str, relation: AnalyticsRelation) -> list[str]:
        return [edge.target for edge in self.relations_from(entity_id, relation)]

    def concepts_by_category(self, category: AnalyticsConceptCategory) -> list[AnalyticsConceptSpec]:
        return [concept for concept in self.concepts.values() if concept.category == category]

    def has_entity(self, entity_id: str) -> bool:
        return entity_id in self.families or entity_id in self.methods or entity_id in self.concepts

    def to_dict(self) -> dict[str, Any]:
        return {
            "families": {family_id: family.to_dict() for family_id, family in self.families.items()},
            "methods": {method_id: method.to_dict() for method_id, method in self.methods.items()},
            "concepts": {concept_id: concept.to_dict() for concept_id, concept in self.concepts.items()},
            "relations": [relation.to_dict() for relation in self.relations],
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
    _register_primitive_concepts(registry)
    _register_concepts(registry)
    _register_relations(registry)
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


def _register_primitive_concepts(registry: AnalyticsRegistry) -> None:
    for method in registry.methods.values():
        registry.add_concept(
            AnalyticsConceptSpec(
                concept_id=method.method_id,
                category="primitive",
                label=method.label,
                description=method.description,
                availability=method.availability,
                planner_actions=[method.method_id],
                required_parameters=[value for value in method.required_inputs if value != "dataset"],
                result_shapes=list(method.output_shapes),
                metadata={
                    "family_id": method.family_id,
                    "default_tool_family": method.default_tool_family,
                },
            )
        )


def _register_concepts(registry: AnalyticsRegistry) -> None:
    concepts = [
        AnalyticsConceptSpec("metadata", "domain", "Metadata", "Dataset schema and profile inspection."),
        AnalyticsConceptSpec("descriptive", "domain", "Descriptive", "Single-metric or dataset summary workflows."),
        AnalyticsConceptSpec("comparative", "domain", "Comparative", "Period or peer comparisons."),
        AnalyticsConceptSpec("ranking", "domain", "Ranking", "Top-N, bottom-N, and ordered leaderboard workflows."),
        AnalyticsConceptSpec("trend", "domain", "Trend", "Time-bucket and trend-oriented workflows."),
        AnalyticsConceptSpec("diagnostic", "domain", "Diagnostic", "Exploratory summaries, anomalies, and diagnostics."),
        AnalyticsConceptSpec("statistical", "domain", "Statistical", "Inferential and statistical workflows."),
        AnalyticsConceptSpec("verification", "domain", "Verification", "Yes/no checks against the dataset."),
        AnalyticsConceptSpec("tabular", "domain", "Tabular", "Record retrieval and grouped table workflows."),
        AnalyticsConceptSpec("segmentation", "domain", "Segmentation", "Grouped analysis by dimensions."),
        AnalyticsConceptSpec("distribution", "domain", "Distribution", "Distribution and spread-oriented analysis."),
        AnalyticsConceptSpec("predictive", "domain", "Predictive", "Forecasting and predictive workflows.", availability="partial"),
        AnalyticsConceptSpec(
            "metadata_inventory",
            "pattern",
            "Metadata Inventory",
            "Column, type, missingness, identifier, and time-field inventories.",
            planner_actions=[
                "column_inventory",
                "column_type_inventory",
                "numeric_column_inventory",
                "categorical_column_inventory",
                "measure_inventory",
                "dimension_inventory",
                "time_column_inventory",
                "missing_value_inventory",
                "identifier_inventory",
                "high_cardinality_inventory",
                "column_count",
                "numeric_column_count",
                "categorical_column_count",
                "measure_count",
                "dimension_count",
                "time_column_count",
                "identifier_count",
                "high_cardinality_count",
            ],
            result_shapes=["table", "scalar"],
        ),
        AnalyticsConceptSpec(
            "distinct_value_listing",
            "pattern",
            "Distinct Value Listing",
            "List the available values for a dimension column.",
            planner_actions=["distinct_values"],
            required_parameters=["target"],
            result_shapes=["table"],
        ),
        AnalyticsConceptSpec(
            "representation_ranking",
            "pattern",
            "Representation Ranking",
            "Rank groups by row-count representation.",
            planner_actions=["count_rows_by_group"],
            required_parameters=["target"],
            result_shapes=["table"],
        ),
        AnalyticsConceptSpec(
            "top_n_by_metric",
            "pattern",
            "Top N By Metric",
            "Rank rows or grouped results by a metric.",
            planner_actions=["ranked_rows", "ranked_breakdown"],
            required_parameters=["target"],
            result_shapes=["table"],
        ),
        AnalyticsConceptSpec(
            "grouped_breakdown",
            "pattern",
            "Grouped Breakdown",
            "Aggregate a metric by one or more grouping dimensions.",
            planner_actions=["group_breakdown"],
            required_parameters=["target", "group_by"],
            result_shapes=["table"],
        ),
        AnalyticsConceptSpec(
            "grouped_trend",
            "pattern",
            "Grouped Trend",
            "Aggregate a metric across time buckets, optionally segmented by groups.",
            planner_actions=["time_bucket_counts", "time_bucket_breakdown", "time_trend"],
            required_parameters=["target"],
            result_shapes=["table", "timeseries"],
        ),
        AnalyticsConceptSpec(
            "period_over_period_comparison",
            "pattern",
            "Period Over Period Comparison",
            "Compare a metric between adjacent time periods.",
            planner_actions=["period_comparison"],
            required_parameters=["target", "time_reference"],
            result_shapes=["timeseries"],
        ),
        AnalyticsConceptSpec(
            "grouped_period_over_period_comparison",
            "pattern",
            "Grouped Period Comparison",
            "Compare grouped totals between adjacent time periods.",
            planner_actions=["grouped_period_comparison"],
            required_parameters=["target", "group_by", "time_reference"],
            result_shapes=["timeseries"],
        ),
        AnalyticsConceptSpec(
            "contribution_breakdown",
            "pattern",
            "Contribution Breakdown",
            "Estimate group-level contribution changes and movers.",
            planner_actions=["contribution_breakdown", "top_movers"],
            required_parameters=["target", "group_by"],
            result_shapes=["table"],
        ),
        AnalyticsConceptSpec(
            "tabular_record_retrieval",
            "pattern",
            "Tabular Record Retrieval",
            "Return filtered rows with selected columns, sorting, and pagination.",
            planner_actions=["tabular_query"],
            result_shapes=["recordset"],
        ),
        AnalyticsConceptSpec(
            "grouped_tabular_retrieval",
            "pattern",
            "Grouped Tabular Retrieval",
            "Return grouped aggregated tables with sorting and pagination.",
            planner_actions=["grouped_tabular_query"],
            required_parameters=["group_by"],
            result_shapes=["table"],
        ),
        AnalyticsConceptSpec(
            "filtered_existence_check",
            "pattern",
            "Filtered Existence Check",
            "Verify whether any rows match the requested filters.",
            planner_actions=["row_existence"],
            result_shapes=["verification"],
        ),
        AnalyticsConceptSpec(
            "time_value_existence_check",
            "pattern",
            "Time Value Existence Check",
            "Verify whether a requested time value exists.",
            planner_actions=["time_value_exists"],
            result_shapes=["verification"],
        ),
        AnalyticsConceptSpec(
            "null_verification",
            "pattern",
            "Null Verification",
            "Verify whether a column has or does not have null values.",
            planner_actions=["null_check"],
            required_parameters=["target"],
            result_shapes=["verification"],
        ),
        AnalyticsConceptSpec(
            "threshold_verification",
            "pattern",
            "Threshold Verification",
            "Verify threshold conditions for a metric.",
            planner_actions=["threshold_check"],
            required_parameters=["target"],
            result_shapes=["verification"],
        ),
        AnalyticsConceptSpec(
            "column_property_verification",
            "pattern",
            "Column Property Verification",
            "Verify whether a column matches a schema property.",
            planner_actions=["column_property_check", "column_presence_check"],
            required_parameters=["target"],
            result_shapes=["verification"],
        ),
        AnalyticsConceptSpec(
            "significance_inference",
            "pattern",
            "Significance Inference",
            "Run a significance test for a grouped metric comparison.",
            planner_actions=["significance_inference"],
            required_parameters=["target", "group_by"],
            result_shapes=["statistical_test"],
        ),
        AnalyticsConceptSpec(
            "confidence_interval",
            "pattern",
            "Confidence Interval",
            "Compute a confidence interval for a metric.",
            planner_actions=["confidence_interval"],
            required_parameters=["target"],
            result_shapes=["statistical_test"],
        ),
        AnalyticsConceptSpec(
            "power_analysis",
            "pattern",
            "Power Analysis",
            "Estimate observed power for a grouped comparison.",
            planner_actions=["power_analysis"],
            required_parameters=["target", "group_by"],
            result_shapes=["statistical_test"],
        ),
        AnalyticsConceptSpec(
            "sample_size_estimate",
            "pattern",
            "Sample Size Estimate",
            "Estimate required sample size for a grouped comparison.",
            planner_actions=["sample_size_estimate"],
            required_parameters=["target", "group_by"],
            result_shapes=["statistical_test"],
        ),
        AnalyticsConceptSpec(
            "forecast_series",
            "pattern",
            "Forecast Series",
            "Generate a forecast for a target time series.",
            planner_actions=["forecast"],
            required_parameters=["target", "horizon"],
            result_shapes=["forecast_result"],
            availability="partial",
        ),
        AnalyticsConceptSpec("requires_metric", "constraint", "Requires Metric", "Needs a numeric metric target."),
        AnalyticsConceptSpec("requires_dimension", "constraint", "Requires Dimension", "Needs a grouping dimension."),
        AnalyticsConceptSpec("requires_time_field", "constraint", "Requires Time Field", "Needs a valid time column."),
        AnalyticsConceptSpec("requires_reference_period", "constraint", "Requires Reference Period", "Needs a resolved time reference."),
        AnalyticsConceptSpec("requires_target_column", "constraint", "Requires Target Column", "Needs a valid target column."),
        AnalyticsConceptSpec("requires_filter", "constraint", "Requires Filter", "Needs a dataset filter condition."),
    ]
    for concept in concepts:
        registry.add_concept(concept)


def _register_relations(registry: AnalyticsRegistry) -> None:
    relations = [
        AnalyticsRelationSpec("metadata_inventory", "specializes", "metadata"),
        AnalyticsRelationSpec("distinct_value_listing", "specializes", "descriptive"),
        AnalyticsRelationSpec("distinct_value_listing", "specializes", "segmentation"),
        AnalyticsRelationSpec("representation_ranking", "specializes", "ranking"),
        AnalyticsRelationSpec("top_n_by_metric", "specializes", "ranking"),
        AnalyticsRelationSpec("top_n_by_metric", "specializes", "comparative"),
        AnalyticsRelationSpec("grouped_breakdown", "specializes", "descriptive"),
        AnalyticsRelationSpec("grouped_breakdown", "specializes", "segmentation"),
        AnalyticsRelationSpec("grouped_trend", "specializes", "trend"),
        AnalyticsRelationSpec("grouped_trend", "specializes", "segmentation"),
        AnalyticsRelationSpec("period_over_period_comparison", "specializes", "comparative"),
        AnalyticsRelationSpec("period_over_period_comparison", "specializes", "trend"),
        AnalyticsRelationSpec("grouped_period_over_period_comparison", "specializes", "comparative"),
        AnalyticsRelationSpec("grouped_period_over_period_comparison", "specializes", "trend"),
        AnalyticsRelationSpec("grouped_period_over_period_comparison", "specializes", "segmentation"),
        AnalyticsRelationSpec("contribution_breakdown", "specializes", "diagnostic"),
        AnalyticsRelationSpec("contribution_breakdown", "specializes", "segmentation"),
        AnalyticsRelationSpec("tabular_record_retrieval", "specializes", "tabular"),
        AnalyticsRelationSpec("grouped_tabular_retrieval", "specializes", "tabular"),
        AnalyticsRelationSpec("grouped_tabular_retrieval", "specializes", "segmentation"),
        AnalyticsRelationSpec("filtered_existence_check", "specializes", "verification"),
        AnalyticsRelationSpec("time_value_existence_check", "specializes", "verification"),
        AnalyticsRelationSpec("null_verification", "specializes", "verification"),
        AnalyticsRelationSpec("threshold_verification", "specializes", "verification"),
        AnalyticsRelationSpec("column_property_verification", "specializes", "verification"),
        AnalyticsRelationSpec("significance_inference", "specializes", "statistical"),
        AnalyticsRelationSpec("confidence_interval", "specializes", "statistical"),
        AnalyticsRelationSpec("power_analysis", "specializes", "statistical"),
        AnalyticsRelationSpec("sample_size_estimate", "specializes", "statistical"),
        AnalyticsRelationSpec("forecast_series", "specializes", "predictive"),
        AnalyticsRelationSpec("forecast_series", "specializes", "trend"),
        AnalyticsRelationSpec("distinct_value_listing", "requires", "requires_target_column"),
        AnalyticsRelationSpec("representation_ranking", "requires", "requires_dimension"),
        AnalyticsRelationSpec("top_n_by_metric", "requires", "requires_metric"),
        AnalyticsRelationSpec("grouped_breakdown", "requires", "requires_metric"),
        AnalyticsRelationSpec("grouped_breakdown", "requires", "requires_dimension"),
        AnalyticsRelationSpec("grouped_trend", "requires", "requires_metric"),
        AnalyticsRelationSpec("grouped_trend", "requires", "requires_time_field"),
        AnalyticsRelationSpec("period_over_period_comparison", "requires", "requires_metric"),
        AnalyticsRelationSpec("period_over_period_comparison", "requires", "requires_time_field"),
        AnalyticsRelationSpec("period_over_period_comparison", "requires", "requires_reference_period"),
        AnalyticsRelationSpec("grouped_period_over_period_comparison", "requires", "requires_metric"),
        AnalyticsRelationSpec("grouped_period_over_period_comparison", "requires", "requires_dimension"),
        AnalyticsRelationSpec("grouped_period_over_period_comparison", "requires", "requires_time_field"),
        AnalyticsRelationSpec("grouped_period_over_period_comparison", "requires", "requires_reference_period"),
        AnalyticsRelationSpec("contribution_breakdown", "requires", "requires_metric"),
        AnalyticsRelationSpec("contribution_breakdown", "requires", "requires_dimension"),
        AnalyticsRelationSpec("filtered_existence_check", "requires", "requires_filter"),
        AnalyticsRelationSpec("time_value_existence_check", "requires", "requires_time_field"),
        AnalyticsRelationSpec("null_verification", "requires", "requires_target_column"),
        AnalyticsRelationSpec("threshold_verification", "requires", "requires_metric"),
        AnalyticsRelationSpec("column_property_verification", "requires", "requires_target_column"),
        AnalyticsRelationSpec("significance_inference", "requires", "requires_metric"),
        AnalyticsRelationSpec("significance_inference", "requires", "requires_dimension"),
        AnalyticsRelationSpec("confidence_interval", "requires", "requires_metric"),
        AnalyticsRelationSpec("power_analysis", "requires", "requires_metric"),
        AnalyticsRelationSpec("power_analysis", "requires", "requires_dimension"),
        AnalyticsRelationSpec("sample_size_estimate", "requires", "requires_metric"),
        AnalyticsRelationSpec("sample_size_estimate", "requires", "requires_dimension"),
        AnalyticsRelationSpec("forecast_series", "requires", "requires_metric"),
        AnalyticsRelationSpec("forecast_series", "requires", "requires_time_field"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "column_inventory"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "column_type_inventory"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "numeric_column_inventory"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "categorical_column_inventory"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "measure_inventory"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "dimension_inventory"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "time_column_inventory"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "missing_value_inventory"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "identifier_inventory"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "high_cardinality_inventory"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "column_count"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "numeric_column_count"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "categorical_column_count"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "measure_count"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "dimension_count"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "time_column_count"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "identifier_count"),
        AnalyticsRelationSpec("metadata_inventory", "uses", "high_cardinality_count"),
        AnalyticsRelationSpec("distinct_value_listing", "uses", "distinct_values"),
        AnalyticsRelationSpec("representation_ranking", "uses", "count_rows_by_group"),
        AnalyticsRelationSpec("top_n_by_metric", "uses", "ranked_rows"),
        AnalyticsRelationSpec("top_n_by_metric", "uses", "ranked_breakdown"),
        AnalyticsRelationSpec("grouped_breakdown", "uses", "group_breakdown"),
        AnalyticsRelationSpec("grouped_trend", "uses", "time_bucket_counts"),
        AnalyticsRelationSpec("grouped_trend", "uses", "time_bucket_breakdown"),
        AnalyticsRelationSpec("grouped_trend", "uses", "time_trend"),
        AnalyticsRelationSpec("period_over_period_comparison", "uses", "period_comparison"),
        AnalyticsRelationSpec("grouped_period_over_period_comparison", "uses", "grouped_period_comparison"),
        AnalyticsRelationSpec("contribution_breakdown", "uses", "contribution_breakdown"),
        AnalyticsRelationSpec("contribution_breakdown", "uses", "top_movers"),
        AnalyticsRelationSpec("tabular_record_retrieval", "uses", "tabular_query"),
        AnalyticsRelationSpec("grouped_tabular_retrieval", "uses", "grouped_tabular_query"),
        AnalyticsRelationSpec("filtered_existence_check", "uses", "row_existence"),
        AnalyticsRelationSpec("time_value_existence_check", "uses", "time_value_exists"),
        AnalyticsRelationSpec("null_verification", "uses", "null_check"),
        AnalyticsRelationSpec("threshold_verification", "uses", "threshold_check"),
        AnalyticsRelationSpec("column_property_verification", "uses", "column_property_check"),
        AnalyticsRelationSpec("significance_inference", "uses", "significance_inference"),
        AnalyticsRelationSpec("confidence_interval", "uses", "confidence_interval"),
        AnalyticsRelationSpec("power_analysis", "uses", "power_analysis"),
        AnalyticsRelationSpec("sample_size_estimate", "uses", "sample_size_estimate"),
        AnalyticsRelationSpec("forecast_series", "uses", "forecast"),
    ]
    for relation in relations:
        registry.add_relation(relation)


_DEFAULT_ANALYTICS_REGISTRY: AnalyticsRegistry | None = None


def get_analytics_registry() -> AnalyticsRegistry:
    global _DEFAULT_ANALYTICS_REGISTRY
    if _DEFAULT_ANALYTICS_REGISTRY is None:
        _DEFAULT_ANALYTICS_REGISTRY = build_default_analytics_registry()
    return _DEFAULT_ANALYTICS_REGISTRY
