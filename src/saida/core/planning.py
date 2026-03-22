"""Structured planning from canonicalized requests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from saida.exceptions import PlanningError
from saida.core.contracts import AnalysisPlan, AnalysisRequest, DatasetProfile, PlanStep, SourceContext

if TYPE_CHECKING:
    from saida.core.prompt_capability_contract import PromptCapabilityContract


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
        return self.build_plan(request, profile, context)

    def build_plan(
        self,
        request: AnalysisRequest,
        profile: DatasetProfile,
        context: SourceContext | None = None,
    ) -> AnalysisPlan:
        """Build an executable plan from the request and profile."""
        self._validate_request(request, profile)
        task_type = request.task_type_hint or "descriptive"
        warnings: list[str] = []
        steps: list[PlanStep] = []

        if request.target is None and profile.measure_columns and request.intent_name not in {
            "row_count",
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
            "time_coverage",
            "time_bucket_counts",
            "time_bucket_breakdown",
            "time_period_comparison",
            "existence_check",
            "tabular_query",
            "grouped_tabular_query",
        }:
            request.target = profile.measure_columns[0]
            warnings.append("No target was provided; using the first measure column.")

        if task_type in {"descriptive", "diagnostic", "statistical"}:
            numeric_target = bool(request.target and request.target in set(profile.measure_columns))
            statistical_test = request.options.get("statistical_test")
            if task_type == "statistical" and statistical_test:
                steps.append(
                    PlanStep(
                        step_id=statistical_test,
                        tool_family="stats",
                        action=statistical_test,
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
                        description=f"Run the deterministic {statistical_test} workflow.",
                    )
                )
                rationale = self._build_rationale(task_type, request, context)
                return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)
            if request.intent_name in {
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
            }:
                steps.append(
                    PlanStep(
                        step_id=request.intent_name,
                        tool_family="metadata",
                        action=request.intent_name,
                        parameters={"target": request.target},
                        description="Return dataset inventory information for the requested metadata view.",
                    )
                )
                rationale = self._build_rationale(task_type, request, context)
                return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)
            if request.intent_name == "time_coverage":
                steps.append(
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
                )
                rationale = self._build_rationale(task_type, request, context)
                return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)
            if request.intent_name == "time_bucket_counts":
                steps.append(
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
                )
                rationale = self._build_rationale(task_type, request, context)
                return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)
            if request.intent_name == "time_bucket_breakdown":
                steps.append(
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
                )
                rationale = self._build_rationale(task_type, request, context)
                return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)
            if request.intent_name == "time_period_comparison":
                comparison_action = "grouped_period_comparison" if request.group_by else "period_comparison"
                steps.append(
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
                )
                rationale = self._build_rationale(task_type, request, context)
                return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)
            if request.intent_name == "existence_check":
                existence_mode = request.options.get("existence_mode", "filtered_rows")
                if existence_mode == "time_value":
                    steps.append(
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
                    )
                elif existence_mode == "null_check":
                    steps.append(
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
                    )
                elif existence_mode == "threshold_check":
                    steps.append(
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
                    )
                elif existence_mode == "column_property_check":
                    steps.append(
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
                    )
                else:
                    steps.append(
                        PlanStep(
                            step_id="row_existence",
                            tool_family="duckdb",
                            action="row_existence",
                            parameters={"filters": request.filters or {}},
                            description="Verify whether any rows match the requested filters.",
                        )
                    )
                rationale = self._build_rationale(task_type, request, context)
                return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)
            if request.intent_name == "tabular_query":
                steps.append(
                    PlanStep(
                        step_id="tabular_query",
                        tool_family="duckdb",
                        action="tabular_query",
                        parameters={
                            "selected_columns": request.options.get("selected_columns") or None,
                            "filters": request.filters,
                            "sort_by": request.options.get("sort_by"),
                            "sort_direction": request.options.get("sort_direction", "asc"),
                            "limit": request.options.get("limit"),
                            "page": request.options.get("page", 1),
                            "page_size": request.options.get("page_size", 50),
                        },
                        description="Return a filtered, sorted, and paginated recordset for natural-language data discovery.",
                    )
                )
                rationale = self._build_rationale(task_type, request, context)
                return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)
            if request.intent_name == "grouped_tabular_query":
                steps.append(
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
                )
                rationale = self._build_rationale(task_type, request, context)
                return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)
            if request.intent_name == "row_count":
                steps.append(
                    PlanStep(
                        step_id="row_count",
                        tool_family="duckdb",
                        action="row_count",
                        parameters={"filters": request.filters},
                        description="Count the number of rows in the requested dataset slice.",
                    )
                )
                rationale = self._build_rationale(task_type, request, context)
                return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)
            if request.intent_name == "representation_ranking" and request.target:
                steps.append(
                    PlanStep(
                        step_id="count_rows_by_group",
                        tool_family="duckdb",
                        action="count_rows_by_group",
                        parameters={
                            "group_by": [request.target],
                            "filters": request.filters,
                            "ascending": request.options.get("ranking_direction") == "asc",
                            "limit": 5,
                        },
                        description="Count rows by group and rank the representation of the requested dimension.",
                    )
                )
                rationale = self._build_rationale(task_type, request, context)
                return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)
            if request.intent_name == "row_ranking" and request.target:
                steps.append(
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
                )
                rationale = self._build_rationale(task_type, request, context)
                return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)
            if request.intent_name == "group_ranking" and request.target and request.group_by:
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
                            "limit": int(request.options.get("ranking_limit", 5)),
                            "ascending": request.options.get("ranking_direction") == "asc",
                        },
                        description="Rank grouped results according to the requested top or bottom limit.",
                    )
                )
                rationale = self._build_rationale(task_type, request, context)
                return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)
            if request.options.get("distinct_values") and request.target:
                steps.append(
                    PlanStep(
                        step_id="distinct_values",
                        tool_family="duckdb",
                        action="distinct_values",
                        parameters={"target": request.target, "filters": request.filters},
                        description="List the distinct values for the requested dimension.",
                    )
                )
                rationale = self._build_rationale(task_type, request, context)
                return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)
            if (
                task_type == "descriptive"
                and request.target in set(profile.dimension_columns)
                and not request.aggregation
                and not request.group_by
            ):
                steps.append(
                    PlanStep(
                        step_id="distinct_values",
                        tool_family="duckdb",
                        action="distinct_values",
                        parameters={"target": request.target, "filters": request.filters},
                        description="List the distinct values for the requested dimension.",
                    )
                )
                warnings.append("Dimension prompt was routed to a distinct value listing.")
                rationale = self._build_rationale(task_type, request, context)
                return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)
            if numeric_target and request.aggregation:
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
            if numeric_target and profile.time_columns:
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
            if numeric_target and request.time_reference and profile.time_columns:
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
            if numeric_target and request.group_by:
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
            elif task_type == "diagnostic" and numeric_target and profile.dimension_columns:
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
            if task_type == "diagnostic" and numeric_target and profile.dimension_columns:
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
            if numeric_target:
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

        if task_type == "forecasting":
            if not profile.time_columns:
                raise PlanningError("Forecasting requires a datetime column.")
            if request.target is None:
                raise PlanningError("Forecasting requires a target metric.")
            steps.append(
                PlanStep(
                    step_id="forecast",
                    tool_family="ml",
                    action="forecast",
                    parameters={"target": request.target, "time_column": profile.time_columns[0], "horizon": request.horizon or 3},
                    description="Generate a forecast for the requested target.",
                )
            )

        if task_type == "predictive":
            warnings.append("Predictive model training is not implemented yet.")

        rationale = self._build_rationale(task_type, request, context)
        return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)

    def validate(self, plan: AnalysisPlan) -> None:
        """Validate a plan before execution."""
        if not plan.steps:
            raise PlanningError("Analysis plan contains no executable steps.")

    def _validate_request(self, request: AnalysisRequest, profile: DatasetProfile) -> None:
        supported_tasks = {"descriptive", "diagnostic", "statistical", "predictive", "forecasting"}
        supported_aggregations = {"sum", "mean", "max", "min", "count"}
        task_type = request.task_type_hint or "descriptive"
        if task_type not in supported_tasks:
            raise PlanningError(f"Unsupported analysis task type: {task_type}")

        profile_columns = {column.name for column in profile.columns}
        if not profile_columns:
            raise PlanningError("Dataset profile contains no columns.")

        if request.target is not None and request.target not in profile_columns:
            raise PlanningError(f"Target column '{request.target}' does not exist in the dataset profile.")
        if request.options.get("distinct_values") and request.target not in set(profile.dimension_columns):
            raise PlanningError("Distinct value listing requires a dimension target.")
        if request.intent_name == "representation_ranking" and request.target not in set(profile.dimension_columns):
            raise PlanningError("Representation ranking requires a dimension target.")
        if request.intent_name == "row_ranking" and request.target not in set(profile.measure_columns):
            raise PlanningError("Row ranking requires a numeric target.")
        if request.intent_name == "group_ranking":
            if request.target not in set(profile.measure_columns) or not request.group_by:
                raise PlanningError("Group ranking requires a numeric target and one grouping column.")
        if request.intent_name == "tabular_query":
            selected_columns = request.options.get("selected_columns", [])
            invalid_selected = [column for column in selected_columns if column not in profile_columns]
            if invalid_selected:
                joined = ", ".join(invalid_selected)
                raise PlanningError(f"Selected columns do not exist in the dataset profile: {joined}")
            sort_by = request.options.get("sort_by")
            if sort_by is not None and sort_by not in profile_columns:
                raise PlanningError(f"Sort column '{sort_by}' does not exist in the dataset profile.")
        if request.intent_name == "grouped_tabular_query":
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
        if request.aggregation and request.aggregation != "count" and request.intent_name not in {
            "time_bucket_breakdown",
            "time_period_comparison",
            "group_ranking",
            "grouped_tabular_query",
        }:
            if request.target not in set(profile.measure_columns):
                raise PlanningError(f"Aggregation '{request.aggregation}' requires a numeric target.")
        if (
            request.group_by
            and request.intent_name not in {"representation_ranking", "group_ranking", "time_bucket_breakdown", "time_period_comparison", "grouped_tabular_query"}
            and request.target is not None
            and request.target not in set(profile.measure_columns)
        ):
            raise PlanningError("Grouped descriptive analysis requires a numeric target or a dedicated dimension intent.")
        if request.intent_name == "time_coverage" and not profile.time_columns:
            raise PlanningError("Time coverage analysis requires a datetime column.")
        if request.intent_name == "time_bucket_counts" and not profile.time_columns:
            raise PlanningError("Time bucket count analysis requires a datetime column.")
        if request.intent_name == "time_bucket_breakdown" and not profile.time_columns:
            raise PlanningError("Time bucket breakdown analysis requires a datetime column.")
        if request.intent_name == "time_period_comparison" and not profile.time_columns:
            raise PlanningError("Time period comparison requires a datetime column.")
        if request.intent_name == "time_column_inventory" and not profile.time_columns:
            raise PlanningError("Time column inventory requires at least one datetime column.")
        if request.intent_name == "time_bucket_breakdown" and request.target not in set(profile.measure_columns):
            raise PlanningError("Time bucket breakdown requires a numeric target.")
        if request.intent_name == "time_period_comparison":
            if request.target not in set(profile.measure_columns):
                raise PlanningError("Time period comparison requires a numeric target.")
            if not request.time_reference:
                raise PlanningError("Time period comparison requires an explicit time reference.")
        if request.intent_name == "existence_check":
            existence_mode = request.options.get("existence_mode", "filtered_rows")
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
                if request.options.get("expected_property") not in {"datetime", "numeric", "categorical", "identifier"}:
                    raise PlanningError("Column property verification requires a supported expected property.")
            elif not request.filters:
                raise PlanningError("Existence verification requires filters or a time-value check.")
        if request.intent_name in {"tabular_query", "grouped_tabular_query"}:
            page = int(request.options.get("page", 1))
            page_size = int(request.options.get("page_size", 50))
            if page <= 0:
                raise PlanningError("Tabular pagination requires page to be 1 or greater.")
            if page_size <= 0:
                raise PlanningError("Tabular pagination requires page_size to be 1 or greater.")
        if request.options.get("statistical_test") == "chi_square":
            comparison_columns = request.options.get("comparison_columns", [])
            if len(comparison_columns) < 2:
                raise PlanningError("Chi-square testing requires two categorical columns.")
        if request.options.get("statistical_test") in {"t_test", "anova", "mann_whitney", "significance_inference", "power_analysis", "sample_size_estimate"}:
            if request.target is None or not request.group_by:
                raise PlanningError("Group-based statistical testing requires a numeric target and one grouping column.")
        if request.options.get("statistical_test") == "confidence_interval" and request.target is None:
            raise PlanningError("Confidence interval analysis requires a numeric target.")
        if request.options.get("statistical_test") == "regression_significance":
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

        if request.time_reference and request.time_reference.get("type") != "month_name" and request.intent_name != "time_period_comparison":
            raise PlanningError("Only month-based time references are supported for non-ML analysis right now.")

        if request.aggregation and request.aggregation not in supported_aggregations:
            raise PlanningError(f"Unsupported aggregation: {request.aggregation}")

        if task_type in {"diagnostic", "statistical", "predictive"} and request.target is None:
            raise PlanningError(f"{task_type.title()} analysis requires a target metric.")
        if task_type == "forecasting" and request.target is None:
            raise PlanningError("Forecasting requires a target metric.")

    def _build_rationale(self, task_type: str, request: AnalysisRequest, context: SourceContext | None) -> str:
        rationale = f"Selected a {task_type} workflow based on the normalized request."
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
