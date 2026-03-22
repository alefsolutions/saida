"""Executable prompt family catalog and invariants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from saida.core.contracts import AnalysisPlan, AnalysisRequest

PromptFamilyGovernance = Literal["governed", "partial", "legacy"]


@dataclass(slots=True)
class PromptFamilySpec:
    """Describe one supported prompt family and its expected invariants."""

    family_id: str
    label: str
    description: str
    intent_names: tuple[str, ...] = ()
    required_parameters: tuple[str, ...] = ()
    option_requirements: dict[str, Any] = field(default_factory=dict)
    primary_result_shapes: tuple[str, ...] = ()
    allowed_plan_actions: tuple[str, ...] = ()
    forbidden_primary_results: tuple[str, ...] = ()
    governance: PromptFamilyGovernance = "governed"
    examples: tuple[str, ...] = ()

    def request_invariant_issues(self, request: AnalysisRequest) -> list[str]:
        """Return request-level invariant mismatches for this family."""

        issues: list[str] = []
        if self.intent_names and request.intent_name not in set(self.intent_names):
            issues.append(
                f"Expected intent_name in {list(self.intent_names)}, received {request.intent_name!r}."
            )
        for parameter_name in self.required_parameters:
            if not _request_parameter_is_resolved(request, parameter_name):
                issues.append(f"Missing required parameter {parameter_name!r} for family {self.family_id!r}.")
        for option_name, expected_value in self.option_requirements.items():
            if request.options.get(option_name) != expected_value:
                issues.append(
                    f"Expected option {option_name!r}={expected_value!r}, "
                    f"received {request.options.get(option_name)!r}."
                )
        return issues

    def plan_invariant_issues(self, plan: AnalysisPlan) -> list[str]:
        """Return plan-level invariant mismatches for this family."""

        if not self.allowed_plan_actions:
            return []
        actions = [step.action for step in plan.steps]
        if not any(action in set(self.allowed_plan_actions) for action in actions):
            return [
                f"Expected at least one plan action in {list(self.allowed_plan_actions)}, received {actions}."
            ]
        unexpected_actions = [action for action in actions if action not in set(self.allowed_plan_actions)]
        if unexpected_actions:
            return [f"Unexpected plan actions for family {self.family_id!r}: {unexpected_actions}."]
        return []

    def result_invariant_issues(self, primary_result: dict[str, Any] | None) -> list[str]:
        """Return primary-result invariant mismatches for this family."""

        if primary_result is None:
            return []
        issues: list[str] = []
        logical_shape = primary_result.get("logical_shape")
        result_name = primary_result.get("name")
        if self.primary_result_shapes and logical_shape not in set(self.primary_result_shapes):
            issues.append(
                f"Expected logical_shape in {list(self.primary_result_shapes)}, received {logical_shape!r}."
            )
        if self.forbidden_primary_results and result_name in set(self.forbidden_primary_results):
            issues.append(f"Primary result {result_name!r} is forbidden for family {self.family_id!r}.")
        return issues

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe summary of the family spec."""

        return {
            "family_id": self.family_id,
            "label": self.label,
            "description": self.description,
            "intent_names": list(self.intent_names),
            "required_parameters": list(self.required_parameters),
            "option_requirements": dict(self.option_requirements),
            "primary_result_shapes": list(self.primary_result_shapes),
            "allowed_plan_actions": list(self.allowed_plan_actions),
            "forbidden_primary_results": list(self.forbidden_primary_results),
            "governance": self.governance,
            "examples": list(self.examples),
        }


