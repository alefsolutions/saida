"""Structured planning from canonicalized requests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from saida.core.analytics_registry import get_analytics_registry
from saida.exceptions import PlanningError
from saida.core.contracts import AnalysisPlan, AnalysisRequest, DatasetProfile, PlanStep, SourceContext
from saida.plan_generation.prompt_family_catalog import derive_prompt_family, get_prompt_family_catalog

if TYPE_CHECKING:
    from saida.plan_generation.prompt_capability_contract import PromptCapabilityContract


_PROMPT_FAMILY_TO_INTENT = {
    "row_count": "row_count",
    "distinct_value_count": "distinct_value_count",
    "distinct_value_listing": "distinct_values",
    "representation_ranking": "representation_ranking",
    "row_ranking": "row_ranking",
    "group_ranking": "group_ranking",
    "column_count": "column_count",
    "column_inventory": "column_inventory",
    "column_type_lookup": "column_type_inventory",
    "column_type_inventory": "column_type_inventory",
    "numeric_column_count": "numeric_column_count",
    "numeric_column_inventory": "numeric_column_inventory",
    "categorical_column_count": "categorical_column_count",
    "categorical_column_inventory": "categorical_column_inventory",
    "measure_count": "measure_count",
    "measure_inventory": "measure_inventory",
    "dimension_count": "dimension_count",
    "dimension_inventory": "dimension_inventory",
    "time_column_count": "time_column_count",
    "time_column_inventory": "time_column_inventory",
    "missing_value_inventory": "missing_value_inventory",
    "identifier_count": "identifier_count",
    "identifier_inventory": "identifier_inventory",
    "high_cardinality_count": "high_cardinality_count",
    "high_cardinality_inventory": "high_cardinality_inventory",
    "column_presence_check": "existence_check",
    "column_property_check": "existence_check",
    "null_verification": "existence_check",
    "threshold_verification": "existence_check",
    "time_value_verification": "existence_check",
    "row_existence_check": "existence_check",
    "time_coverage": "time_coverage",
    "time_bucket_counts": "time_bucket_counts",
    "time_bucket_breakdown": "time_bucket_breakdown",
    "time_period_comparison": "time_period_comparison",
    "tabular_record_retrieval": "tabular_query",
    "grouped_entity_count": "grouped_tabular_query",
    "grouped_metric_table": "grouped_tabular_query",
}

_PROMPT_FAMILY_TO_EXISTENCE_MODE = {
    "column_presence_check": "column_presence_check",
    "column_property_check": "column_property_check",
    "null_verification": "null_check",
    "threshold_verification": "threshold_check",
    "time_value_verification": "time_value",
    "row_existence_check": "row_existence",
}

_STATISTICAL_PROMPT_FAMILIES = {
    "significance_inference",
    "confidence_interval",
    "power_analysis",
    "sample_size_estimate",
    "t_test",
    "anova",
    "mann_whitney",
    "regression_significance",
    "chi_square",
}

_METADATA_PROMPT_FAMILY_TO_ACTION = {
    "column_count": "column_count",
    "column_inventory": "column_inventory",
    "column_type_lookup": "column_type_inventory",
    "column_type_inventory": "column_type_inventory",
    "numeric_column_count": "numeric_column_count",
    "numeric_column_inventory": "numeric_column_inventory",
    "categorical_column_count": "categorical_column_count",
    "categorical_column_inventory": "categorical_column_inventory",
    "measure_count": "measure_count",
    "measure_inventory": "measure_inventory",
    "dimension_count": "dimension_count",
    "dimension_inventory": "dimension_inventory",
    "time_column_count": "time_column_count",
    "time_column_inventory": "time_column_inventory",
    "missing_value_inventory": "missing_value_inventory",
    "identifier_count": "identifier_count",
    "identifier_inventory": "identifier_inventory",
    "high_cardinality_count": "high_cardinality_count",
    "high_cardinality_inventory": "high_cardinality_inventory",
}


class PlanBuilder:
    """Create executable analytical plans from canonical requests."""

    def build_plan_from_contract(
        self,
        contract: PromptCapabilityContract,
        request: AnalysisRequest,
        profile: DatasetProfile,
        context: SourceContext | None = None,
    ) -> AnalysisPlan:
        """Compile a plan through the prompt capability contract layer."""

        if contract.status == "unsupported_capability":
            raise PlanningError("Prompt capability contract resolved to an unsupported capability.")
        if contract.status in {"supported_but_data_infeasible", "supported_but_data_insufficient"}:
            raise PlanningError("Prompt capability contract failed data feasibility checks.")
        if request.prompt_family is None:
            request.prompt_family = contract.prompt_family or derive_prompt_family(request)
        plan = self.build_plan(request, profile, context)
        prompt_family = request.prompt_family or contract.prompt_family
        if prompt_family:
            self._validate_family_plan(prompt_family, plan)
        return plan

    def build_plan(
        self,
        request: AnalysisRequest,
        profile: DatasetProfile,
        context: SourceContext | None = None,
    ) -> AnalysisPlan:
        """Build an executable plan from the request and profile."""
        self._validate_request(request, profile)
        if request.prompt_family is None:
            request.prompt_family = derive_prompt_family(request)
        task_type = request.task_type_hint or "descriptive"
        warnings: list[str] = []
        family_plan = self._build_plan_for_prompt_family(request, profile, context, task_type, warnings)
        if family_plan is not None:
            return family_plan

        if task_type in {"descriptive", "diagnostic", "statistical"}:
            raise PlanningError("The request did not resolve to a safe supported prompt family.")

        if task_type == "forecasting":
            if not profile.time_columns:
                raise PlanningError("Forecasting requires a datetime column.")
            if request.target is None:
                raise PlanningError("Forecasting requires a target metric.")
            steps = [
                PlanStep(
                    step_id="forecast",
                    tool_family="ml",
                    action="forecast",
                    parameters={"target": request.target, "time_column": profile.time_columns[0], "horizon": request.horizon or 3},
                    description="Generate a forecast for the requested target.",
                )
            ]
            rationale = self._build_rationale(task_type, request, context)
            return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)

        if task_type == "predictive":
            warnings.append("Predictive model training is not implemented yet.")

        rationale = self._build_rationale(task_type, request, context)
        return AnalysisPlan(task_type=task_type, rationale=rationale, steps=[], warnings=warnings)

    def _build_plan_for_prompt_family(
        self,
        request: AnalysisRequest,
        profile: DatasetProfile,
        context: SourceContext | None,
        task_type: str,
        warnings: list[str],
    ) -> AnalysisPlan | None:
        prompt_family = request.prompt_family
        if not prompt_family:
            return None
        family_spec = get_prompt_family_catalog().get(prompt_family)
        if family_spec is not None and family_spec.plan_steps:
            steps = family_spec.compile_steps(request, profile)
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family == "metric_aggregate":
            steps = self._build_metric_overview_steps(request, profile, task_type, include_aggregate_step=True)
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family == "exploratory_metric_overview":
            steps = self._build_metric_overview_steps(request, profile, task_type, include_aggregate_step=False)
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family in _STATISTICAL_PROMPT_FAMILIES:
            steps = [
                PlanStep(
                    step_id=prompt_family,
                    tool_family="stats",
                    action=prompt_family,
                    parameters={
                        "target": request.target,
                        "group_by": request.group_by,
                        "filters": request.filters,
                        "alpha": request.options.get("alpha", 0.05),
                        "confidence_level": request.options.get("confidence_level", 0.95),
                        "desired_power": request.options.get("desired_power", 0.80),
                        "feature_columns": request.options.get("feature_columns", []),
                        "comparison_columns": request.options.get("comparison_columns", []),
                    },
                    description=f"Run the deterministic {prompt_family} workflow selected from the prompt family.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family in _METADATA_PROMPT_FAMILY_TO_ACTION:
            action = _METADATA_PROMPT_FAMILY_TO_ACTION[prompt_family]
            steps = [
                PlanStep(
                    step_id=action,
                    tool_family="metadata",
                    action=action,
                    parameters={"target": request.target},
                    description="Return dataset inventory information for the requested metadata family.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family == "time_coverage":
            steps = [
                PlanStep(
                    step_id="time_coverage",
                    tool_family="duckdb",
                    action="time_coverage",
                    parameters={
                        "time_column": profile.time_columns[0],
                        "filters": request.filters,
                        "mode": request.options.get("time_coverage_mode", "years_present"),
                    },
                    description="Inspect time coverage in the dataset without treating the datetime column as a metric.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family == "time_bucket_counts":
            steps = [
                PlanStep(
                    step_id="time_bucket_counts",
                    tool_family="duckdb",
                    action="time_bucket_counts",
                    parameters={
                        "time_column": profile.time_columns[0],
                        "filters": request.filters,
                        "bucket": request.options.get("time_bucket", "year"),
                    },
                    description="Count rows across derived time buckets such as years or months.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family == "time_bucket_breakdown":
            steps = [
                PlanStep(
                    step_id="time_bucket_breakdown",
                    tool_family="duckdb",
                    action="time_bucket_breakdown",
                    parameters={
                        "target": request.target,
                        "time_column": profile.time_columns[0],
                        "bucket": request.options.get("time_bucket", "month"),
                        "aggregation": request.aggregation or "sum",
                        "group_by": request.group_by,
                        "filters": request.filters,
                    },
                    description="Aggregate a numeric target across derived time buckets such as month, quarter, or year.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family == "time_period_comparison":
            comparison_action = "grouped_period_comparison" if request.group_by else "period_comparison"
            steps = [
                PlanStep(
                    step_id=comparison_action,
                    tool_family="duckdb",
                    action=comparison_action,
                    parameters={
                        "target": request.target,
                        "group_by": request.group_by,
                        "time_column": profile.time_columns[0],
                        "time_reference": request.time_reference,
                        "bucket": request.options.get("time_bucket", "month"),
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                    },
                    description="Compare adjacent derived time periods such as month, quarter, or year.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family in {
            "column_presence_check",
            "column_property_check",
            "null_verification",
            "threshold_verification",
            "time_value_verification",
            "row_existence_check",
        }:
            return self._build_existence_family_plan(request, profile, context, task_type, warnings, prompt_family)

        if prompt_family == "grouped_metric_table":
            steps = [
                PlanStep(
                    step_id="grouped_tabular_query",
                    tool_family="duckdb",
                    action="grouped_tabular_query",
                    parameters={
                        "target": request.target,
                        "group_by": request.group_by,
                        "aggregation": request.aggregation or ("count" if request.target is None else "sum"),
                        "filters": request.filters,
                        "sort_by": request.options.get("sort_by"),
                        "sort_direction": request.options.get("sort_direction", "desc"),
                        "limit": request.options.get("limit"),
                        "page": request.options.get("page", 1),
                        "page_size": request.options.get("page_size", 50),
                    },
                    description="Return a grouped, tabular dataset slice for discovery-style analysis.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family == "row_ranking" and request.target:
            steps = [
                PlanStep(
                    step_id="ranked_rows",
                    tool_family="duckdb",
                    action="ranked_rows",
                    parameters={
                        "target": request.target,
                        "filters": request.filters,
                        "ascending": request.options.get("ranking_direction") == "asc",
                        "limit": int(request.options.get("ranking_limit", 5)),
                    },
                    description="Rank individual rows by the requested numeric target.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family == "group_ranking" and request.target and request.group_by:
            steps = [
                PlanStep(
                    step_id="ranked_breakdown",
                    tool_family="duckdb",
                    action="ranked_breakdown",
                    parameters={
                        "target": request.target,
                        "group_by": request.group_by,
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                        "limit": int(request.options.get("ranking_limit", 5)),
                        "ascending": request.options.get("ranking_direction") == "asc",
                    },
                    description="Rank grouped results according to the requested top or bottom limit.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        return None

    def _build_metric_overview_steps(
        self,
        request: AnalysisRequest,
        profile: DatasetProfile,
        task_type: str,
        *,
        include_aggregate_step: bool,
    ) -> list[PlanStep]:
        if request.target is None or request.target not in set(profile.measure_columns):
            raise PlanningError("Exploratory metric workflows require a numeric target.")

        steps: list[PlanStep] = []
        if include_aggregate_step and request.aggregation:
            steps.append(
                PlanStep(
                    step_id="aggregate_value",
                    tool_family="duckdb",
                    action="aggregate_value",
                    parameters={
                        "target": request.target,
                        "aggregation": request.aggregation,
                        "filters": request.filters,
                    },
                    description=f"Compute the {request.aggregation} value for the requested target.",
                )
            )

        steps.append(
            PlanStep(
                step_id="summary_metrics",
                tool_family="duckdb",
                action="dataset_summary",
                parameters={"target": request.target, "filters": request.filters},
                description="Compute top-level dataset metrics.",
            )
        )
        if profile.time_columns:
            steps.append(
                PlanStep(
                    step_id="time_trend",
                    tool_family="duckdb",
                    action="time_trend",
                    parameters={
                        "target": request.target,
                        "time_column": profile.time_columns[0],
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                    },
                    description="Compute the target trend over time.",
                )
            )
        if request.time_reference and profile.time_columns:
            steps.append(
                PlanStep(
                    step_id="period_comparison",
                    tool_family="duckdb",
                    action="period_comparison",
                    parameters={
                        "target": request.target,
                        "time_column": profile.time_columns[0],
                        "time_reference": request.time_reference,
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                    },
                    description="Compare the requested period against the previous comparable period.",
                )
            )
            if request.group_by:
                steps.append(
                    PlanStep(
                        step_id="grouped_period_comparison",
                        tool_family="duckdb",
                        action="grouped_period_comparison",
                        parameters={
                            "target": request.target,
                            "group_by": request.group_by,
                            "time_column": profile.time_columns[0],
                            "time_reference": request.time_reference,
                            "aggregation": request.aggregation or "sum",
                            "filters": request.filters,
                        },
                        description="Compare grouped totals between adjacent periods.",
                    )
                )
        if request.group_by:
            steps.append(
                PlanStep(
                    step_id="group_breakdown",
                    tool_family="duckdb",
                    action="group_breakdown",
                    parameters={
                        "target": request.target,
                        "group_by": request.group_by,
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                    },
                    description="Break down the target metric by requested dimensions.",
                )
            )
            steps.append(
                PlanStep(
                    step_id="ranked_breakdown",
                    tool_family="duckdb",
                    action="ranked_breakdown",
                    parameters={
                        "target": request.target,
                        "group_by": request.group_by,
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                        "limit": 5,
                    },
                    description="Rank the largest grouped contributors.",
                )
            )
            if request.time_reference and profile.time_columns:
                steps.append(
                    PlanStep(
                        step_id="top_movers",
                        tool_family="duckdb",
                        action="top_movers",
                        parameters={
                            "target": request.target,
                            "group_by": request.group_by,
                            "time_column": profile.time_columns[0],
                            "time_reference": request.time_reference,
                            "aggregation": request.aggregation or "sum",
                            "filters": request.filters,
                            "limit": 5,
                        },
                        description="Identify the largest grouped movers between adjacent periods.",
                    )
                )
        elif task_type == "diagnostic" and profile.dimension_columns:
            steps.append(
                PlanStep(
                    step_id="top_dimension_breakdown",
                    tool_family="duckdb",
                    action="group_breakdown",
                    parameters={
                        "target": request.target,
                        "group_by": [profile.dimension_columns[0]],
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                    },
                    description="Break down the target metric by the leading dimension candidate.",
                )
            )
            steps.append(
                PlanStep(
                    step_id="top_dimension_ranking",
                    tool_family="duckdb",
                    action="ranked_breakdown",
                    parameters={
                        "target": request.target,
                        "group_by": [profile.dimension_columns[0]],
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                        "limit": 5,
                    },
                    description="Rank the leading grouped contributors for the diagnostic workflow.",
                )
            )
            if request.time_reference and profile.time_columns:
                steps.append(
                    PlanStep(
                        step_id="top_dimension_movers",
                        tool_family="duckdb",
                        action="top_movers",
                        parameters={
                            "target": request.target,
                            "group_by": [profile.dimension_columns[0]],
                            "time_column": profile.time_columns[0],
                            "time_reference": request.time_reference,
                            "aggregation": request.aggregation or "sum",
                            "filters": request.filters,
                            "limit": 5,
                        },
                        description="Identify the largest movers for the leading dimension candidate.",
                    )
                )
        if task_type == "diagnostic" and profile.dimension_columns:
            steps.append(
                PlanStep(
                    step_id="contribution_breakdown",
                    tool_family="duckdb",
                    action="contribution_breakdown",
                    parameters={
                        "target": request.target,
                        "group_by": request.group_by or [profile.dimension_columns[0]],
                        "time_column": profile.time_columns[0] if profile.time_columns else None,
                        "time_reference": request.time_reference,
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                    },
                    description="Estimate group-level contribution changes for the diagnostic workflow.",
                )
            )
        steps.append(
            PlanStep(
                step_id="missingness_summary",
                tool_family="stats",
                action="missingness_summary",
                parameters={},
                description="Summarize missing values by column.",
            )
        )
        steps.append(
            PlanStep(
                step_id="numeric_summary",
                tool_family="stats",
                action="numeric_summary",
                parameters={},
                description="Summarize numeric columns with deterministic statistics.",
            )
        )
        steps.append(
            PlanStep(
                step_id="distribution_summary",
                tool_family="stats",
                action="distribution_summary",
                parameters={"target": request.target},
                description="Summarize the target distribution.",
            )
        )
        steps.append(
            PlanStep(
                step_id="target_correlation",
                tool_family="stats",
                action="target_correlation",
                parameters={"target": request.target},
                description="Measure correlations between the target and other numeric columns.",
            )
        )
        steps.append(
            PlanStep(
                step_id="anomaly_summary",
                tool_family="stats",
                action="anomaly_summary",
                parameters={
                    "target": request.target,
                    "time_column": profile.time_columns[0] if profile.time_columns else None,
                },
                description="Flag simple anomaly candidates for the target.",
            )
        )
        if profile.time_columns:
            steps.append(
                PlanStep(
                    step_id="time_series_diagnostics",
                    tool_family="stats",
                    action="time_series_diagnostics",
                    parameters={"target": request.target, "time_column": profile.time_columns[0]},
                    description="Compute simple time-series diagnostics for the target.",
                )
            )
        candidate_dimensions = request.group_by or profile.dimension_columns
        comparison_dimension = [column for column in candidate_dimensions if column != request.target][:1]
        if comparison_dimension:
            steps.append(
                PlanStep(
                    step_id="group_mean_comparison",
                    tool_family="stats",
                    action="group_mean_comparison",
                    parameters={"target": request.target, "group_column": comparison_dimension[0]},
                    description="Compare the target mean across the first available grouping dimension.",
                )
            )
        return steps

    def _build_existence_family_plan(
        self,
        request: AnalysisRequest,
        profile: DatasetProfile,
        context: SourceContext | None,
        task_type: str,
        warnings: list[str],
        prompt_family: str,
    ) -> AnalysisPlan:
        if prompt_family == "time_value_verification":
            steps = [
                PlanStep(
                    step_id="time_value_exists",
                    tool_family="duckdb",
                    action="time_value_exists",
                    parameters={
                        "time_column": request.target or profile.time_columns[0],
                        "filters": request.filters,
                        "expected_year": request.options.get("expected_year"),
                        "time_reference": request.time_reference,
                    },
                    description="Verify whether the requested time value exists in the dataset.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)
        if prompt_family == "null_verification":
            steps = [
                PlanStep(
                    step_id="null_check",
                    tool_family="duckdb",
                    action="null_check",
                    parameters={
                        "target": request.target,
                        "filters": request.filters,
                        "null_expectation": request.options.get("null_expectation", "has_nulls"),
                    },
                    description="Verify whether the requested column has missing values or is complete.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)
        if prompt_family == "threshold_verification":
            steps = [
                PlanStep(
                    step_id="threshold_check",
                    tool_family="duckdb",
                    action="threshold_check",
                    parameters={
                        "target": request.target,
                        "filters": request.filters,
                        "threshold_operator": request.options.get("threshold_operator"),
                        "threshold_value": request.options.get("threshold_value"),
                        "lower_bound": request.options.get("lower_bound"),
                        "upper_bound": request.options.get("upper_bound"),
                    },
                    description="Verify whether the requested numeric threshold condition is present in the data.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)
        if prompt_family == "column_property_check":
            steps = [
                PlanStep(
                    step_id="column_property_check",
                    tool_family="metadata",
                    action="column_property_check",
                    parameters={
                        "target": request.target,
                        "expected_property": request.options.get("expected_property"),
                    },
                    description="Verify whether the requested column has the expected schema property.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)
        if prompt_family == "column_presence_check":
            steps = [
                PlanStep(
                    step_id="column_presence_check",
                    tool_family="metadata",
                    action="column_presence_check",
                    parameters={
                        "requested_column": request.options.get("requested_column"),
                    },
                    description="Verify whether the requested column exists in the dataset schema.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        steps = [
            PlanStep(
                step_id="row_existence",
                tool_family="duckdb",
                action="row_existence",
                parameters={"filters": request.filters or {}},
                description="Verify whether any rows match the requested filters.",
            )
        ]
        return self._finalize_plan(task_type, request, context, steps, warnings)

    def _finalize_plan(
        self,
        task_type: str,
        request: AnalysisRequest,
        context: SourceContext | None,
        steps: list[PlanStep],
        warnings: list[str],
    ) -> AnalysisPlan:
        normalized_steps = [self._normalize_step_parameters(step) for step in steps]
        rationale = self._build_rationale(task_type, request, context)
        plan = AnalysisPlan(task_type=task_type, rationale=rationale, steps=normalized_steps, warnings=list(warnings))
        if request.prompt_family:
            self._validate_family_plan(request.prompt_family, plan)
        return plan

    def _normalize_step_parameters(self, step: PlanStep) -> PlanStep:
        method_id = step.method_id or step.action
        method_spec = get_analytics_registry().get_method(method_id)
        if method_spec is None:
            return step
        supported_parameters = {
            value
            for value in (*method_spec.required_inputs, *method_spec.allowed_configs)
            if value != "dataset"
        }
        step.parameters = {
            name: value
            for name, value in step.parameters.items()
            if name in supported_parameters and value is not None
        }
        return step

    def _validate_family_plan(self, prompt_family: str, plan: AnalysisPlan) -> None:
        family_spec = get_prompt_family_catalog().get(prompt_family)
        if family_spec is None:
            return
        issues = family_spec.plan_invariant_issues(plan)
        if not issues:
            return
        if family_spec.governance == "governed":
            raise PlanningError(f"Prompt family {prompt_family!r} produced an invalid plan: {' '.join(issues)}")
        plan.warnings.extend(issues)

    def validate(self, plan: AnalysisPlan) -> None:
        """Validate a plan before execution."""
        if not plan.steps:
            raise PlanningError("Analysis plan contains no executable steps.")

    def _validate_request(self, request: AnalysisRequest, profile: DatasetProfile) -> None:
        supported_tasks = {"descriptive", "diagnostic", "statistical", "predictive", "forecasting"}
        supported_aggregations = {"sum", "mean", "max", "min", "count"}
        task_type = request.task_type_hint or "descriptive"
        prompt_family = request.prompt_family or derive_prompt_family(request)
        effective_intent_name = request.intent_name or _PROMPT_FAMILY_TO_INTENT.get(prompt_family)
        effective_existence_mode = request.options.get("existence_mode") or _PROMPT_FAMILY_TO_EXISTENCE_MODE.get(prompt_family, "filtered_rows")
        effective_statistical_test = request.options.get("statistical_test")
        if effective_statistical_test is None and prompt_family in _STATISTICAL_PROMPT_FAMILIES:
            effective_statistical_test = prompt_family
        if task_type not in supported_tasks:
            raise PlanningError(f"Unsupported analysis task type: {task_type}")

        profile_columns = {column.name for column in profile.columns}
        if not profile_columns:
            raise PlanningError("Dataset profile contains no columns.")

        existence_mode = effective_existence_mode
        allows_missing_target_lookup = (
            effective_intent_name == "existence_check"
            and existence_mode in {"column_property_check", "column_presence_check"}
        )
        if request.target is not None and request.target not in profile_columns and not allows_missing_target_lookup:
            raise PlanningError(f"Target column '{request.target}' does not exist in the dataset profile.")
        if request.options.get("distinct_values") and request.target not in set(profile.dimension_columns):
            raise PlanningError("Distinct value listing requires a dimension target.")
        if effective_intent_name == "distinct_value_count" and request.target not in set(profile.dimension_columns):
            raise PlanningError("Distinct value count requires a dimension target.")
        if effective_intent_name == "representation_ranking" and request.target not in set(profile.dimension_columns):
            raise PlanningError("Representation ranking requires a dimension target.")
        if effective_intent_name == "row_ranking" and request.target not in set(profile.measure_columns):
            raise PlanningError("Row ranking requires a numeric target.")
        if effective_intent_name == "group_ranking":
            if request.target not in set(profile.measure_columns) or not request.group_by:
                raise PlanningError("Group ranking requires a numeric target and one grouping column.")
        if effective_intent_name == "tabular_query":
            selected_columns = request.options.get("selected_columns", [])
            invalid_selected = [column for column in selected_columns if column not in profile_columns]
            if invalid_selected:
                joined = ", ".join(invalid_selected)
                raise PlanningError(f"Selected columns do not exist in the dataset profile: {joined}")
            sort_by = request.options.get("sort_by")
            if sort_by is not None and sort_by not in profile_columns:
                raise PlanningError(f"Sort column '{sort_by}' does not exist in the dataset profile.")
        if effective_intent_name == "grouped_tabular_query":
            if not request.group_by:
                raise PlanningError("Grouped tabular querying requires at least one grouping column.")
            if request.target is not None and request.target not in set(profile.measure_columns):
                raise PlanningError("Grouped tabular querying requires a numeric target when a target is provided.")
            grouped_sort_by = request.options.get("sort_by")
            if grouped_sort_by is not None and grouped_sort_by not in {
                *(request.group_by or []),
                request.target,
                "row_count",
                "target_total",
            }:
                raise PlanningError("Grouped tabular query sort column must be a grouping column or aggregate output.")
        if request.aggregation and request.aggregation != "count" and effective_intent_name not in {
            "time_bucket_breakdown",
            "time_period_comparison",
            "group_ranking",
            "grouped_tabular_query",
        }:
            if request.target not in set(profile.measure_columns):
                raise PlanningError(f"Aggregation '{request.aggregation}' requires a numeric target.")
        if (
            request.group_by
            and effective_intent_name not in {"representation_ranking", "group_ranking", "time_bucket_breakdown", "time_period_comparison", "grouped_tabular_query"}
            and effective_statistical_test != "chi_square"
            and request.target is not None
            and request.target not in set(profile.measure_columns)
        ):
            raise PlanningError("Grouped descriptive analysis requires a numeric target or a dedicated dimension intent.")
        if effective_intent_name == "time_coverage" and not profile.time_columns:
            raise PlanningError("Time coverage analysis requires a datetime column.")
        if effective_intent_name == "time_bucket_counts" and not profile.time_columns:
            raise PlanningError("Time bucket count analysis requires a datetime column.")
        if effective_intent_name == "time_bucket_breakdown" and not profile.time_columns:
            raise PlanningError("Time bucket breakdown analysis requires a datetime column.")
        if effective_intent_name == "time_period_comparison" and not profile.time_columns:
            raise PlanningError("Time period comparison requires a datetime column.")
        if effective_intent_name == "time_column_inventory" and not profile.time_columns:
            raise PlanningError("Time column inventory requires at least one datetime column.")
        if effective_intent_name == "time_bucket_breakdown" and request.target not in set(profile.measure_columns):
            raise PlanningError("Time bucket breakdown requires a numeric target.")
        if effective_intent_name == "time_period_comparison":
            if request.target not in set(profile.measure_columns):
                raise PlanningError("Time period comparison requires a numeric target.")
            if not request.time_reference:
                raise PlanningError("Time period comparison requires an explicit time reference.")
        if effective_intent_name == "existence_check":
            if existence_mode == "time_value":
                if not profile.time_columns:
                    raise PlanningError("Time existence verification requires a datetime column.")
                if request.target is not None and request.target not in set(profile.time_columns):
                    raise PlanningError("Time existence verification requires a datetime target column.")
                if request.options.get("expected_year") is None and not request.time_reference:
                    raise PlanningError("Time existence verification requires a concrete year or time reference.")
            elif existence_mode == "null_check":
                if request.target is None:
                    raise PlanningError("Null verification requires a target column.")
                if request.options.get("null_expectation") not in {"has_nulls", "no_nulls"}:
                    raise PlanningError("Null verification requires a supported missing-value expectation.")
            elif existence_mode == "threshold_check":
                if request.target is None or request.target not in set(profile.measure_columns):
                    raise PlanningError("Threshold verification requires a numeric target.")
                operator = request.options.get("threshold_operator")
                if operator == "between":
                    if request.options.get("lower_bound") is None or request.options.get("upper_bound") is None:
                        raise PlanningError("Between-threshold verification requires lower and upper bounds.")
                elif operator not in {"gt", "gte", "lt", "lte"} or request.options.get("threshold_value") is None:
                    raise PlanningError("Threshold verification requires a supported comparator and threshold value.")
            elif existence_mode == "column_property_check":
                if request.target is None:
                    raise PlanningError("Column property verification requires a target column.")
                if request.options.get("expected_property") not in {
                    "datetime",
                    "numeric",
                    "categorical",
                    "identifier",
                    "dimension",
                    "measure",
                    "high_cardinality",
                }:
                    raise PlanningError("Column property verification requires a supported expected property.")
            elif existence_mode == "column_presence_check":
                if not request.options.get("requested_column"):
                    raise PlanningError("Column presence verification requires a requested column name.")
            elif not request.filters:
                raise PlanningError("Existence verification requires filters or a time-value check.")
        if effective_intent_name in {"tabular_query", "grouped_tabular_query"}:
            page = int(request.options.get("page", 1))
            page_size = int(request.options.get("page_size", 50))
            if page <= 0:
                raise PlanningError("Tabular pagination requires page to be 1 or greater.")
            if page_size <= 0:
                raise PlanningError("Tabular pagination requires page_size to be 1 or greater.")
        if effective_statistical_test == "chi_square":
            comparison_columns = request.options.get("comparison_columns", [])
            if len(comparison_columns) < 2:
                raise PlanningError("Chi-square testing requires two categorical columns.")
        if effective_statistical_test in {"t_test", "anova", "mann_whitney", "significance_inference", "power_analysis", "sample_size_estimate"}:
            if request.target is None or not request.group_by:
                raise PlanningError("Group-based statistical testing requires a numeric target and one grouping column.")
        if effective_statistical_test == "confidence_interval" and request.target is None:
            raise PlanningError("Confidence interval analysis requires a numeric target.")
        if effective_statistical_test == "regression_significance":
            feature_columns = request.options.get("feature_columns", [])
            if request.target is None or not feature_columns:
                raise PlanningError("Regression significance testing requires a target and at least one feature column.")

        if request.group_by:
            invalid_groups = [column for column in request.group_by if column not in profile_columns]
            if invalid_groups:
                joined = ", ".join(invalid_groups)
                raise PlanningError(f"Grouping columns do not exist in the dataset profile: {joined}")

        if request.filters:
            invalid_filters = [column for column in request.filters if column not in profile_columns]
            if invalid_filters:
                joined = ", ".join(invalid_filters)
                raise PlanningError(f"Filter columns do not exist in the dataset profile: {joined}")

        if request.time_reference and not profile.time_columns:
            raise PlanningError("Time-based analysis requires a datetime column.")

        supported_time_reference_types = {"month_name", "quarter", "relative_period"}
        if request.time_reference and request.time_reference.get("type") not in supported_time_reference_types:
            raise PlanningError("Unsupported time reference in analysis request.")

        if request.time_reference:
            reference_type = request.time_reference.get("type")
            if reference_type == "relative_period" and effective_intent_name != "time_period_comparison":
                raise PlanningError("Relative time references are only supported for period-comparison analysis right now.")

        if request.aggregation and request.aggregation not in supported_aggregations:
            raise PlanningError(f"Unsupported aggregation: {request.aggregation}")

        if task_type in {"diagnostic", "statistical", "predictive"} and request.target is None:
            raise PlanningError(f"{task_type.title()} analysis requires a target metric.")
        if task_type == "forecasting" and request.target is None:
            raise PlanningError("Forecasting requires a target metric.")

    def _build_rationale(self, task_type: str, request: AnalysisRequest, context: SourceContext | None) -> str:
        rationale = f"Selected a {task_type} workflow based on the normalized request."
        if request.prompt_family:
            rationale += f" Prompt family: {request.prompt_family}."
        if request.target:
            rationale += f" Target metric: {request.target}."
        if request.aggregation:
            rationale += f" Aggregation: {request.aggregation}."
        if context and context.metric_definitions:
            rationale += " Semantic metric definitions were available."
        if request.filters:
            rationale += f" Filters were detected for: {', '.join(request.filters)}."
        if request.options.get("distinct_values"):
            rationale += " A distinct value listing was requested."
        if request.intent_name == "row_ranking":
            rationale += " Ranked row retrieval was requested."
        if request.intent_name == "group_ranking":
            rationale += " Group ranking was requested."
        if request.intent_name == "tabular_query":
            rationale += " Tabular record retrieval was requested."
        if request.intent_name == "grouped_tabular_query":
            rationale += " Grouped tabular querying was requested."
        if request.intent_name:
            rationale += f" Intent: {request.intent_name}."
        if request.intent_name == "time_coverage":
            rationale += f" Time coverage mode: {request.options.get('time_coverage_mode', 'years_present')}."
        if request.intent_name == "time_bucket_counts":
            rationale += f" Time bucket counts: {request.options.get('time_bucket', 'year')}."
        if request.intent_name == "time_bucket_breakdown":
            rationale += f" Time bucket breakdown: {request.options.get('time_bucket', 'month')}."
        if request.intent_name == "time_period_comparison":
            rationale += f" Time period comparison bucket: {request.options.get('time_bucket', 'month')}."
        if request.intent_name == "existence_check":
            rationale += f" Existence mode: {request.options.get('existence_mode', 'filtered_rows')}."
        if request.intent_name in {"tabular_query", "grouped_tabular_query"}:
            if request.options.get("selected_columns"):
                rationale += f" Selected columns: {', '.join(request.options['selected_columns'])}."
            if request.options.get("sort_by"):
                rationale += f" Sort: {request.options['sort_by']} {request.options.get('sort_direction', 'asc')}."
            rationale += (
                f" Pagination: page {request.options.get('page', 1)} "
                f"with page size {request.options.get('page_size', 50)}."
            )
        if request.options.get("statistical_test"):
            rationale += f" Statistical test: {request.options['statistical_test']}."
        return rationale


AnalysisPlanner = PlanBuilder
