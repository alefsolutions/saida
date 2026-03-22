"""Main orchestration engine for SAIDA."""

from __future__ import annotations

import pandas as pd

from saida.adapters import DuckDBAdapter, MlAdapter, StatsModelsAdapter
from saida.config import SaidaConfig
from saida.core import (
    BackendRouter,
    InputCanonicalizer,
    PlanBuilder,
    PlanValidator,
    ResultCanonicalizer,
    SchemaDiscoveryService,
    SourceContextParser,
    build_prompt_capability_contract,
)
from saida.exceptions import PlanningError, ReasoningError, ValidationError
from saida.llm import BaseLlmProvider, ResponseContext, build_llm_provider
from saida.outputs import SummaryFormatter
from saida.core.contracts import (
    AnalysisResult,
    AnalysisPlan,
    AnalysisRequest,
    ColumnProfile,
    Dataset,
    DatasetProfile,
    ExecutionTraceEvent,
    ForecastAnalysisResult,
    ModelSpec,
    Metric,
    PredictionResult,
    SourceContext,
    TableArtifact,
    TrainResult,
)


class Saida:
    """Coordinate SAIDA modules through a simple Python API."""

    HIGH_CARDINALITY_DISTINCT_RATIO = 0.8

    def __init__(self, config: SaidaConfig | None = None, llm_provider: BaseLlmProvider | None = None) -> None:
        self.config = config or SaidaConfig()
        self.discovery = SchemaDiscoveryService()
        self.canonicalizer = InputCanonicalizer(self.config.nlp)
        self.plan_builder = PlanBuilder()
        self.validator = PlanValidator()
        self.duckdb = DuckDBAdapter()
        self.stats = StatsModelsAdapter()
        self.ml = MlAdapter()
        self.router = BackendRouter(
            duckdb_adapter=self.duckdb,
            stats_adapter=self.stats,
            ml_adapter=self.ml,
        )
        self.summary_formatter = SummaryFormatter()
        self.result_canonicalizer = ResultCanonicalizer()
        self.llm_provider = llm_provider or build_llm_provider(self.config.llm)

    def profile(self, dataset: Dataset) -> DatasetProfile:
        """Profile a dataset deterministically."""
        return self.discovery.profile(dataset)

    def capabilities(self) -> dict[str, bool]:
        """Return the currently available public SAIDA capabilities."""
        return {
            "analyze": True,
            "profile": True,
            "load_context": True,
            "train": False,
            "predict": False,
            "forecast": False,
            "prompt_capability_contract": True,
            "capability_registry": True,
            "llm_prompting": bool(self.llm_provider and self.config.llm.use_for_prompting),
            "llm_reasoning": bool(self.llm_provider and self.config.llm.use_for_reasoning),
        }

    def analyze(self, dataset: Dataset, question: str) -> AnalysisResult:
        """Run an end-to-end deterministic analysis workflow."""
        self.validator.validate_dataset(dataset)
        trace = [self._trace("adapter", "dataset loaded", {"dataset": dataset.name})]
        if dataset.context is not None:
            trace.append(self._trace("context", "context attached", {"metric_count": len(dataset.context.metric_definitions)}))

        profile = self.profile(dataset)
        trace.append(self._trace("profiling", "profile generated", {"row_count": profile.row_count}))

        request, request_warnings, llm_trace_event = self._build_request(question, dataset, profile)
        if llm_trace_event is not None:
            trace.append(llm_trace_event)
        trace.append(self._trace("nlp", "request normalized", {"task_type": request.task_type_hint, "target": request.target}))

        capability_contract = build_prompt_capability_contract(request, profile)
        trace.append(
            self._trace(
                "contract",
                "prompt capability contract built",
                {
                    "status": capability_contract.status,
                    "selected_capabilities": list(capability_contract.selected_capabilities),
                },
            )
        )

        if request.options.get("analysis_outcome") == "clarify":
            plan = AnalysisPlan(
                task_type="clarification",
                rationale="Optional LLM interpretation requested clarification before planning.",
                steps=[],
                warnings=request_warnings,
            )
            summary = request.options.get("llm_message") or "We need clarification before running this analysis."
            trace.append(self._trace("results", "clarification returned", {"summary_length": len(summary)}))
            return self.result_canonicalizer.build_analysis_result(
                summary,
                None,
                None,
                "deterministic",
                [],
                [],
                self._merge_warnings(request_warnings, capability_contract.warnings),
                plan,
                request,
                profile,
                trace,
                capability_contract,
            )

        if request.options.get("analysis_outcome") == "refuse":
            plan = AnalysisPlan(
                task_type="unavailable",
                rationale="Optional LLM interpretation declined the request before planning.",
                steps=[],
                warnings=request_warnings,
            )
            summary = request.options.get("llm_message") or "We are not able to provide this information at this time."
            trace.append(self._trace("results", "refusal returned", {"summary_length": len(summary)}))
            return self.result_canonicalizer.build_analysis_result(
                summary,
                None,
                None,
                "deterministic",
                [],
                [],
                self._merge_warnings(request_warnings, capability_contract.warnings),
                plan,
                request,
                profile,
                trace,
                capability_contract,
            )

        contract_warning_messages = [issue.message for issue in capability_contract.validation_issues if issue.severity != "error"]
        if capability_contract.status == "unsupported_capability":
            summary = "The request mapped to capabilities that SAIDA does not currently support."
            plan = AnalysisPlan(
                task_type="unavailable",
                rationale="Prompt capability contract determined the request is unsupported before planning.",
                steps=[],
                warnings=self._merge_warnings(request_warnings, capability_contract.warnings, contract_warning_messages),
            )
            trace.append(self._trace("results", "unsupported capability returned", {"summary_length": len(summary)}))
            return self.result_canonicalizer.build_analysis_result(
                summary,
                None,
                None,
                "deterministic",
                [],
                [],
                self._merge_warnings(request_warnings, capability_contract.warnings, contract_warning_messages),
                plan,
                request,
                profile,
                trace,
                capability_contract,
            )

        if (
            request.options.get("nlp_backend") == "llm+validation"
            and capability_contract.status in {"supported_but_data_infeasible", "supported_but_data_insufficient"}
        ):
            summary = self._contract_guidance_message(capability_contract)
            plan = AnalysisPlan(
                task_type="clarification",
                rationale="Prompt capability contract requires clarification or better data support before planning.",
                steps=[],
                warnings=self._merge_warnings(request_warnings, capability_contract.warnings, contract_warning_messages),
            )
            trace.append(self._trace("results", "contract clarification returned", {"summary_length": len(summary)}))
            return self.result_canonicalizer.build_analysis_result(
                summary,
                None,
                None,
                "deterministic",
                [],
                [],
                self._merge_warnings(request_warnings, capability_contract.warnings, contract_warning_messages),
                plan,
                request,
                profile,
                trace,
                capability_contract,
            )

        try:
            plan = self.plan_builder.build_plan_from_contract(capability_contract, request, profile, dataset.context)
        except PlanningError as exc:
            if request.options.get("nlp_backend") != "llm+validation" or not capability_contract.missing_parameters:
                raise
            summary = self._contract_guidance_message(capability_contract, fallback_message=str(exc))
            plan = AnalysisPlan(
                task_type="clarification",
                rationale="Prompt capability contract could not be compiled into a safe deterministic plan.",
                steps=[],
                warnings=self._merge_warnings(request_warnings, capability_contract.warnings, contract_warning_messages),
            )
            trace.append(self._trace("results", "planning clarification returned", {"summary_length": len(summary)}))
            return self.result_canonicalizer.build_analysis_result(
                summary,
                None,
                None,
                "deterministic",
                [],
                [],
                self._merge_warnings(request_warnings, capability_contract.warnings, contract_warning_messages),
                plan,
                request,
                profile,
                trace,
                capability_contract,
            )

        self.validator.validate_plan(plan)
        trace.append(self._trace("planning", "plan validated", {"task_type": plan.task_type, "step_count": len(plan.steps)}))

        metrics = []
        tables = []
        warnings = self._merge_warnings(
            profile.warnings,
            request_warnings,
            capability_contract.warnings,
            contract_warning_messages,
            plan.warnings,
        )

        for step in plan.steps:
            if step.tool_family == "metadata":
                if step.action == "column_property_check":
                    tables.append(self._column_property_check_table(step.parameters, profile))
                elif step.action == "column_presence_check":
                    tables.append(self._column_presence_check_table(step.parameters, profile))
                else:
                    tables.append(self._metadata_table(step.action, profile, step.parameters))
                trace.append(self._trace("compute", f"executed {step.action}", step.parameters))
                continue

            adapter = self.router.route(step.tool_family)
            if step.tool_family == "duckdb":
                if step.action == "dataset_summary":
                    step_metrics, step_tables = adapter.dataset_summary(
                        dataset.data,
                        step.parameters.get("target"),
                        step.parameters.get("filters"),
                    )
                    metrics.extend(step_metrics)
                    tables.extend(step_tables)
                elif step.action == "row_count":
                    metrics.extend(
                        adapter.row_count(
                            dataset.data,
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "count_rows_by_group":
                    tables.append(
                        adapter.count_rows_by_group(
                            dataset.data,
                            step.parameters["group_by"],
                            step.parameters.get("filters"),
                            step.parameters.get("ascending", False),
                            step.parameters.get("limit"),
                        )
                    )
                elif step.action == "distinct_values":
                    tables.append(
                        adapter.distinct_values(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "tabular_query":
                    tables.append(
                        adapter.tabular_query(
                            dataset.data,
                            step.parameters.get("selected_columns"),
                            step.parameters.get("filters"),
                            step.parameters.get("sort_by"),
                            step.parameters.get("sort_direction", "asc"),
                            step.parameters.get("limit"),
                            step.parameters.get("page", 1),
                            step.parameters.get("page_size", 50),
                        )
                    )
                elif step.action == "grouped_tabular_query":
                    tables.append(
                        adapter.grouped_tabular_query(
                            dataset.data,
                            step.parameters["group_by"],
                            step.parameters.get("target"),
                            step.parameters.get("aggregation", "count"),
                            step.parameters.get("filters"),
                            step.parameters.get("sort_by"),
                            step.parameters.get("sort_direction", "desc"),
                            step.parameters.get("limit"),
                            step.parameters.get("page", 1),
                            step.parameters.get("page_size", 50),
                        )
                    )
                elif step.action == "time_coverage":
                    tables.append(
                        adapter.time_coverage(
                            dataset.data,
                            step.parameters["time_column"],
                            step.parameters.get("mode", "years_present"),
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "time_bucket_counts":
                    tables.append(
                        adapter.time_bucket_counts(
                            dataset.data,
                            step.parameters["time_column"],
                            step.parameters.get("bucket", "year"),
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "time_bucket_breakdown":
                    tables.append(
                        adapter.time_bucket_breakdown(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["time_column"],
                            step.parameters.get("bucket", "month"),
                            step.parameters.get("aggregation", "sum"),
                            step.parameters.get("group_by"),
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "row_existence":
                    tables.append(
                        adapter.row_existence(
                            dataset.data,
                            step.parameters.get("filters", {}),
                        )
                    )
                elif step.action == "time_value_exists":
                    tables.append(
                        adapter.time_value_exists(
                            dataset.data,
                            step.parameters["time_column"],
                            step.parameters.get("expected_year"),
                            step.parameters.get("time_reference"),
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "null_check":
                    tables.append(
                        adapter.null_check(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters.get("null_expectation", "has_nulls"),
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "threshold_check":
                    tables.append(
                        adapter.threshold_check(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["threshold_operator"],
                            step.parameters.get("threshold_value"),
                            step.parameters.get("lower_bound"),
                            step.parameters.get("upper_bound"),
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "aggregate_value":
                    step_metrics = adapter.aggregate_value(
                        dataset.data,
                        step.parameters["target"],
                        step.parameters["aggregation"],
                        step.parameters.get("filters"),
                    )
                    metrics.extend(step_metrics)
                elif step.action == "ranked_rows":
                    tables.append(
                        adapter.ranked_rows(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters.get("filters"),
                            step.parameters.get("ascending", False),
                            step.parameters.get("limit", 5),
                        )
                    )
                elif step.action == "time_trend":
                    tables.append(
                        adapter.time_trend(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["time_column"],
                            step.parameters.get("aggregation", "sum"),
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "group_breakdown":
                    tables.append(
                        adapter.group_breakdown(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"],
                            step.parameters.get("aggregation", "sum"),
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "ranked_breakdown":
                    tables.append(
                        adapter.ranked_breakdown(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"],
                            step.parameters.get("aggregation", "sum"),
                            step.parameters.get("filters"),
                            step.parameters.get("limit", 5),
                            step.parameters.get("ascending", False),
                        )
                    )
                elif step.action == "grouped_period_comparison":
                    tables.append(
                        adapter.grouped_period_comparison(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"],
                            step.parameters["time_column"],
                            step.parameters["time_reference"],
                            step.parameters.get("bucket"),
                            step.parameters.get("aggregation", "sum"),
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "top_movers":
                    tables.append(
                        adapter.top_movers(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"],
                            step.parameters["time_column"],
                            step.parameters["time_reference"],
                            step.parameters.get("aggregation", "sum"),
                            step.parameters.get("filters"),
                            step.parameters.get("limit", 5),
                        )
                    )
                elif step.action == "contribution_breakdown":
                    tables.append(
                        adapter.contribution_breakdown(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"],
                            step.parameters.get("time_column"),
                            step.parameters.get("time_reference"),
                            step.parameters.get("aggregation", "sum"),
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "period_comparison":
                    tables.append(
                        adapter.period_comparison(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["time_column"],
                            step.parameters["time_reference"],
                            step.parameters.get("bucket"),
                            step.parameters.get("aggregation", "sum"),
                            step.parameters.get("filters"),
                        )
                    )
            elif step.tool_family == "stats":
                if step.action == "missingness_summary":
                    tables.append(adapter.missingness_summary(dataset.data))
                elif step.action == "numeric_summary":
                    tables.append(adapter.numeric_summary(dataset.data))
                elif step.action == "distribution_summary":
                    distribution_table = adapter.distribution_summary(dataset.data, step.parameters["target"])
                    if distribution_table is not None:
                        tables.append(distribution_table)
                elif step.action == "target_correlation":
                    correlation_table = adapter.correlation_matrix(dataset.data, step.parameters.get("target"))
                    if correlation_table is not None:
                        tables.append(correlation_table)
                elif step.action == "anomaly_summary":
                    anomaly_table = adapter.anomaly_summary(
                        dataset.data,
                        step.parameters["target"],
                        step.parameters.get("time_column"),
                    )
                    if anomaly_table is not None:
                        tables.append(anomaly_table)
                elif step.action == "time_series_diagnostics":
                    diagnostics_table = adapter.time_series_diagnostics(
                        dataset.data,
                        step.parameters["target"],
                        step.parameters["time_column"],
                    )
                    if diagnostics_table is not None:
                        tables.append(diagnostics_table)
                elif step.action == "group_mean_comparison":
                    comparison_table = adapter.group_mean_comparison(
                        dataset.data,
                        step.parameters["target"],
                        step.parameters["group_column"],
                    )
                    if comparison_table is not None:
                        tables.append(comparison_table)
                elif step.action == "t_test":
                    tables.append(
                        adapter.t_test(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"][0],
                            step.parameters.get("alpha", 0.05),
                        )
                    )
                elif step.action == "chi_square":
                    comparison_columns = step.parameters.get("comparison_columns", [])
                    tables.append(
                        adapter.chi_square_test(
                            dataset.data,
                            comparison_columns[0],
                            comparison_columns[1],
                            step.parameters.get("alpha", 0.05),
                        )
                    )
                elif step.action == "anova":
                    tables.append(
                        adapter.anova_test(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"][0],
                            step.parameters.get("alpha", 0.05),
                        )
                    )
                elif step.action == "mann_whitney":
                    tables.append(
                        adapter.mann_whitney_test(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"][0],
                            step.parameters.get("alpha", 0.05),
                        )
                    )
                elif step.action == "confidence_interval":
                    tables.append(
                        adapter.confidence_interval(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters.get("confidence_level", 0.95),
                        )
                    )
                elif step.action == "regression_significance":
                    tables.append(
                        adapter.regression_significance(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters.get("feature_columns", []),
                            step.parameters.get("alpha", 0.05),
                        )
                    )
                elif step.action == "significance_inference":
                    tables.append(
                        adapter.group_significance_test(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"][0],
                            step.parameters.get("alpha", 0.05),
                        )
                    )
                elif step.action == "power_analysis":
                    tables.append(
                        adapter.power_analysis(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"][0],
                            step.parameters.get("alpha", 0.05),
                        )
                    )
                elif step.action == "sample_size_estimate":
                    tables.append(
                        adapter.sample_size_estimate(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"][0],
                            step.parameters.get("alpha", 0.05),
                            step.parameters.get("desired_power", 0.80),
                        )
                    )
            trace.append(self._trace("compute", f"executed {step.action}", step.parameters))

        deterministic_summary = self.summary_formatter.summarize(plan, metrics, tables, warnings, request, profile, dataset.context)
        summary, llm_summary, summary_source, llm_reasoning_warning = self._build_summary(
            question,
            request,
            profile,
            plan,
            metrics,
            tables,
            warnings,
            deterministic_summary,
            dataset.context,
        )
        if llm_reasoning_warning is not None:
            warnings = self._merge_warnings(warnings, [llm_reasoning_warning])
        trace.append(self._trace("results", "analysis result packaged", {"summary_length": len(summary)}))
        return self.result_canonicalizer.build_analysis_result(
            summary,
            deterministic_summary,
            llm_summary,
            summary_source,
            metrics,
            tables,
            warnings,
            plan,
            request,
            profile,
            trace,
            capability_contract,
        )

    def train(
        self,
        dataset: Dataset,
        target: str,
        problem_type: str = "regression",
        feature_columns: list[str] | None = None,
    ) -> TrainResult:
        """Reserve the training API surface for a later ML implementation."""
        spec = ModelSpec(problem_type=problem_type, target=target, feature_columns=feature_columns, model_name=None)
        return self.ml.train(spec)

    def predict(self, dataset: Dataset, artifact_path: str) -> PredictionResult:
        """Reserve the prediction API surface for a later ML implementation."""
        _ = dataset
        _ = artifact_path
        return self.ml.predict()

    def forecast(self, dataset: Dataset, target: str, horizon: int = 3) -> ForecastAnalysisResult:
        """Reserve the forecast API surface for a later ML implementation."""
        _ = dataset
        return self.ml.forecast(target, horizon)

    def load_context(self, markdown: str) -> SourceContext:
        """Parse markdown context through the context layer."""
        return SourceContextParser().parse(markdown)
    def _trace(self, stage: str, message: str, payload: dict[str, object] | None = None) -> ExecutionTraceEvent:
        return ExecutionTraceEvent(stage=stage, message=message, payload=payload)
    def _merge_warnings(self, *warning_groups: list[str]) -> list[str]:
        merged: list[str] = []
        for warning_group in warning_groups:
            for warning in warning_group:
                if warning not in merged:
                    merged.append(warning)
        return merged

    def _build_request(
        self,
        question: str,
        dataset: Dataset,
        profile: DatasetProfile,
    ) -> tuple[AnalysisRequest, list[str], ExecutionTraceEvent | None]:
        if not self.llm_provider or not self.config.llm.use_for_prompting:
            request, warnings = self.canonicalizer.normalize(question, dataset, profile, dataset.context)
            return request, warnings, None

        try:
            proposal = self.llm_provider.interpret_prompt(
                question=question,
                dataset_name=dataset.name,
                profile_summary=self._profile_summary(profile),
                context_summary=self._context_summary(dataset.context),
            )
        except ReasoningError:
            request, warnings = self.canonicalizer.normalize(question, dataset, profile, dataset.context)
            warnings.append("Optional LLM prompting failed; falling back to deterministic request normalization.")
            return request, warnings, self._trace("llm", "prompt interpretation failed", {"fallback": "rules"})

        if proposal is None:
            request, warnings = self.canonicalizer.normalize(question, dataset, profile, dataset.context)
            warnings.append("Optional LLM prompting was unavailable; falling back to deterministic request normalization.")
            return request, warnings, self._trace("llm", "prompt interpretation skipped", {"fallback": "rules"})

        if proposal.status in {"clarify", "refuse"}:
            fallback_request, fallback_warnings = self.canonicalizer.normalize(question, dataset, profile, dataset.context)
            if self._is_confident_deterministic_request(fallback_request, fallback_warnings):
                fallback_warnings.append(
                    "Optional LLM prompting requested clarification or refusal, but deterministic request normalization found a valid supported intent."
                )
                return (
                    fallback_request,
                    fallback_warnings,
                    self._trace("llm", "early LLM outcome overridden by deterministic request normalization", {"status": proposal.status}),
                )
            request = AnalysisRequest(
                question=question,
                task_type_hint=None,
                target=None,
                options={
                    "dataset": dataset.name,
                    "nlp_backend": "llm+validation",
                    "analysis_outcome": proposal.status,
                    "llm_message": proposal.message,
                },
            )
            return request, list(proposal.warnings), self._trace("llm", "prompt interpretation returned early outcome", {"status": proposal.status})

        request, warnings = self.canonicalizer.normalize_with_proposal(question, dataset, profile, proposal, dataset.context)
        return request, warnings, self._trace("llm", "prompt interpreted by optional LLM", {"status": proposal.status})

    def _build_summary(
        self,
        question: str,
        request: AnalysisRequest,
        profile: DatasetProfile,
        plan: AnalysisPlan,
        metrics: list[Metric],
        tables: list[TableArtifact],
        warnings: list[str],
        deterministic_summary: str,
        context: SourceContext | None,
    ) -> tuple[str, str | None, str, str | None]:
        if not self.llm_provider or not self.config.llm.use_for_reasoning:
            return deterministic_summary, None, "deterministic", None

        response_context = ResponseContext(
            question=question,
            dataset_name=profile.dataset_name,
            task_type=plan.task_type,
            deterministic_summary=deterministic_summary,
            context_summary=self._context_summary(context),
            metric_lookup={metric.name: metric.value for metric in metrics},
            table_index={
                table.name: {
                    "rows": int(len(table.dataframe)),
                    "columns": list(table.dataframe.columns),
                    "description": table.description,
                    "metadata": dict(table.metadata),
                }
                for table in tables
            },
            warnings=list(warnings),
        )
        try:
            proposal = self.llm_provider.generate_response(response_context)
        except ReasoningError:
            return deterministic_summary, None, "deterministic", "Optional LLM response generation failed; using deterministic summary."

        if proposal is None:
            return deterministic_summary, None, "deterministic", "Optional LLM response generation was unavailable; using deterministic summary."
        if proposal.status != "ready" or not proposal.summary:
            return deterministic_summary, None, "deterministic", "Optional LLM response was invalid; using deterministic summary."
        return proposal.summary, proposal.summary, "llm", None

    def _profile_summary(self, profile: DatasetProfile) -> str:
        return (
            f"rows={profile.row_count}; columns={profile.column_count}; "
            f"measures={profile.measure_columns}; dimensions={profile.dimension_columns}; "
            f"time_columns={profile.time_columns}; identifiers={profile.identifier_columns}"
        )

    def _context_summary(self, context: SourceContext | None) -> str | None:
        if context is None:
            return None
        parts: list[str] = []
        if context.metric_definitions:
            parts.append(f"metrics={list(context.metric_definitions.keys())}")
        if context.trusted_date_fields:
            parts.append(f"trusted_dates={context.trusted_date_fields}")
        if context.preferred_identifiers:
            parts.append(f"identifiers={context.preferred_identifiers}")
        if context.caveats:
            parts.append(f"caveats={context.caveats}")
        if context.freshness_notes:
            parts.append(f"freshness_notes={context.freshness_notes}")
        if context.business_rules:
            parts.append(f"business_rules={context.business_rules}")
        return "; ".join(parts) if parts else None

    def _is_confident_deterministic_request(
        self,
        request: AnalysisRequest,
        warnings: list[str],
    ) -> bool:
        if warnings:
            return False
        if request.intent_name is not None:
            return True
        if request.aggregation or request.group_by or request.time_reference:
            return True
        return False

    def _contract_guidance_message(
        self,
        capability_contract: object,
        fallback_message: str | None = None,
    ) -> str:
        missing_parameters = getattr(capability_contract, "missing_parameters", [])
        issues = getattr(capability_contract, "validation_issues", [])
        if missing_parameters:
            joined = ", ".join(str(parameter) for parameter in missing_parameters)
            return f"We need clarification before running this analysis. Missing or unresolved inputs: {joined}."
        if issues:
            first_message = getattr(issues[0], "message", None)
            if isinstance(first_message, str) and first_message.strip():
                return first_message
        return fallback_message or "We need clarification or better data support before running this analysis."

    def _metadata_table(self, action: str, profile: DatasetProfile, parameters: dict[str, object] | None = None) -> TableArtifact:
        parameters = parameters or {}
        if action == "column_inventory":
            dataframe = pd.DataFrame({"column_name": [column.name for column in profile.columns]})
            return TableArtifact(name="column_inventory", description="Available dataset columns.", dataframe=dataframe)
        if action == "column_type_inventory":
            rows = []
            for column in profile.columns:
                rows.append(
                    {
                        "column_name": column.name,
                        "dtype": column.inferred_type,
                        "nullable": column.nullable,
                        "null_count": self._estimated_null_count(profile, column.null_ratio),
                        "null_ratio": column.null_ratio,
                        "unique_count": column.unique_count,
                        "distinct_ratio": column.distinct_ratio,
                        "semantic_role": self._semantic_role(column.name, profile),
                    }
                )
            target = parameters.get("target")
            if isinstance(target, str):
                rows = [row for row in rows if row["column_name"] == target]
            dataframe = pd.DataFrame(rows)
            return TableArtifact(
                name="column_type_inventory",
                description=(
                    f"Detected data type and schema properties for column '{target}'."
                    if isinstance(target, str)
                    else "Detected data types and schema properties for all columns."
                ),
                dataframe=dataframe,
            )
        if action == "numeric_column_inventory":
            rows = []
            for column in profile.columns:
                if column.inferred_type not in {"integer", "float", "numeric"}:
                    continue
                rows.append({"column_name": column.name, "dtype": column.inferred_type})
            dataframe = pd.DataFrame(rows, columns=["column_name", "dtype"])
            return TableArtifact(
                name="numeric_column_inventory",
                description="Detected numeric columns.",
                dataframe=dataframe,
            )
        if action == "categorical_column_inventory":
            rows = []
            for column in profile.columns:
                if column.inferred_type not in {"category", "string", "boolean"}:
                    continue
                rows.append({"column_name": column.name, "dtype": column.inferred_type})
            dataframe = pd.DataFrame(rows, columns=["column_name", "dtype"])
            return TableArtifact(
                name="categorical_column_inventory",
                description="Detected categorical and text-like columns.",
                dataframe=dataframe,
            )
        if action == "measure_inventory":
            dataframe = pd.DataFrame({"measure_column": list(profile.measure_columns)})
            return TableArtifact(name="measure_inventory", description="Detected measure columns.", dataframe=dataframe)
        if action == "dimension_inventory":
            dataframe = pd.DataFrame({"dimension_column": list(profile.dimension_columns)})
            return TableArtifact(name="dimension_inventory", description="Detected dimension columns.", dataframe=dataframe)
        if action == "time_column_inventory":
            rows = []
            for column in profile.columns:
                if column.name not in set(profile.time_columns):
                    continue
                rows.append({"time_column": column.name, "dtype": column.inferred_type})
            dataframe = pd.DataFrame(rows, columns=["time_column", "dtype"])
            return TableArtifact(name="time_column_inventory", description="Detected time columns.", dataframe=dataframe)
        if action == "missing_value_inventory":
            rows = []
            for column in profile.columns:
                null_count = self._estimated_null_count(profile, column.null_ratio)
                if null_count <= 0:
                    continue
                rows.append(
                    {
                        "column_name": column.name,
                        "null_count": null_count,
                        "null_ratio": column.null_ratio,
                    }
                )
            dataframe = pd.DataFrame(rows, columns=["column_name", "null_count", "null_ratio"])
            return TableArtifact(
                name="missing_value_inventory",
                description="Columns with observed missing values.",
                dataframe=dataframe,
            )
        if action == "identifier_inventory":
            rows = []
            for column in profile.columns:
                if not column.is_identifier_candidate:
                    continue
                rows.append(
                    {
                        "column_name": column.name,
                        "dtype": column.inferred_type,
                        "unique_count": column.unique_count,
                        "distinct_ratio": column.distinct_ratio,
                    }
                )
            dataframe = pd.DataFrame(rows, columns=["column_name", "dtype", "unique_count", "distinct_ratio"])
            return TableArtifact(
                name="identifier_inventory",
                description="Columns that look like identifiers.",
                dataframe=dataframe,
            )
        if action == "high_cardinality_inventory":
            rows = []
            for column in profile.columns:
                if column.distinct_ratio is None or column.distinct_ratio < self.HIGH_CARDINALITY_DISTINCT_RATIO:
                    continue
                rows.append(
                    {
                        "column_name": column.name,
                        "dtype": column.inferred_type,
                        "unique_count": column.unique_count,
                        "distinct_ratio": column.distinct_ratio,
                    }
                )
            dataframe = pd.DataFrame(rows, columns=["column_name", "dtype", "unique_count", "distinct_ratio"])
            return TableArtifact(
                name="high_cardinality_inventory",
                description="Columns with a high distinct-value ratio.",
                dataframe=dataframe,
            )
        raise ValidationError(f"Unsupported metadata action: {action}")

    def _estimated_null_count(self, profile: DatasetProfile, null_ratio: float) -> int:
        return int(round(profile.row_count * null_ratio))

    def _column_property_check_table(self, parameters: dict[str, object], profile: DatasetProfile) -> TableArtifact:
        target = str(parameters["target"])
        expected_property = str(parameters["expected_property"])
        column = next((column for column in profile.columns if column.name == target), None)
        matches = self._column_matches_property(column, profile, expected_property) if column is not None else False
        return TableArtifact(
            name="column_property_check",
            description="Verification of a requested schema property for a column.",
            dataframe=pd.DataFrame(
                [
                    {
                        "column_name": target,
                        "expected_property": expected_property,
                        "matches": bool(matches),
                        "column_exists": bool(column is not None),
                        "dtype": column.inferred_type if column is not None else None,
                        "semantic_role": self._semantic_role(target, profile) if column is not None else None,
                        "is_identifier_candidate": bool(column.is_identifier_candidate) if column is not None else False,
                        "distinct_ratio": column.distinct_ratio if column is not None else None,
                    }
                ]
            ),
        )

    def _column_presence_check_table(self, parameters: dict[str, object], profile: DatasetProfile) -> TableArtifact:
        requested_column = str(parameters["requested_column"])
        profile_columns = {column.name.lower(): column.name for column in profile.columns}
        matched_column = profile_columns.get(requested_column.lower())
        column = next((item for item in profile.columns if item.name == matched_column), None)
        return TableArtifact(
            name="column_presence_check",
            description="Verification of whether a requested column exists in the dataset schema.",
            dataframe=pd.DataFrame(
                [
                    {
                        "requested_column": requested_column,
                        "matched_column": matched_column,
                        "exists": bool(matched_column is not None),
                        "dtype": column.inferred_type if column is not None else None,
                        "semantic_role": self._semantic_role(matched_column, profile) if matched_column is not None else None,
                    }
                ]
            ),
        )

    def _column_matches_property(self, column: ColumnProfile, profile: DatasetProfile, expected_property: str) -> bool:
        if expected_property == "datetime":
            return column.name in set(profile.time_columns) or column.inferred_type == "datetime"
        if expected_property == "numeric":
            return column.name in set(profile.measure_columns) or column.inferred_type in {"integer", "float", "numeric"}
        if expected_property == "categorical":
            return column.name in set(profile.dimension_columns) or column.inferred_type in {"category", "string", "boolean"}
        if expected_property == "identifier":
            return column.name in set(profile.identifier_columns) or bool(column.is_identifier_candidate)
        if expected_property == "dimension":
            return column.name in set(profile.dimension_columns)
        if expected_property == "measure":
            return column.name in set(profile.measure_columns)
        if expected_property == "high_cardinality":
            return bool(column.distinct_ratio is not None and column.distinct_ratio >= self.HIGH_CARDINALITY_DISTINCT_RATIO)
        return False

    def _semantic_role(self, column_name: str, profile: DatasetProfile) -> str:
        if column_name in set(profile.time_columns):
            return "time"
        if column_name in set(profile.identifier_columns):
            return "identifier"
        if column_name in set(profile.measure_columns):
            return "measure"
        if column_name in set(profile.dimension_columns):
            return "dimension"
        return "unclassified"