@dataclass(slots=True)
class PromptFamilyCatalog:
    """Registry of executable prompt family specs."""

    families: dict[str, PromptFamilySpec] = field(default_factory=dict)

    def add_family(self, spec: PromptFamilySpec) -> None:
        self.families[spec.family_id] = spec

    def get(self, family_id: str | None) -> PromptFamilySpec | None:
        if family_id is None:
            return None
        return self.families.get(family_id)

    def derive_family(self, request: AnalysisRequest) -> str | None:
        return derive_prompt_family(request, self)

    def to_dict(self) -> dict[str, Any]:
        return {family_id: spec.to_dict() for family_id, spec in self.families.items()}

    def to_markdown(self) -> str:
        """Render a stable markdown catalog snapshot."""

        lines = [
            "# Prompt Family Catalog",
            "",
            "This file is a human-readable snapshot of the live prompt family catalog in `src/saida/core/prompt_family_catalog.py`.",
            "",
            "| Family | Governance | Intents | Required Parameters | Primary Result Shapes | Plan Actions | Forbidden Primary Results |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for spec in sorted(self.families.values(), key=lambda item: item.family_id):
            intents = ", ".join(spec.intent_names) or "-"
            required_parameters = ", ".join(spec.required_parameters) or "-"
            result_shapes = ", ".join(spec.primary_result_shapes) or "-"
            plan_actions = ", ".join(spec.allowed_plan_actions) or "-"
            forbidden_results = ", ".join(spec.forbidden_primary_results) or "-"
            lines.append(
                f"| `{spec.family_id}` | `{spec.governance}` | {intents} | "
                f"{required_parameters} | {result_shapes} | {plan_actions} | {forbidden_results} |"
            )
        lines.extend(
            [
                "",
                "## Notes",
                "",
                "- `governed`: family has a stable explicit intent surface and defined invariants.",
                "- `partial`: family is explicit, but some plan or result behavior still relies on legacy branching.",
                "- `legacy`: family exists mainly to expose non-governed fallback behavior while migration continues.",
            ]
        )
        return "\n".join(lines) + "\n"


_METADATA_INTENT_TO_FAMILY = {
    "column_inventory": "column_inventory",
    "numeric_column_inventory": "numeric_column_inventory",
    "categorical_column_inventory": "categorical_column_inventory",
    "measure_inventory": "measure_inventory",
    "dimension_inventory": "dimension_inventory",
    "time_column_inventory": "time_column_inventory",
    "missing_value_inventory": "missing_value_inventory",
    "identifier_inventory": "identifier_inventory",
    "high_cardinality_inventory": "high_cardinality_inventory",
}

_STATISTICAL_TEST_TO_FAMILY = {
    "significance_inference": "significance_inference",
    "confidence_interval": "confidence_interval",
    "power_analysis": "power_analysis",
    "sample_size_estimate": "sample_size_estimate",
    "t_test": "t_test",
    "anova": "anova",
    "mann_whitney": "mann_whitney",
    "regression_significance": "regression_significance",
    "chi_square": "chi_square",
}

_EXISTENCE_MODE_TO_FAMILY = {
    "column_presence_check": "column_presence_check",
    "column_property_check": "column_property_check",
    "null_check": "null_verification",
    "threshold_check": "threshold_verification",
    "time_value": "time_value_verification",
}


def build_default_prompt_family_catalog() -> PromptFamilyCatalog:
    """Build the live prompt family catalog for the current SAIDA surface."""

    catalog = PromptFamilyCatalog()

    families = [
        PromptFamilySpec(
            family_id="row_count",
            label="Row Count",
            description="Return the number of rows in the dataset or filtered slice.",
            intent_names=("row_count",),
            primary_result_shapes=("count",),
            allowed_plan_actions=("row_count",),
            examples=("How many rows are there?",),
        ),
        PromptFamilySpec(
            family_id="distinct_value_listing",
            label="Distinct Value Listing",
            description="List distinct values for one dimension with row counts.",
            intent_names=("distinct_values",),
            required_parameters=("target",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("distinct_values",),
            forbidden_primary_results=("numeric_summary",),
            examples=("List all channels.",),
        ),
        PromptFamilySpec(
            family_id="grouped_entity_count",
            label="Grouped Entity Count",
            description="Count rows by one or more grouping dimensions.",
            intent_names=("grouped_tabular_query",),
            required_parameters=("group_by",),
            option_requirements={"intent_name": "grouped_tabular_query"},
            primary_result_shapes=("table",),
            allowed_plan_actions=("grouped_tabular_query",),
            forbidden_primary_results=("numeric_summary",),
            examples=("Give me the total tickets per channel.",),
        ),
        PromptFamilySpec(
            family_id="grouped_metric_table",
            label="Grouped Metric Table",
            description="Aggregate a metric by group and return a grouped table.",
            intent_names=("grouped_tabular_query",),
            required_parameters=("target", "group_by"),
            primary_result_shapes=("table",),
            allowed_plan_actions=("grouped_tabular_query",),
            examples=("Show total revenue by region.",),
        ),
        PromptFamilySpec(
            family_id="tabular_record_retrieval",
            label="Tabular Record Retrieval",
            description="Return rows with selected columns, sorting, and pagination.",
            intent_names=("tabular_query",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("tabular_query",),
            examples=("Show the latest 10 tickets with priority and channel.",),
        ),
        PromptFamilySpec(
            family_id="representation_ranking",
            label="Representation Ranking",
            description="Rank groups by row-count representation.",
            intent_names=("representation_ranking",),
            required_parameters=("target",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("count_rows_by_group",),
            forbidden_primary_results=("numeric_summary",),
            examples=("Which channel has the most tickets?",),
        ),
        PromptFamilySpec(
            family_id="row_ranking",
            label="Row Ranking",
            description="Rank individual rows by a metric.",
            intent_names=("row_ranking",),
            required_parameters=("target",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("ranked_rows",),
            examples=("Which ticket has the highest resolution hours?",),
        ),
        PromptFamilySpec(
            family_id="group_ranking",
            label="Group Ranking",
            description="Rank grouped metric results by a target measure.",
            intent_names=("group_ranking",),
            required_parameters=("target", "group_by"),
            primary_result_shapes=("table",),
            allowed_plan_actions=("ranked_breakdown",),
            examples=("Which region has the highest revenue?",),
        ),
        PromptFamilySpec(
            family_id="column_inventory",
            label="Column Inventory",
            description="List dataset columns.",
            intent_names=("column_inventory",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("column_inventory",),
            examples=("What are the columns in the dataset?",),
        ),
        PromptFamilySpec(
            family_id="column_type_lookup",
            label="Column Type Lookup",
            description="Return the data type for one named column.",
            intent_names=("column_type_inventory",),
            required_parameters=("target",),
            primary_result_shapes=("scalar",),
            allowed_plan_actions=("column_type_inventory",),
            examples=("What is the data type of created_at?",),
        ),
        PromptFamilySpec(
            family_id="column_type_inventory",
            label="Column Type Inventory",
            description="Return data types for all columns.",
            intent_names=("column_type_inventory",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("column_type_inventory",),
            examples=("What are the data types of the fields?",),
        ),
        PromptFamilySpec(
            family_id="numeric_column_inventory",
            label="Numeric Column Inventory",
            description="List numeric columns in the dataset.",
            intent_names=("numeric_column_inventory",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("numeric_column_inventory",),
        ),
        PromptFamilySpec(
            family_id="categorical_column_inventory",
            label="Categorical Column Inventory",
            description="List categorical columns in the dataset.",
            intent_names=("categorical_column_inventory",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("categorical_column_inventory",),
        ),
        PromptFamilySpec(
            family_id="measure_inventory",
            label="Measure Inventory",
            description="List measure columns in the dataset.",
            intent_names=("measure_inventory",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("measure_inventory",),
        ),
        PromptFamilySpec(
            family_id="dimension_inventory",
            label="Dimension Inventory",
            description="List dimension columns in the dataset.",
            intent_names=("dimension_inventory",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("dimension_inventory",),
        ),
        PromptFamilySpec(
            family_id="time_column_inventory",
            label="Time Column Inventory",
            description="List time columns in the dataset.",
            intent_names=("time_column_inventory",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("time_column_inventory",),
        ),
        PromptFamilySpec(
            family_id="missing_value_inventory",
            label="Missing Value Inventory",
            description="List columns with missingness properties.",
            intent_names=("missing_value_inventory",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("missing_value_inventory",),
        ),
        PromptFamilySpec(
            family_id="identifier_inventory",
            label="Identifier Inventory",
            description="List likely identifier columns.",
            intent_names=("identifier_inventory",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("identifier_inventory",),
        ),
        PromptFamilySpec(
            family_id="high_cardinality_inventory",
            label="High Cardinality Inventory",
            description="List high-cardinality columns.",
            intent_names=("high_cardinality_inventory",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("high_cardinality_inventory",),
        ),
        PromptFamilySpec(
            family_id="column_presence_check",
            label="Column Presence Check",
            description="Verify whether a named column exists.",
            intent_names=("existence_check",),
            required_parameters=("requested_column",),
            option_requirements={"existence_mode": "column_presence_check"},
            primary_result_shapes=("verification",),
            allowed_plan_actions=("column_presence_check",),
            examples=("Does the dataset have a created_at column?",),
        ),
        PromptFamilySpec(
            family_id="column_property_check",
            label="Column Property Check",
            description="Verify a property for one named column.",
            intent_names=("existence_check",),
            required_parameters=("requested_column", "expected_property"),
            option_requirements={"existence_mode": "column_property_check"},
            primary_result_shapes=("verification",),
            allowed_plan_actions=("column_property_check",),
            examples=("Is priority a dimension?",),
        ),
        PromptFamilySpec(
            family_id="null_verification",
            label="Null Verification",
            description="Verify whether a target column has or lacks null values.",
            intent_names=("existence_check",),
            required_parameters=("target",),
            option_requirements={"existence_mode": "null_check"},
            primary_result_shapes=("verification",),
            allowed_plan_actions=("null_check",),
        ),
        PromptFamilySpec(
            family_id="threshold_verification",
            label="Threshold Verification",
            description="Verify whether a numeric target meets a threshold condition.",
            intent_names=("existence_check",),
            required_parameters=("target", "threshold_value", "threshold_operator"),
            option_requirements={"existence_mode": "threshold_check"},
            primary_result_shapes=("verification",),
            allowed_plan_actions=("threshold_check",),
        ),
        PromptFamilySpec(
            family_id="time_value_verification",
            label="Time Value Verification",
            description="Verify whether a time value is present in the dataset.",
            intent_names=("existence_check",),
            required_parameters=("target",),
            option_requirements={"existence_mode": "time_value"},
            primary_result_shapes=("verification",),
            allowed_plan_actions=("time_value_exists",),
        ),
        PromptFamilySpec(
            family_id="row_existence_check",
            label="Row Existence Check",
            description="Verify whether any rows satisfy the requested filters.",
            intent_names=("existence_check",),
            option_requirements={"existence_mode": "row_existence"},
            primary_result_shapes=("verification",),
            allowed_plan_actions=("row_existence",),
        ),
        PromptFamilySpec(
            family_id="time_coverage",
            label="Time Coverage",
            description="Return temporal coverage over the dataset.",
            intent_names=("time_coverage",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("time_coverage",),
        ),
        PromptFamilySpec(
            family_id="time_bucket_counts",
            label="Time Bucket Counts",
            description="Count rows by a time bucket.",
            intent_names=("time_bucket_counts",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("count_rows_by_group", "time_bucket_counts"),
            governance="partial",
        ),
        PromptFamilySpec(
            family_id="time_bucket_breakdown",
            label="Time Bucket Breakdown",
            description="Aggregate a metric by time bucket.",
            intent_names=("time_bucket_breakdown",),
            required_parameters=("target",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("time_bucket_breakdown",),
        ),
        PromptFamilySpec(
            family_id="time_period_comparison",
            label="Time Period Comparison",
            description="Compare one metric across adjacent time periods.",
            intent_names=("time_period_comparison",),
            required_parameters=("target", "time_reference"),
            primary_result_shapes=("table",),
            allowed_plan_actions=("period_comparison", "grouped_period_comparison"),
        ),
        PromptFamilySpec(
            family_id="significance_inference",
            label="Significance Inference",
            description="Run a significance inference workflow.",
            intent_names=(),
            required_parameters=("target",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("significance_inference",),
        ),
        PromptFamilySpec(
            family_id="confidence_interval",
            label="Confidence Interval",
            description="Compute a confidence interval for a target metric.",
            intent_names=(),
            required_parameters=("target",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("confidence_interval",),
        ),
        PromptFamilySpec(
            family_id="power_analysis",
            label="Power Analysis",
            description="Estimate statistical power.",
            intent_names=(),
            required_parameters=("target",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("power_analysis",),
        ),
        PromptFamilySpec(
            family_id="sample_size_estimate",
            label="Sample Size Estimate",
            description="Estimate required sample size.",
            intent_names=(),
            required_parameters=("target",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("sample_size_estimate",),
        ),
        PromptFamilySpec(
            family_id="t_test",
            label="T-Test",
            description="Run a deterministic t-test workflow.",
            intent_names=(),
            required_parameters=("target",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("t_test",),
        ),
        PromptFamilySpec(
            family_id="anova",
            label="ANOVA",
            description="Run a deterministic ANOVA workflow.",
            intent_names=(),
            required_parameters=("target",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("anova",),
        ),
        PromptFamilySpec(
            family_id="mann_whitney",
            label="Mann-Whitney",
            description="Run a deterministic Mann-Whitney workflow.",
            intent_names=(),
            required_parameters=("target",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("mann_whitney",),
        ),
        PromptFamilySpec(
            family_id="regression_significance",
            label="Regression Significance",
            description="Run a regression-significance workflow.",
            intent_names=(),
            required_parameters=("target",),
            primary_result_shapes=("table",),
            allowed_plan_actions=("regression_significance",),
        ),
        PromptFamilySpec(
            family_id="chi_square",
            label="Chi-Square",
            description="Run a chi-square workflow.",
            intent_names=(),
            required_parameters=("target", "group_by"),
            primary_result_shapes=("table",),
            allowed_plan_actions=("chi_square",),
        ),
        PromptFamilySpec(
            family_id="metric_aggregate",
            label="Metric Aggregate",
            description="Return a scalar aggregate value for one target metric.",
            intent_names=(),
            required_parameters=("target",),
            primary_result_shapes=("aggregate", "count"),
            governance="partial",
            examples=("What is the average resolution_hours?",),
        ),
        PromptFamilySpec(
            family_id="legacy_metric_overview",
            label="Legacy Metric Overview",
            description="Legacy descriptive fallback for metric-oriented prompts without a governed family.",
            intent_names=(),
            required_parameters=("target",),
            governance="legacy",
            examples=("Show revenue.",),
        ),
    ]

    for family in families:
        catalog.add_family(family)

    return catalog


def get_prompt_family_catalog() -> PromptFamilyCatalog:
    """Return a fresh prompt family catalog."""

    return build_default_prompt_family_catalog()


def derive_prompt_family(
    request: AnalysisRequest,
    catalog: PromptFamilyCatalog | None = None,
) -> str | None:
    """Derive the prompt family id from a normalized request."""

    _ = catalog
    statistical_test = request.options.get("statistical_test")
    if isinstance(statistical_test, str) and statistical_test in _STATISTICAL_TEST_TO_FAMILY:
        return _STATISTICAL_TEST_TO_FAMILY[statistical_test]

    if request.intent_name == "column_type_inventory":
        return "column_type_lookup" if request.target else "column_type_inventory"

    if request.intent_name in _METADATA_INTENT_TO_FAMILY:
        return _METADATA_INTENT_TO_FAMILY[request.intent_name]

    if request.intent_name == "row_count":
        return "row_count"
    if request.intent_name == "distinct_values":
        return "distinct_value_listing"
    if request.intent_name == "representation_ranking":
        return "representation_ranking"
    if request.intent_name == "row_ranking":
        return "row_ranking"
    if request.intent_name == "group_ranking":
        return "group_ranking"
    if request.intent_name == "tabular_query":
        return "tabular_record_retrieval"
    if request.intent_name == "grouped_tabular_query":
        if request.group_by and request.target is None and request.aggregation == "count":
            return "grouped_entity_count"
        return "grouped_metric_table"
    if request.intent_name == "time_coverage":
        return "time_coverage"
    if request.intent_name == "time_bucket_counts":
        return "time_bucket_counts"
    if request.intent_name == "time_bucket_breakdown":
        return "time_bucket_breakdown"
    if request.intent_name == "time_period_comparison":
        return "time_period_comparison"
    if request.intent_name == "existence_check":
        existence_mode = request.options.get("existence_mode")
        if isinstance(existence_mode, str):
            return _EXISTENCE_MODE_TO_FAMILY.get(existence_mode, "row_existence_check")
        return "row_existence_check"
    if request.target and request.aggregation and not request.group_by:
        return "metric_aggregate"
    if request.target and not request.group_by and request.task_type_hint in {"descriptive", "diagnostic"}:
        return "legacy_metric_overview"
    return None


def _request_parameter_is_resolved(request: AnalysisRequest, parameter_name: str) -> bool:
    if parameter_name == "target":
        return bool(request.target)
    if parameter_name == "group_by":
        return bool(request.group_by)
    if parameter_name == "time_reference":
        return bool(request.time_reference)
    if parameter_name == "requested_column":
        return bool(request.options.get("requested_column") or request.target)
    if parameter_name == "expected_property":
        return bool(request.options.get("expected_property"))
    if parameter_name == "threshold_value":
        return request.options.get("threshold_value") is not None
    if parameter_name == "threshold_operator":
        return bool(request.options.get("threshold_operator"))
    return request.options.get(parameter_name) is not None
