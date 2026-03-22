"""Capability graph registry scaffolding for prompt-to-plan compilation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

CapabilityCategory = Literal["domain", "pattern", "primitive", "constraint"]
CapabilityRelation = Literal[
    "specializes",
    "requires",
    "uses",
    "compatible_with",
    "incompatible_with",
    "implies",
]
CapabilityAvailability = Literal["implemented", "partial", "planned"]


@dataclass(slots=True)
class CapabilityNode:
    """Describe a single capability node in the prompt capability graph."""

    capability_id: str
    category: CapabilityCategory
    label: str
    description: str
    availability: CapabilityAvailability = "implemented"
    planner_actions: list[str] = field(default_factory=list)
    required_parameters: list[str] = field(default_factory=list)
    result_shapes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CapabilityEdge:
    """Typed relationship between capability nodes."""

    source: str
    relation: CapabilityRelation
    target: str
    detail: str | None = None


@dataclass(slots=True)
class CapabilityRegistry:
    """In-memory capability graph registry."""

    nodes: dict[str, CapabilityNode] = field(default_factory=dict)
    edges: list[CapabilityEdge] = field(default_factory=list)

    def add_node(self, node: CapabilityNode) -> None:
        self.nodes[node.capability_id] = node

    def add_edge(self, edge: CapabilityEdge) -> None:
        if edge.source not in self.nodes:
            raise ValueError(f"Unknown capability edge source: {edge.source}")
        if edge.target not in self.nodes:
            raise ValueError(f"Unknown capability edge target: {edge.target}")
        self.edges.append(edge)

    def get_node(self, capability_id: str) -> CapabilityNode | None:
        return self.nodes.get(capability_id)

    def edges_from(
        self,
        capability_id: str,
        relation: CapabilityRelation | None = None,
    ) -> list[CapabilityEdge]:
        return [
            edge
            for edge in self.edges
            if edge.source == capability_id and (relation is None or edge.relation == relation)
        ]

    def edges_to(
        self,
        capability_id: str,
        relation: CapabilityRelation | None = None,
    ) -> list[CapabilityEdge]:
        return [
            edge
            for edge in self.edges
            if edge.target == capability_id and (relation is None or edge.relation == relation)
        ]

    def related(
        self,
        capability_id: str,
        relation: CapabilityRelation,
    ) -> list[str]:
        return [edge.target for edge in self.edges_from(capability_id, relation)]

    def nodes_by_category(self, category: CapabilityCategory) -> list[CapabilityNode]:
        return [node for node in self.nodes.values() if node.category == category]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {
                node_id: {
                    "category": node.category,
                    "label": node.label,
                    "description": node.description,
                    "availability": node.availability,
                    "planner_actions": list(node.planner_actions),
                    "required_parameters": list(node.required_parameters),
                    "result_shapes": list(node.result_shapes),
                    "metadata": dict(node.metadata),
                }
                for node_id, node in self.nodes.items()
            },
            "edges": [
                {
                    "source": edge.source,
                    "relation": edge.relation,
                    "target": edge.target,
                    "detail": edge.detail,
                }
                for edge in self.edges
            ],
        }


def build_default_capability_registry() -> CapabilityRegistry:
    """Build the first concrete registry grounded in the live SAIDA surface."""

    registry = CapabilityRegistry()

    nodes = [
        CapabilityNode("metadata", "domain", "Metadata", "Dataset schema and profile inspection."),
        CapabilityNode("descriptive", "domain", "Descriptive", "Single-metric or dataset summary workflows."),
        CapabilityNode("comparative", "domain", "Comparative", "Period or peer comparisons."),
        CapabilityNode("ranking", "domain", "Ranking", "Top-N, bottom-N, and representation ranking."),
        CapabilityNode("trend", "domain", "Trend", "Time-bucket and trend-oriented workflows."),
        CapabilityNode("diagnostic", "domain", "Diagnostic", "Contribution, movers, anomalies, and drivers."),
        CapabilityNode("statistical", "domain", "Statistical", "Inferential and statistical workflows."),
        CapabilityNode("verification", "domain", "Verification", "Yes/no checks against the dataset."),
        CapabilityNode("tabular", "domain", "Tabular", "Record retrieval and grouped table workflows."),
        CapabilityNode("segmentation", "domain", "Segmentation", "Grouped analysis by dimensions."),
        CapabilityNode("distribution", "domain", "Distribution", "Distribution and spread-oriented analysis."),
        CapabilityNode(
            "predictive",
            "domain",
            "Predictive",
            "Forecasting and predictive workflows.",
            availability="partial",
        ),
        CapabilityNode(
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
            ],
            result_shapes=["table"],
        ),
        CapabilityNode(
            "distinct_value_listing",
            "pattern",
            "Distinct Value Listing",
            "List the available values for a dimension column.",
            planner_actions=["distinct_values"],
            required_parameters=["target"],
            result_shapes=["table"],
        ),
        CapabilityNode(
            "representation_ranking",
            "pattern",
            "Representation Ranking",
            "Rank groups by row count representation.",
            planner_actions=["count_rows_by_group"],
            required_parameters=["target"],
            result_shapes=["table"],
        ),
        CapabilityNode(
            "top_n_by_metric",
            "pattern",
            "Top N By Metric",
            "Rank rows or grouped results by a metric.",
            planner_actions=["ranked_rows", "ranked_breakdown"],
            required_parameters=["target"],
            result_shapes=["table"],
        ),
        CapabilityNode(
            "grouped_breakdown",
            "pattern",
            "Grouped Breakdown",
            "Aggregate a metric by one or more grouping dimensions.",
            planner_actions=["group_breakdown"],
            required_parameters=["target", "group_by"],
            result_shapes=["table"],
        ),
        CapabilityNode(
            "grouped_trend",
            "pattern",
            "Grouped Trend",
            "Aggregate a metric across time buckets, optionally segmented by groups.",
            planner_actions=["time_bucket_breakdown", "time_trend"],
            required_parameters=["target"],
            result_shapes=["timeseries"],
        ),
        CapabilityNode(
            "period_over_period_comparison",
            "pattern",
            "Period Over Period Comparison",
            "Compare a metric between adjacent time periods.",
            planner_actions=["period_comparison"],
            required_parameters=["target", "time_reference"],
            result_shapes=["timeseries"],
        ),
        CapabilityNode(
            "grouped_period_over_period_comparison",
            "pattern",
            "Grouped Period Comparison",
            "Compare grouped totals between adjacent time periods.",
            planner_actions=["grouped_period_comparison"],
            required_parameters=["target", "group_by", "time_reference"],
            result_shapes=["timeseries"],
        ),
        CapabilityNode(
            "contribution_breakdown",
            "pattern",
            "Contribution Breakdown",
            "Estimate group-level contribution changes and movers.",
            planner_actions=["contribution_breakdown", "top_movers"],
            required_parameters=["target", "group_by"],
            result_shapes=["table"],
        ),
        CapabilityNode(
            "tabular_record_retrieval",
            "pattern",
            "Tabular Record Retrieval",
            "Return filtered rows with selected columns, sorting, and pagination.",
            planner_actions=["tabular_query"],
            result_shapes=["recordset"],
        ),
        CapabilityNode(
            "grouped_tabular_retrieval",
            "pattern",
            "Grouped Tabular Retrieval",
            "Return grouped aggregated tables with sorting and pagination.",
            planner_actions=["grouped_tabular_query"],
            required_parameters=["group_by"],
            result_shapes=["table"],
        ),
        CapabilityNode(
            "filtered_existence_check",
            "pattern",
            "Filtered Existence Check",
            "Verify whether any rows match the requested filters.",
            planner_actions=["row_existence"],
            result_shapes=["verification"],
        ),
        CapabilityNode(
            "time_value_existence_check",
            "pattern",
            "Time Value Existence Check",
            "Verify whether a requested date, month, quarter, or year exists.",
            planner_actions=["time_value_exists"],
            result_shapes=["verification"],
        ),
        CapabilityNode(
            "null_verification",
            "pattern",
            "Null Verification",
            "Verify whether a column has or does not have null values.",
            planner_actions=["null_check"],
            required_parameters=["target"],
            result_shapes=["verification"],
        ),
        CapabilityNode(
            "threshold_verification",
            "pattern",
            "Threshold Verification",
            "Verify whether a numeric threshold condition exists.",
            planner_actions=["threshold_check"],
            required_parameters=["target"],
            result_shapes=["verification"],
        ),
        CapabilityNode(
            "column_property_verification",
            "pattern",
            "Column Property Verification",
            "Verify whether a column matches an expected schema property.",
            planner_actions=["column_property_check"],
            required_parameters=["target"],
            result_shapes=["verification"],
        ),
        CapabilityNode(
            "anomaly_scan",
            "pattern",
            "Anomaly Scan",
            "Flag deterministic anomaly candidates for a metric.",
            planner_actions=["anomaly_summary"],
            required_parameters=["target"],
            result_shapes=["table"],
        ),
        CapabilityNode(
            "significance_inference",
            "pattern",
            "Significance Inference",
            "Run a deterministic significance workflow over a metric and grouping column.",
            planner_actions=["significance_inference"],
            required_parameters=["target", "group_by"],
            result_shapes=["statistical_test"],
        ),
        CapabilityNode(
            "confidence_interval",
            "pattern",
            "Confidence Interval",
            "Compute a confidence interval for a numeric target.",
            planner_actions=["confidence_interval"],
            required_parameters=["target"],
            result_shapes=["statistical_test"],
        ),
        CapabilityNode(
            "power_analysis",
            "pattern",
            "Power Analysis",
            "Estimate whether the current grouped sample has enough statistical power.",
            planner_actions=["power_analysis"],
            required_parameters=["target", "group_by"],
            result_shapes=["statistical_test"],
        ),
        CapabilityNode(
            "sample_size_estimate",
            "pattern",
            "Sample Size Estimate",
            "Estimate required grouped sample size for a target.",
            planner_actions=["sample_size_estimate"],
            required_parameters=["target", "group_by"],
            result_shapes=["statistical_test"],
        ),
        CapabilityNode(
            "forecast_series",
            "pattern",
            "Forecast Series",
            "Generate a forecast for a target metric over a future horizon.",
            availability="partial",
            planner_actions=["forecast"],
            required_parameters=["target", "horizon"],
            result_shapes=["timeseries"],
        ),
        CapabilityNode("column_inventory", "primitive", "Column Inventory", "Return column inventory metadata."),
        CapabilityNode("distinct_values", "primitive", "Distinct Values", "Return distinct values for a dimension."),
        CapabilityNode("row_count", "primitive", "Row Count", "Count rows for the requested slice."),
        CapabilityNode("count_rows_by_group", "primitive", "Count Rows By Group", "Count grouped row representation."),
        CapabilityNode("aggregate_value", "primitive", "Aggregate Value", "Compute a scalar aggregate."),
        CapabilityNode("dataset_summary", "primitive", "Dataset Summary", "Compute top-level summary metrics."),
        CapabilityNode("time_trend", "primitive", "Time Trend", "Aggregate a target over time."),
        CapabilityNode("time_bucket_counts", "primitive", "Time Bucket Counts", "Count rows by derived time bucket."),
        CapabilityNode("time_bucket_breakdown", "primitive", "Time Bucket Breakdown", "Aggregate a target by time bucket."),
        CapabilityNode("period_comparison", "primitive", "Period Comparison", "Compare adjacent time periods."),
        CapabilityNode(
            "grouped_period_comparison",
            "primitive",
            "Grouped Period Comparison",
            "Compare grouped totals across adjacent time periods.",
        ),
        CapabilityNode("group_breakdown", "primitive", "Group Breakdown", "Aggregate a target by group."),
        CapabilityNode("ranked_rows", "primitive", "Ranked Rows", "Rank rows by a target."),
        CapabilityNode("ranked_breakdown", "primitive", "Ranked Breakdown", "Rank grouped aggregates by a target."),
        CapabilityNode("top_movers", "primitive", "Top Movers", "Identify largest movers between periods."),
        CapabilityNode(
            "contribution_breakdown",
            "primitive",
            "Contribution Breakdown Primitive",
            "Compute contribution changes by group.",
        ),
        CapabilityNode("tabular_query", "primitive", "Tabular Query", "Return filtered and paginated records."),
        CapabilityNode(
            "grouped_tabular_query",
            "primitive",
            "Grouped Tabular Query",
            "Return grouped aggregated and paginated rows.",
        ),
        CapabilityNode("row_existence", "primitive", "Row Existence", "Check whether filtered rows exist."),
        CapabilityNode(
            "time_value_exists",
            "primitive",
            "Time Value Exists",
            "Check whether a time value exists in the dataset.",
        ),
        CapabilityNode("null_check", "primitive", "Null Check", "Check null expectations for a column."),
        CapabilityNode("threshold_check", "primitive", "Threshold Check", "Check numeric threshold conditions."),
        CapabilityNode(
            "column_property_check",
            "primitive",
            "Column Property Check",
            "Check whether a column satisfies a schema property.",
        ),
        CapabilityNode(
            "missingness_summary",
            "primitive",
            "Missingness Summary",
            "Summarize missing values by column.",
        ),
        CapabilityNode("numeric_summary", "primitive", "Numeric Summary", "Summarize numeric columns."),
        CapabilityNode(
            "distribution_summary",
            "primitive",
            "Distribution Summary",
            "Summarize the target distribution.",
        ),
        CapabilityNode(
            "target_correlation",
            "primitive",
            "Target Correlation",
            "Measure correlations against the target.",
        ),
        CapabilityNode("anomaly_summary", "primitive", "Anomaly Summary", "Compute anomaly candidates."),
        CapabilityNode(
            "group_mean_comparison",
            "primitive",
            "Group Mean Comparison",
            "Compare group means for a target.",
        ),
        CapabilityNode(
            "significance_inference_action",
            "primitive",
            "Significance Inference Primitive",
            "Execute the significance inference workflow.",
            planner_actions=["significance_inference"],
        ),
        CapabilityNode(
            "confidence_interval_action",
            "primitive",
            "Confidence Interval Primitive",
            "Execute the confidence interval workflow.",
            planner_actions=["confidence_interval"],
        ),
        CapabilityNode(
            "power_analysis_action",
            "primitive",
            "Power Analysis Primitive",
            "Execute the power analysis workflow.",
            planner_actions=["power_analysis"],
        ),
        CapabilityNode(
            "sample_size_estimate_action",
            "primitive",
            "Sample Size Estimate Primitive",
            "Execute the sample size estimate workflow.",
            planner_actions=["sample_size_estimate"],
        ),
        CapabilityNode(
            "forecast",
            "primitive",
            "Forecast Primitive",
            "Execute the forecast workflow.",
            availability="partial",
        ),
        CapabilityNode("requires_metric", "constraint", "Requires Metric", "Needs a numeric metric target."),
        CapabilityNode("requires_dimension", "constraint", "Requires Dimension", "Needs a grouping dimension."),
        CapabilityNode("requires_time_field", "constraint", "Requires Time Field", "Needs a valid time column."),
        CapabilityNode(
            "requires_reference_period",
            "constraint",
            "Requires Reference Period",
            "Needs an explicit comparison period reference.",
        ),
        CapabilityNode(
            "requires_target_column",
            "constraint",
            "Requires Target Column",
            "Needs a resolved target column.",
        ),
        CapabilityNode("requires_filter", "constraint", "Requires Filter", "Needs a dataset filter condition."),
        CapabilityNode("output_shape_table", "constraint", "Table Output", "Produces a tabular result shape."),
        CapabilityNode(
            "output_shape_timeseries",
            "constraint",
            "Timeseries Output",
            "Produces a time-oriented result shape.",
        ),
        CapabilityNode(
            "output_shape_verification",
            "constraint",
            "Verification Output",
            "Produces a verification-oriented result shape.",
        ),
        CapabilityNode(
            "output_shape_recordset",
            "constraint",
            "Recordset Output",
            "Produces a record retrieval result shape.",
        ),
        CapabilityNode(
            "output_shape_statistical_test",
            "constraint",
            "Statistical Test Output",
            "Produces a statistical test result shape.",
        ),
    ]

    for node in nodes:
        registry.add_node(node)

    edges = [
        CapabilityEdge("metadata_inventory", "specializes", "metadata"),
        CapabilityEdge("distinct_value_listing", "specializes", "descriptive"),
        CapabilityEdge("distinct_value_listing", "specializes", "segmentation"),
        CapabilityEdge("representation_ranking", "specializes", "ranking"),
        CapabilityEdge("top_n_by_metric", "specializes", "ranking"),
        CapabilityEdge("top_n_by_metric", "specializes", "comparative"),
        CapabilityEdge("grouped_breakdown", "specializes", "descriptive"),
        CapabilityEdge("grouped_breakdown", "specializes", "segmentation"),
        CapabilityEdge("grouped_trend", "specializes", "trend"),
        CapabilityEdge("grouped_trend", "specializes", "segmentation"),
        CapabilityEdge("period_over_period_comparison", "specializes", "comparative"),
        CapabilityEdge("period_over_period_comparison", "specializes", "trend"),
        CapabilityEdge("grouped_period_over_period_comparison", "specializes", "comparative"),
        CapabilityEdge("grouped_period_over_period_comparison", "specializes", "trend"),
        CapabilityEdge("grouped_period_over_period_comparison", "specializes", "segmentation"),
        CapabilityEdge("contribution_breakdown", "specializes", "diagnostic"),
        CapabilityEdge("contribution_breakdown", "specializes", "segmentation"),
        CapabilityEdge("tabular_record_retrieval", "specializes", "tabular"),
        CapabilityEdge("grouped_tabular_retrieval", "specializes", "tabular"),
        CapabilityEdge("grouped_tabular_retrieval", "specializes", "segmentation"),
        CapabilityEdge("filtered_existence_check", "specializes", "verification"),
        CapabilityEdge("time_value_existence_check", "specializes", "verification"),
        CapabilityEdge("null_verification", "specializes", "verification"),
        CapabilityEdge("threshold_verification", "specializes", "verification"),
        CapabilityEdge("column_property_verification", "specializes", "verification"),
        CapabilityEdge("anomaly_scan", "specializes", "diagnostic"),
        CapabilityEdge("anomaly_scan", "specializes", "distribution"),
        CapabilityEdge("significance_inference", "specializes", "statistical"),
        CapabilityEdge("confidence_interval", "specializes", "statistical"),
        CapabilityEdge("power_analysis", "specializes", "statistical"),
        CapabilityEdge("sample_size_estimate", "specializes", "statistical"),
        CapabilityEdge("forecast_series", "specializes", "predictive"),
        CapabilityEdge("forecast_series", "specializes", "trend"),
        CapabilityEdge("distinct_value_listing", "requires", "requires_target_column"),
        CapabilityEdge("representation_ranking", "requires", "requires_dimension"),
        CapabilityEdge("top_n_by_metric", "requires", "requires_metric"),
        CapabilityEdge("grouped_breakdown", "requires", "requires_metric"),
        CapabilityEdge("grouped_breakdown", "requires", "requires_dimension"),
        CapabilityEdge("grouped_trend", "requires", "requires_metric"),
        CapabilityEdge("grouped_trend", "requires", "requires_time_field"),
        CapabilityEdge("period_over_period_comparison", "requires", "requires_metric"),
        CapabilityEdge("period_over_period_comparison", "requires", "requires_time_field"),
        CapabilityEdge("period_over_period_comparison", "requires", "requires_reference_period"),
        CapabilityEdge("grouped_period_over_period_comparison", "requires", "requires_metric"),
        CapabilityEdge("grouped_period_over_period_comparison", "requires", "requires_dimension"),
        CapabilityEdge("grouped_period_over_period_comparison", "requires", "requires_time_field"),
        CapabilityEdge("grouped_period_over_period_comparison", "requires", "requires_reference_period"),
        CapabilityEdge("contribution_breakdown", "requires", "requires_metric"),
        CapabilityEdge("contribution_breakdown", "requires", "requires_dimension"),
        CapabilityEdge("filtered_existence_check", "requires", "requires_filter"),
        CapabilityEdge("time_value_existence_check", "requires", "requires_time_field"),
        CapabilityEdge("null_verification", "requires", "requires_target_column"),
        CapabilityEdge("threshold_verification", "requires", "requires_metric"),
        CapabilityEdge("column_property_verification", "requires", "requires_target_column"),
        CapabilityEdge("anomaly_scan", "requires", "requires_metric"),
        CapabilityEdge("significance_inference", "requires", "requires_metric"),
        CapabilityEdge("significance_inference", "requires", "requires_dimension"),
        CapabilityEdge("confidence_interval", "requires", "requires_metric"),
        CapabilityEdge("power_analysis", "requires", "requires_metric"),
        CapabilityEdge("power_analysis", "requires", "requires_dimension"),
        CapabilityEdge("sample_size_estimate", "requires", "requires_metric"),
        CapabilityEdge("sample_size_estimate", "requires", "requires_dimension"),
        CapabilityEdge("forecast_series", "requires", "requires_metric"),
        CapabilityEdge("forecast_series", "requires", "requires_time_field"),
        CapabilityEdge("top_n_by_metric", "uses", "ranked_rows"),
        CapabilityEdge("top_n_by_metric", "uses", "ranked_breakdown"),
        CapabilityEdge("grouped_breakdown", "uses", "group_breakdown"),
        CapabilityEdge("grouped_trend", "uses", "time_bucket_breakdown"),
        CapabilityEdge("grouped_trend", "uses", "time_trend"),
        CapabilityEdge("period_over_period_comparison", "uses", "period_comparison"),
        CapabilityEdge("grouped_period_over_period_comparison", "uses", "grouped_period_comparison"),
        CapabilityEdge("contribution_breakdown", "uses", "contribution_breakdown"),
        CapabilityEdge("contribution_breakdown", "uses", "top_movers"),
        CapabilityEdge("tabular_record_retrieval", "uses", "tabular_query"),
        CapabilityEdge("grouped_tabular_retrieval", "uses", "grouped_tabular_query"),
        CapabilityEdge("filtered_existence_check", "uses", "row_existence"),
        CapabilityEdge("time_value_existence_check", "uses", "time_value_exists"),
        CapabilityEdge("null_verification", "uses", "null_check"),
        CapabilityEdge("threshold_verification", "uses", "threshold_check"),
        CapabilityEdge("column_property_verification", "uses", "column_property_check"),
        CapabilityEdge("metadata_inventory", "uses", "column_inventory"),
        CapabilityEdge("distinct_value_listing", "uses", "distinct_values"),
        CapabilityEdge("representation_ranking", "uses", "count_rows_by_group"),
        CapabilityEdge("anomaly_scan", "uses", "anomaly_summary"),
        CapabilityEdge("significance_inference", "uses", "significance_inference_action"),
        CapabilityEdge("confidence_interval", "uses", "confidence_interval_action"),
        CapabilityEdge("power_analysis", "uses", "power_analysis_action"),
        CapabilityEdge("sample_size_estimate", "uses", "sample_size_estimate_action"),
        CapabilityEdge("forecast_series", "uses", "forecast"),
        CapabilityEdge("grouped_breakdown", "compatible_with", "period_over_period_comparison"),
        CapabilityEdge("top_n_by_metric", "compatible_with", "grouped_trend"),
        CapabilityEdge("tabular_record_retrieval", "incompatible_with", "output_shape_verification"),
        CapabilityEdge("forecast_series", "incompatible_with", "output_shape_recordset"),
        CapabilityEdge("representation_ranking", "implies", "segmentation"),
        CapabilityEdge("grouped_trend", "implies", "trend"),
        CapabilityEdge("period_over_period_comparison", "implies", "comparative"),
        CapabilityEdge("forecast_series", "implies", "trend"),
        CapabilityEdge("tabular_record_retrieval", "implies", "output_shape_recordset"),
        CapabilityEdge("grouped_tabular_retrieval", "implies", "output_shape_table"),
        CapabilityEdge("grouped_trend", "implies", "output_shape_timeseries"),
        CapabilityEdge("period_over_period_comparison", "implies", "output_shape_timeseries"),
        CapabilityEdge("grouped_period_over_period_comparison", "implies", "output_shape_timeseries"),
        CapabilityEdge("filtered_existence_check", "implies", "output_shape_verification"),
        CapabilityEdge("time_value_existence_check", "implies", "output_shape_verification"),
        CapabilityEdge("null_verification", "implies", "output_shape_verification"),
        CapabilityEdge("threshold_verification", "implies", "output_shape_verification"),
        CapabilityEdge("column_property_verification", "implies", "output_shape_verification"),
        CapabilityEdge("significance_inference", "implies", "output_shape_statistical_test"),
        CapabilityEdge("confidence_interval", "implies", "output_shape_statistical_test"),
        CapabilityEdge("power_analysis", "implies", "output_shape_statistical_test"),
        CapabilityEdge("sample_size_estimate", "implies", "output_shape_statistical_test"),
    ]

    for edge in edges:
        registry.add_edge(edge)

    return registry


def get_capability_registry() -> CapabilityRegistry:
    """Return a fresh copy of the default capability registry."""

    return build_default_capability_registry()
