"""Central capability contract for SAIDA's current deterministic surface."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


SUPPORTED_TASK_TYPES = (
    "descriptive",
    "diagnostic",
    "statistical",
    "predictive",
    "forecasting",
)

SUPPORTED_AGGREGATIONS = (
    "sum",
    "mean",
    "max",
    "min",
    "count",
)

SUPPORTED_TIME_REFERENCE_TYPES = (
    "month_name",
    "quarter",
    "relative_period",
)

SUPPORTED_FILTER_OPERATORS = (
    "eq",
    "neq",
    "year_eq",
    "month_eq",
)

SUPPORTED_EXISTENCE_MODES = (
    "filtered_rows",
    "time_value",
    "column_presence_check",
    "null_check",
    "threshold_check",
    "column_property_check",
)

SUPPORTED_COLUMN_PROPERTIES = (
    "datetime",
    "numeric",
    "categorical",
    "identifier",
    "dimension",
    "measure",
    "high_cardinality",
)

SUPPORTED_STATISTICAL_TESTS = (
    "t_test",
    "chi_square",
    "anova",
    "mann_whitney",
    "confidence_interval",
    "regression_significance",
    "power_analysis",
    "sample_size_estimate",
    "significance_inference",
)

SUPPORTED_RESULT_PHYSICAL_SHAPES = (
    "scalar",
    "vector",
    "object",
    "recordset",
)

SUPPORTED_RESULT_LOGICAL_SHAPES = (
    "empty",
    "scalar",
    "count",
    "aggregate",
    "table",
    "recordset",
    "timeseries",
    "verification",
    "distribution",
    "correlation_matrix",
    "statistical_test",
)

SUPPORTED_RESULT_DTYPES = (
    "null",
    "boolean",
    "integer",
    "float",
    "datetime",
    "string",
    "object",
    "record",
)

SUPPORTED_SCHEMA_COLUMN_DTYPES = (
    "boolean",
    "integer",
    "float",
    "datetime",
    "string",
)

ANALYSIS_REQUEST_FIELDS = (
    "question",
    "intent_name",
    "task_type_hint",
    "target",
    "aggregation",
    "horizon",
    "filters",
    "group_by",
    "time_reference",
    "options",
)

ANALYSIS_PLAN_FIELDS = (
    "task_type",
    "rationale",
    "steps",
    "warnings",
)

PLAN_STEP_FIELDS = (
    "step_id",
    "tool_family",
    "action",
    "parameters",
    "description",
)

ANALYSIS_RESULT_TOP_LEVEL_FIELDS = (
    "schema_version",
    "status",
    "request",
    "interpretation",
    "execution",
    "result",
    "tables",
    "reasoning",
    "history",
    "warnings",
    "errors",
    "meta",
)

RESULT_OBJECT_FIELDS = (
    "name",
    "description",
    "physical_shape",
    "logical_shape",
    "dtype",
    "schema",
    "dimensions",
    "row_count",
    "labels",
    "pagination",
    "metadata",
    "value",
)

PAGINATION_FIELDS = (
    "page",
    "page_size",
    "total_rows",
    "returned_rows",
    "has_next_page",
    "has_previous_page",
    "offset",
    "next_page_token",
)

INPUT_SURFACE = {
    "entry_points": [
        "Saida.analyze(dataset, question)",
        "Saida.profile(dataset)",
        "Saida.load_context(markdown)",
        "Saida.train(dataset, target, problem_type='regression', feature_columns=None)",
        "Saida.predict(dataset, artifact_path)",
        "Saida.forecast(dataset, target, horizon=3)",
    ],
    "dataset_contract": {
        "fields": ["name", "source_type", "data", "metadata", "context"],
        "required": ["name", "source_type", "data"],
    },
    "analysis_request_fields": list(ANALYSIS_REQUEST_FIELDS),
    "task_types": list(SUPPORTED_TASK_TYPES),
    "aggregations": list(SUPPORTED_AGGREGATIONS),
    "time_reference_types": list(SUPPORTED_TIME_REFERENCE_TYPES),
    "filter_operators": list(SUPPORTED_FILTER_OPERATORS),
}

INTENT_FAMILIES = {
    "metadata_inquiry": {
        "intent_names": [
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
        "planner_actions": [
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
            "column_property_check",
            "column_presence_check",
        ],
        "accepted_inputs": {
            "target": "optional for inventory requests; required for column_property_check",
            "group_by": "not used",
            "filters": "not used for inventory requests",
            "aggregation": "not used",
        },
        "result_shapes": ["table", "verification"],
    },
    "row_counting": {
        "intent_names": ["row_count", "representation_ranking"],
        "planner_actions": ["row_count", "count_rows_by_group"],
        "accepted_inputs": {
            "target": "optional for row_count; dimension target required for representation_ranking",
            "group_by": "derived from target for representation_ranking",
            "filters": "supported",
            "aggregation": "count only",
        },
        "result_shapes": ["count", "table"],
    },
    "time_analysis": {
        "intent_names": [
            "time_coverage",
            "time_bucket_counts",
            "time_bucket_breakdown",
            "time_period_comparison",
        ],
        "planner_actions": [
            "time_coverage",
            "time_bucket_counts",
            "time_bucket_breakdown",
            "period_comparison",
            "grouped_period_comparison",
            "time_trend",
        ],
        "accepted_inputs": {
            "target": "not required for time_coverage or time_bucket_counts; numeric target required for breakdown/comparison",
            "group_by": "optional for grouped period comparison",
            "filters": "supported",
            "aggregation": "sum, mean, max, min, count",
            "time_bucket": "year, month, quarter",
        },
        "result_shapes": ["timeseries", "table"],
    },
    "verification": {
        "intent_names": ["existence_check"],
        "planner_actions": [
            "time_value_exists",
            "row_existence",
            "column_presence_check",
            "null_check",
            "threshold_check",
            "column_property_check",
        ],
        "accepted_inputs": {
            "target": "required except for filtered row existence and column_presence_check",
            "group_by": "not used",
            "filters": "supported",
            "aggregation": "not used",
            "existence_modes": list(SUPPORTED_EXISTENCE_MODES),
        },
        "result_shapes": ["verification"],
    },
    "ranking": {
        "intent_names": ["row_ranking", "group_ranking"],
        "planner_actions": ["ranked_rows", "ranked_breakdown"],
        "accepted_inputs": {
            "target": "numeric target required",
            "group_by": "required for group_ranking",
            "filters": "supported",
            "aggregation": "optional for group_ranking; defaults to sum",
            "ordering": "top/bottom translated to desc/asc",
            "limit": "supported",
        },
        "result_shapes": ["table"],
    },
    "tabular_querying": {
        "intent_names": ["tabular_query", "grouped_tabular_query"],
        "planner_actions": ["tabular_query", "grouped_tabular_query"],
        "accepted_inputs": {
            "selected_columns": "supported for tabular_query",
            "target": "optional for grouped_tabular_query; numeric target required when provided",
            "group_by": "required for grouped_tabular_query",
            "filters": "supported",
            "ordering": "supported",
            "limit": "supported",
            "pagination": "page and page_size supported",
        },
        "result_shapes": ["recordset", "table"],
    },
    "descriptive_and_diagnostic_analysis": {
        "intent_names": ["generic_descriptive", "grouped_descriptive", "diagnostic"],
        "planner_actions": [
            "aggregate_value",
            "dataset_summary",
            "time_trend",
            "group_breakdown",
            "ranked_breakdown",
            "top_movers",
            "contribution_breakdown",
            "missingness_summary",
            "numeric_summary",
            "distribution_summary",
            "target_correlation",
            "anomaly_summary",
            "time_series_diagnostics",
            "group_mean_comparison",
        ],
        "accepted_inputs": {
            "target": "numeric target required for aggregations and grouped descriptive analysis",
            "group_by": "supported for grouped descriptive analysis",
            "filters": "supported",
            "aggregation": "sum, mean, max, min, count",
            "time_reference": "month_name and quarter supported outside explicit period-comparison family; relative_period reserved for comparisons",
        },
        "result_shapes": ["aggregate", "timeseries", "table", "distribution", "correlation_matrix"],
    },
    "statistical_testing": {
        "intent_names": ["statistical_workflow"],
        "planner_actions": list(SUPPORTED_STATISTICAL_TESTS),
        "accepted_inputs": {
            "target": "usually numeric target required",
            "group_by": "required for group-based tests",
            "filters": "supported indirectly through canonical request",
            "alpha": "supported",
            "confidence_level": "supported",
            "desired_power": "supported",
            "feature_columns": "supported for regression_significance",
            "comparison_columns": "supported for chi_square",
        },
        "result_shapes": ["statistical_test"],
    },
    "ml_placeholders": {
        "intent_names": ["predictive", "forecasting"],
        "planner_actions": ["forecast"],
        "accepted_inputs": {
            "target": "required",
            "horizon": "supported for forecasting",
        },
        "result_shapes": ["forecast_result", "training_result", "prediction_result"],
    },
}

RESULT_CONTRACT = {
    "analysis_result_top_level_fields": list(ANALYSIS_RESULT_TOP_LEVEL_FIELDS),
    "analysis_plan_fields": list(ANALYSIS_PLAN_FIELDS),
    "plan_step_fields": list(PLAN_STEP_FIELDS),
    "result_object_fields": list(RESULT_OBJECT_FIELDS),
    "physical_shapes": list(SUPPORTED_RESULT_PHYSICAL_SHAPES),
    "logical_shapes": list(SUPPORTED_RESULT_LOGICAL_SHAPES),
    "result_dtypes": list(SUPPORTED_RESULT_DTYPES),
    "schema_column_dtypes": list(SUPPORTED_SCHEMA_COLUMN_DTYPES),
    "pagination_fields": list(PAGINATION_FIELDS),
    "status_values": ["ok", "clarify", "refuse"],
    "reasoning_fields": ["summary", "deterministic_summary", "llm_summary", "summary_source"],
    "execution_fields": ["status", "tool_families", "rationale", "step_count", "steps"],
    "interpretation_fields": [
        "intent_name",
        "task_type",
        "target",
        "aggregation",
        "group_by",
        "filters",
        "time_reference",
        "horizon",
        "options",
    ],
}

LLM_INTENT_PROMPT_CONTRACT = {
    "allowed_status_values": ["ready", "clarify", "refuse"],
    "return_keys": [
        "status",
        "candidate_capabilities",
        "task_type_hint",
        "target",
        "aggregation",
        "horizon",
        "filters",
        "group_by",
        "time_reference",
        "message",
        "warnings",
    ],
    "routing_rules": [
        "Do not invent columns.",
        "If possible, return candidate_capabilities using SAIDA capability-like labels such as ranking, trend, comparative, segmentation, verification, tabular, metadata, significance_inference, top_n_by_metric, grouped_breakdown, period_over_period_comparison, tabular_record_retrieval, null_verification, or forecast_series.",
        "If uncertain, use clarify or refuse.",
        "If a request is supported but underspecified, prefer status=ready and leave unsupported fields null so deterministic normalization can finish the routing.",
        "Do not refuse a supported tabular request just because it is not an aggregation.",
        "For prompts about least or most represented groups, prefer grouped row-count interpretations when a dimension column is present.",
        "For prompts about available columns, return ready instead of clarification.",
    ],
}

LLM_RESPONSE_PROMPT_CONTRACT = {
    "allowed_status_values": ["ready", "refuse"],
    "return_keys": ["status", "summary", "message", "warnings"],
    "grounding_rules": [
        "Do not invent metrics or facts.",
        "Use the deterministic summary and metric payload only.",
    ],
}


def get_capability_contract() -> dict[str, Any]:
    """Return a deep-copied view of the current live capability contract."""
    return deepcopy(
        {
            "input_surface": INPUT_SURFACE,
            "intent_families": INTENT_FAMILIES,
            "result_contract": RESULT_CONTRACT,
            "llm_intent_prompt_contract": LLM_INTENT_PROMPT_CONTRACT,
            "llm_response_prompt_contract": LLM_RESPONSE_PROMPT_CONTRACT,
        }
    )


def build_intent_capability_summary() -> str:
    """Build a compact provider-facing summary of deterministic capabilities."""
    family_descriptions = [
        "row counts and grouped row counts for representation questions",
        "metadata inventory for columns, types, missingness, identifiers, and high-cardinality fields",
        "scalar aggregations and grouped aggregations",
        "time coverage, time buckets, trends, and period comparisons",
        "boolean verification checks",
        "ranked row and ranked group retrieval",
        "tabular query workflows including filtered row retrieval, selected columns, sorting, limits, grouped table outputs, and pagination-friendly requests for recordset retrieval",
        "deterministic statistical workflows",
    ]
    return "Supported deterministic capability families include " + "; ".join(family_descriptions) + "."


def build_intent_prompt_contract_text() -> str:
    """Build prompt text from the current capability contract for LLM intent routing."""
    rules = " ".join(LLM_INTENT_PROMPT_CONTRACT["routing_rules"])
    return_keys = ", ".join(LLM_INTENT_PROMPT_CONTRACT["return_keys"])
    statuses = ", ".join(f'"{value}"' for value in LLM_INTENT_PROMPT_CONTRACT["allowed_status_values"])
    return (
        f"Allowed status values: {statuses}.\n"
        f"{build_intent_capability_summary()}\n"
        "Requests for rows, records, tables, or tickets can be supported when they map to deterministic tabular querying.\n"
        f"{rules}\n"
        f"Return keys: {return_keys}.\n"
    )


def build_response_contract_text() -> str:
    """Build prompt text from the current result contract for LLM response generation."""
    statuses = ", ".join(f'"{value}"' for value in LLM_RESPONSE_PROMPT_CONTRACT["allowed_status_values"])
    return_keys = ", ".join(LLM_RESPONSE_PROMPT_CONTRACT["return_keys"])
    grounding_rules = " ".join(LLM_RESPONSE_PROMPT_CONTRACT["grounding_rules"])
    result_fields = ", ".join(RESULT_OBJECT_FIELDS)
    top_level_fields = ", ".join(ANALYSIS_RESULT_TOP_LEVEL_FIELDS)
    return (
        f"Allowed status values: {statuses}.\n"
        f"{grounding_rules}\n"
        f"The current standardized response envelope fields are: {top_level_fields}.\n"
        f"The current self-describing result object fields are: {result_fields}.\n"
        f"Return keys: {return_keys}.\n"
    )
