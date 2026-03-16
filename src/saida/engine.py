"""Main orchestration engine for SAIDA."""

from __future__ import annotations

import pandas as pd

from saida.compute import BaselineMlEngine, DuckDBComputeEngine, StatsComputeEngine
from saida.config import SaidaConfig
from saida.context import SourceContextParser
from saida.exceptions import ReasoningError, ValidationError
from saida.llm import BaseLlmProvider, ResponseContext, build_llm_provider
from saida.nlp import RequestNormalizer
from saida.planning import AnalysisPlanner
from saida.profiling import DatasetProfiler
from saida.reasoning import ResultSummarizer
from saida.results import ResultBuilder
from saida.schemas import (
    AnalysisResult,
    AnalysisPlan,
    AnalysisRequest,
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

    def __init__(self, config: SaidaConfig | None = None, llm_provider: BaseLlmProvider | None = None) -> None:
        self.config = config or SaidaConfig()
        self.profiler = DatasetProfiler()
        self.normalizer = RequestNormalizer(self.config.nlp)
        self.planner = AnalysisPlanner()
        self.duckdb = DuckDBComputeEngine()
        self.stats = StatsComputeEngine()
        self.ml = BaselineMlEngine()
        self.summarizer = ResultSummarizer()
        self.results = ResultBuilder()
        self.llm_provider = llm_provider or build_llm_provider(self.config.llm)

    def profile(self, dataset: Dataset) -> DatasetProfile:
        """Profile a dataset deterministically."""
        return self.profiler.profile(dataset)

    def capabilities(self) -> dict[str, bool]:
        """Return the currently available public SAIDA capabilities."""
        return {
            "analyze": True,
            "profile": True,
            "load_context": True,
            "train": False,
            "predict": False,
            "forecast": False,
            "llm_prompting": bool(self.llm_provider and self.config.llm.use_for_prompting),
            "llm_reasoning": bool(self.llm_provider and self.config.llm.use_for_reasoning),
        }

    def analyze(self, dataset: Dataset, question: str) -> AnalysisResult:
        """Run an end-to-end deterministic analysis workflow."""
        self._validate_dataset(dataset)
        trace = [self._trace("adapter", "dataset loaded", {"dataset": dataset.name})]
        if dataset.context is not None:
            trace.append(self._trace("context", "context attached", {"metric_count": len(dataset.context.metric_definitions)}))

        profile = self.profile(dataset)
        trace.append(self._trace("profiling", "profile generated", {"row_count": profile.row_count}))

        request, request_warnings, llm_trace_event = self._build_request(question, dataset, profile)
        if llm_trace_event is not None:
            trace.append(llm_trace_event)
        trace.append(self._trace("nlp", "request normalized", {"task_type": request.task_type_hint, "target": request.target}))

        if request.options.get("analysis_outcome") == "clarify":
            plan = AnalysisPlan(
                task_type="clarification",
                rationale="Optional LLM interpretation requested clarification before planning.",
                steps=[],
                warnings=request_warnings,
            )
            summary = request.options.get("llm_message") or "We need clarification before running this analysis."
            trace.append(self._trace("results", "clarification returned", {"summary_length": len(summary)}))
            return self.results.build_analysis_result(summary, None, None, "deterministic", [], [], request_warnings, plan, request, profile, trace)

        if request.options.get("analysis_outcome") == "refuse":
            plan = AnalysisPlan(
                task_type="unavailable",
                rationale="Optional LLM interpretation declined the request before planning.",
                steps=[],
                warnings=request_warnings,
            )
            summary = request.options.get("llm_message") or "We are not able to provide this information at this time."
            trace.append(self._trace("results", "refusal returned", {"summary_length": len(summary)}))
            return self.results.build_analysis_result(summary, None, None, "deterministic", [], [], request_warnings, plan, request, profile, trace)

        plan = self.planner.build_plan(request, profile, dataset.context)
        self.planner.validate(plan)
        trace.append(self._trace("planning", "plan validated", {"task_type": plan.task_type, "step_count": len(plan.steps)}))

        metrics = []
        tables = []
        warnings = self._merge_warnings(profile.warnings, request_warnings, plan.warnings)

        for step in plan.steps:
            if step.tool_family == "duckdb":
                if step.action == "dataset_summary":
                    step_metrics, step_tables = self.duckdb.dataset_summary(
                        dataset.data,
                        step.parameters.get("target"),
                        step.parameters.get("filters"),
                    )
                    metrics.extend(step_metrics)
                    tables.extend(step_tables)
                elif step.action == "row_count":
                    metrics.extend(
                        self.duckdb.row_count(
                            dataset.data,
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "count_rows_by_group":
                    tables.append(
                        self.duckdb.count_rows_by_group(
                            dataset.data,
                            step.parameters["group_by"],
                            step.parameters.get("filters"),
                            step.parameters.get("ascending", False),
                            step.parameters.get("limit"),
                        )
                    )
                elif step.action == "distinct_values":
                    tables.append(
                        self.duckdb.distinct_values(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "time_coverage":
                    tables.append(
                        self.duckdb.time_coverage(
                            dataset.data,
                            step.parameters["time_column"],
                            step.parameters.get("mode", "years_present"),
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "aggregate_value":
                    step_metrics = self.duckdb.aggregate_value(
                        dataset.data,
                        step.parameters["target"],
                        step.parameters["aggregation"],
                        step.parameters.get("filters"),
                    )
                    metrics.extend(step_metrics)
                elif step.action == "ranked_rows":
                    tables.append(
                        self.duckdb.ranked_rows(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters.get("filters"),
                            step.parameters.get("ascending", False),
                            step.parameters.get("limit", 5),
                        )
                    )
                elif step.action == "time_trend":
                    tables.append(
                        self.duckdb.time_trend(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["time_column"],
                            step.parameters.get("aggregation", "sum"),
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "group_breakdown":
                    tables.append(
                        self.duckdb.group_breakdown(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"],
                            step.parameters.get("aggregation", "sum"),
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "ranked_breakdown":
                    tables.append(
                        self.duckdb.ranked_breakdown(
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
                        self.duckdb.grouped_period_comparison(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"],
                            step.parameters["time_column"],
                            step.parameters["time_reference"],
                            step.parameters.get("aggregation", "sum"),
                            step.parameters.get("filters"),
                        )
                    )
                elif step.action == "top_movers":
                    tables.append(
                        self.duckdb.top_movers(
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
                        self.duckdb.contribution_breakdown(
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
                        self.duckdb.period_comparison(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["time_column"],
                            step.parameters["time_reference"],
                            step.parameters.get("aggregation", "sum"),
                            step.parameters.get("filters"),
                        )
                    )
            elif step.tool_family == "stats":
                if step.action == "missingness_summary":
                    tables.append(self.stats.missingness_summary(dataset.data))
                elif step.action == "numeric_summary":
                    tables.append(self.stats.numeric_summary(dataset.data))
                elif step.action == "distribution_summary":
                    distribution_table = self.stats.distribution_summary(dataset.data, step.parameters["target"])
                    if distribution_table is not None:
                        tables.append(distribution_table)
                elif step.action == "target_correlation":
                    correlation_table = self.stats.correlation_matrix(dataset.data, step.parameters.get("target"))
                    if correlation_table is not None:
                        tables.append(correlation_table)
                elif step.action == "anomaly_summary":
                    anomaly_table = self.stats.anomaly_summary(
                        dataset.data,
                        step.parameters["target"],
                        step.parameters.get("time_column"),
                    )
                    if anomaly_table is not None:
                        tables.append(anomaly_table)
                elif step.action == "time_series_diagnostics":
                    diagnostics_table = self.stats.time_series_diagnostics(
                        dataset.data,
                        step.parameters["target"],
                        step.parameters["time_column"],
                    )
                    if diagnostics_table is not None:
                        tables.append(diagnostics_table)
                elif step.action == "group_mean_comparison":
                    comparison_table = self.stats.group_mean_comparison(
                        dataset.data,
                        step.parameters["target"],
                        step.parameters["group_column"],
                    )
                    if comparison_table is not None:
                        tables.append(comparison_table)
                elif step.action == "t_test":
                    tables.append(
                        self.stats.t_test(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"][0],
                            step.parameters.get("alpha", 0.05),
                        )
                    )
                elif step.action == "chi_square":
                    comparison_columns = step.parameters.get("comparison_columns", [])
                    tables.append(
                        self.stats.chi_square_test(
                            dataset.data,
                            comparison_columns[0],
                            comparison_columns[1],
                            step.parameters.get("alpha", 0.05),
                        )
                    )
                elif step.action == "anova":
                    tables.append(
                        self.stats.anova_test(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"][0],
                            step.parameters.get("alpha", 0.05),
                        )
                    )
                elif step.action == "mann_whitney":
                    tables.append(
                        self.stats.mann_whitney_test(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"][0],
                            step.parameters.get("alpha", 0.05),
                        )
                    )
                elif step.action == "confidence_interval":
                    tables.append(
                        self.stats.confidence_interval(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters.get("confidence_level", 0.95),
                        )
                    )
                elif step.action == "regression_significance":
                    tables.append(
                        self.stats.regression_significance(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters.get("feature_columns", []),
                            step.parameters.get("alpha", 0.05),
                        )
                    )
                elif step.action == "significance_inference":
                    tables.append(
                        self.stats.group_significance_test(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"][0],
                            step.parameters.get("alpha", 0.05),
                        )
                    )
                elif step.action == "power_analysis":
                    tables.append(
                        self.stats.power_analysis(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"][0],
                            step.parameters.get("alpha", 0.05),
                        )
                    )
                elif step.action == "sample_size_estimate":
                    tables.append(
                        self.stats.sample_size_estimate(
                            dataset.data,
                            step.parameters["target"],
                            step.parameters["group_by"][0],
                            step.parameters.get("alpha", 0.05),
                            step.parameters.get("desired_power", 0.80),
                        )
                    )
            elif step.tool_family == "metadata":
                tables.append(self._metadata_table(step.action, profile))
            trace.append(self._trace("compute", f"executed {step.action}", step.parameters))

        deterministic_summary = self.summarizer.summarize(plan, metrics, tables, warnings, request, profile, dataset.context)
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
        return self.results.build_analysis_result(
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
            request, warnings = self.normalizer.normalize(question, dataset, profile, dataset.context)
            return request, warnings, None

        try:
            proposal = self.llm_provider.interpret_prompt(
                question=question,
                dataset_name=dataset.name,
                profile_summary=self._profile_summary(profile),
                context_summary=self._context_summary(dataset.context),
            )
        except ReasoningError:
            request, warnings = self.normalizer.normalize(question, dataset, profile, dataset.context)
            warnings.append("Optional LLM prompting failed; falling back to deterministic request normalization.")
            return request, warnings, self._trace("llm", "prompt interpretation failed", {"fallback": "rules"})

        if proposal is None:
            request, warnings = self.normalizer.normalize(question, dataset, profile, dataset.context)
            warnings.append("Optional LLM prompting was unavailable; falling back to deterministic request normalization.")
            return request, warnings, self._trace("llm", "prompt interpretation skipped", {"fallback": "rules"})

        if proposal.status in {"clarify", "refuse"}:
            fallback_request, fallback_warnings = self.normalizer.normalize(question, dataset, profile, dataset.context)
            if self._is_confident_deterministic_request(fallback_request, fallback_warnings):
                fallback_warnings.append(
                    "Optional LLM prompting requested clarification, but deterministic request normalization found a valid intent."
                )
                return (
                    fallback_request,
                    fallback_warnings,
                    self._trace("llm", "clarification overridden by deterministic request normalization", {"status": proposal.status}),
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

        request, warnings = self.normalizer.normalize_with_proposal(question, dataset, profile, proposal, dataset.context)
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

    def _validate_dataset(self, dataset: Dataset) -> None:
        if not isinstance(dataset.data, pd.DataFrame):
            raise ValidationError("Dataset.data must be a pandas DataFrame.")
        if dataset.data.empty:
            raise ValidationError("Cannot analyze an empty dataset.")
        if len(dataset.data.columns) == 0:
            raise ValidationError("Cannot analyze a dataset with no columns.")
        duplicate_columns = dataset.data.columns[dataset.data.columns.duplicated()].tolist()
        if duplicate_columns:
            joined = ", ".join(str(column_name) for column_name in duplicate_columns)
            raise ValidationError(f"Dataset contains duplicate column names: {joined}")

    def _metadata_table(self, action: str, profile: DatasetProfile) -> TableArtifact:
        if action == "column_inventory":
            dataframe = pd.DataFrame({"column_name": [column.name for column in profile.columns]})
            return TableArtifact(name="column_inventory", description="Available dataset columns.", dataframe=dataframe)
        if action == "measure_inventory":
            dataframe = pd.DataFrame({"measure_column": list(profile.measure_columns)})
            return TableArtifact(name="measure_inventory", description="Detected measure columns.", dataframe=dataframe)
        if action == "dimension_inventory":
            dataframe = pd.DataFrame({"dimension_column": list(profile.dimension_columns)})
            return TableArtifact(name="dimension_inventory", description="Detected dimension columns.", dataframe=dataframe)
        if action == "time_column_inventory":
            dataframe = pd.DataFrame({"time_column": list(profile.time_columns)})
            return TableArtifact(name="time_column_inventory", description="Detected time columns.", dataframe=dataframe)
        raise ValidationError(f"Unsupported metadata action: {action}")
