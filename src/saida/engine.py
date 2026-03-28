"""Main plan-first orchestration runtime for SAIDA."""

from __future__ import annotations

from copy import deepcopy

from saida.adapters import ComputeRequest, DuckDBAdapter, MetadataComputeAdapter, MlAdapter, StatsModelsAdapter
from saida.config import SaidaConfig
from saida.core import (
    BackendRouter,
    PlanValidator,
    get_analytics_registry,
    get_prompt_family_catalog,
    ResultCanonicalizer,
    SchemaDiscoveryService,
    SourceContextParser,
    PromptCapabilityContract,
)
from saida.exceptions import ReasoningError, ValidationError
from saida.llm import BaseLlmProvider, ResponseContext, build_llm_provider
from saida.outputs import JsonOutputAdapter, OutputInterface, SummaryFormatter, SummaryOutputAdapter
from saida.core.contracts import (
    AnalysisInterpretation,
    AnalysisResult,
    AnalysisPlan,
    Dataset,
    DatasetProfile,
    ExecutionTraceEvent,
    ForecastAnalysisResult,
    ModelSpec,
    Metric,
    PlanInput,
    PredictionResult,
    SourceContext,
    TableArtifact,
    TrainResult,
)


class Saida:
    """Coordinate SAIDA's plan-first framework layers through a simple Python API.

    Core framework path:
    - Dataset
    - AnalysisPlan
    - validation
    - execution
    - AnalysisResult

    Prompt generation and LLM usage remain supported, but they are optional
    frontend helpers layered on top of the core execution contract via
    ``PromptAnalysisFrontend``.
    """

    HIGH_CARDINALITY_DISTINCT_RATIO = 0.8

    def __init__(self, config: SaidaConfig | None = None, llm_provider: BaseLlmProvider | None = None) -> None:
        self.config = config or SaidaConfig()
        self.discovery = SchemaDiscoveryService()
        self.validator = PlanValidator()
        self.duckdb = DuckDBAdapter()
        self.metadata = MetadataComputeAdapter()
        self.stats = StatsModelsAdapter()
        self.ml = MlAdapter()
        self.router = BackendRouter(
            duckdb_adapter=self.duckdb,
            metadata_adapter=self.metadata,
            stats_adapter=self.stats,
            ml_adapter=self.ml,
        )
        self.summary_formatter = SummaryFormatter()
        self.output_adapters: dict[str, OutputInterface] = {
            "json": JsonOutputAdapter(),
            "summary": SummaryOutputAdapter(),
        }
        self.result_canonicalizer = ResultCanonicalizer()
        self.llm_provider = llm_provider or build_llm_provider(self.config.llm)

    def profile(self, dataset: Dataset) -> DatasetProfile:
        """Profile a dataset deterministically."""
        return self.discovery.profile(dataset)

    def capabilities(self) -> dict[str, bool]:
        """Return the currently available public SAIDA capabilities."""
        return {
            "execute_plan": True,
            "profile": True,
            "load_context": True,
            "render_output": True,
            "train": False,
            "predict": False,
            "forecast": False,
            "capability_registry": True,
            "llm_reasoning": bool(self.llm_provider and self.config.llm.use_for_reasoning),
        }

    def render_output(
        self,
        result: AnalysisResult,
        *,
        output_format: str = "json",
        adapter: OutputInterface | None = None,
    ) -> object:
        """Render an AnalysisResult through a registered output adapter."""
        selected_adapter = adapter or self.output_adapters.get(output_format)
        if selected_adapter is None:
            raise ValidationError(f"No output adapter is registered for format '{output_format}'.")
        return selected_adapter.render(result)

    def execute_plan(
        self,
        dataset: Dataset,
        plan: AnalysisPlan,
    ) -> AnalysisResult:
        """Execute a validated AnalysisPlan deterministically through the core framework path."""
        self.validator.validate_dataset(dataset)
        trace = [self._trace("adapter", "dataset loaded", {"dataset": dataset.name})]
        if dataset.context is not None:
            trace.append(self._trace("context", "context attached", {"metric_count": len(dataset.context.metric_definitions)}))

        profile = self.profile(dataset)
        trace.append(self._trace("profiling", "profile generated", {"row_count": profile.row_count}))

        bound_plan = self._bind_plan_to_dataset(deepcopy(plan), dataset, profile)
        interpretation = self._interpretation_from_plan(bound_plan, profile=profile, dataset_name=dataset.name)
        trace.append(
            self._trace(
                "contract",
                "interpretation derived from plan",
                {"prompt_family": interpretation.prompt_family, "intent_name": interpretation.intent_name},
            )
        )
        trace.append(
            self._trace(
                "planning",
                "plan supplied for direct execution",
                {"task_type": bound_plan.task_type, "step_count": len(bound_plan.steps)},
            )
        )

        return self._execute_prepared_plan(
            dataset=dataset,
            question=interpretation.question,
            interpretation=interpretation,
            profile=profile,
            plan=bound_plan,
            trace=trace,
            capability_contract=None,
            warning_groups=(profile.warnings,),
        )
    def _execute_prepared_plan(
        self,
        dataset: Dataset,
        question: str,
        interpretation: AnalysisInterpretation,
        profile: DatasetProfile,
        plan: AnalysisPlan,
        trace: list[ExecutionTraceEvent],
        capability_contract: PromptCapabilityContract | None,
        warning_groups: tuple[list[str], ...] = (),
    ) -> AnalysisResult:
        self.validator.validate_plan(plan, dataset=dataset, profile=profile, router=self.router)
        trace.append(self._trace("planning", "plan validated", {"task_type": plan.task_type, "step_count": len(plan.steps)}))

        metrics: list[Metric] = []
        tables: list[TableArtifact] = []
        warnings = self._merge_warnings(*warning_groups, plan.warnings)

        for step in plan.steps:
            self._execute_step(dataset, profile, step, metrics, tables)
            trace.append(self._trace("compute", f"executed {step.action}", step.parameters))

        deterministic_summary = self.summary_formatter.summarize(
            plan,
            metrics,
            tables,
            warnings,
            interpretation,
            profile,
            dataset.context,
        )
        summary, llm_summary, summary_source, llm_reasoning_warning = self._build_summary(
            question,
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
            interpretation,
            profile,
            trace,
            capability_contract,
        )

    def _execute_step(
        self,
        dataset: Dataset,
        profile: DatasetProfile,
        step: object,
        metrics: list[Metric],
        tables: list[TableArtifact],
    ) -> None:
        adapter = self.router.route(step.tool_family)
        response = adapter.execute(
            ComputeRequest(
                method_id=step.method_id or step.action,
                dataset=dataset,
                profile=profile,
                parameters=step.parameters,
            )
        )
        metrics.extend(response.metrics)
        tables.extend(response.tables)

    def _bind_plan_to_dataset(
        self,
        plan: AnalysisPlan,
        dataset: Dataset,
        profile: DatasetProfile,
        interpretation: AnalysisInterpretation | None = None,
    ) -> AnalysisPlan:
        analytics_registry = get_analytics_registry()
        if not plan.dataset_refs:
            plan.dataset_refs = [dataset.name]
        elif dataset.name not in set(plan.dataset_refs):
            plan.dataset_refs = [*plan.dataset_refs, dataset.name]

        if not plan.inputs:
            plan.inputs = [
                PlanInput(
                    input_id="primary_dataset",
                    kind="dataset",
                    ref=dataset.name,
                    metadata={"source_type": dataset.source_type},
                )
            ]

        plan.metadata = deepcopy(plan.metadata)
        plan.metadata["dataset_name"] = dataset.name
        plan.metadata["dataset_source_type"] = dataset.source_type
        if interpretation is not None:
            plan.metadata["origin_question"] = interpretation.question
            plan.metadata["prompt_family"] = interpretation.prompt_family
            plan.metadata["intent_name"] = interpretation.intent_name
            plan.metadata["interpretation_snapshot"] = self._interpretation_snapshot(interpretation)
        elif isinstance(plan.metadata.get("request_snapshot"), dict) and "interpretation_snapshot" not in plan.metadata:
            plan.metadata["interpretation_snapshot"] = deepcopy(plan.metadata["request_snapshot"])
        plan.metadata.setdefault(
            "profile_summary",
            {
                "dataset_name": profile.dataset_name,
                "row_count": profile.row_count,
                "column_count": profile.column_count,
            },
        )

        for index, step in enumerate(plan.steps, start=1):
            method_id = step.method_id or step.action
            method_spec = analytics_registry.get_method(method_id)
            if step.family is None:
                step.family = (
                    method_spec.family_id
                    if method_spec is not None
                    else self._string_or_none(plan.metadata.get("prompt_family"))
                    or self._string_or_none(plan.metadata.get("intent_name"))
                    or plan.task_type
                )
            if step.method_id is None:
                step.method_id = method_id
            if not step.output_refs:
                step.output_refs = [step.step_id]
            if step.expected_output is None:
                inferred_output = self._infer_step_expected_output(step)
                if inferred_output is not None:
                    step.expected_output = inferred_output
            step.metadata = deepcopy(step.metadata)
            step.metadata.setdefault("execution_order", index)

        bound_interpretation = self._interpretation_from_plan(plan, profile=profile, dataset_name=dataset.name)
        plan.metadata["origin_question"] = bound_interpretation.question
        plan.metadata["prompt_family"] = bound_interpretation.prompt_family
        plan.metadata["intent_name"] = bound_interpretation.intent_name
        plan.metadata["interpretation_snapshot"] = self._interpretation_snapshot(bound_interpretation)
        if plan.plan_id is None:
            plan.plan_id = self._deterministic_plan_id(plan, dataset, bound_interpretation)
        if plan.expected_result_name is None:
            plan.expected_result_name = self._infer_expected_result_name(bound_interpretation, plan)
        if plan.expected_result_shape is None:
            plan.expected_result_shape = self._infer_expected_result_shape(bound_interpretation, plan)
        return plan

    def _interpretation_from_plan(
        self,
        plan: AnalysisPlan,
        profile: DatasetProfile | None = None,
        dataset_name: str | None = None,
    ) -> AnalysisInterpretation:
        interpretation_snapshot = plan.metadata.get("interpretation_snapshot")
        if isinstance(interpretation_snapshot, dict):
            interpretation = AnalysisInterpretation.from_snapshot(interpretation_snapshot)
        else:
            legacy_request_snapshot = plan.metadata.get("request_snapshot")
            if isinstance(legacy_request_snapshot, dict):
                interpretation = AnalysisInterpretation.from_snapshot(legacy_request_snapshot)
            else:
                question = str(plan.metadata.get("origin_question") or f"Execute {plan.plan_id or plan.task_type} plan")
                interpretation = AnalysisInterpretation(
                    question=question,
                    task_type_hint=plan.task_type,
                    options={},
                )
                interpretation.prompt_family = self._string_or_none(plan.metadata.get("prompt_family"))
                interpretation.intent_name = self._string_or_none(plan.metadata.get("intent_name"))
                if plan.steps:
                    inferred = self._interpretation_fields_from_step(plan.steps[0], plan)
                    interpretation.prompt_family = inferred.get("prompt_family") or interpretation.prompt_family
                    interpretation.intent_name = inferred.get("intent_name") or interpretation.intent_name
                    interpretation.target = inferred.get("target")
                    interpretation.aggregation = inferred.get("aggregation")
                    interpretation.filters = inferred.get("filters")
                    interpretation.group_by = inferred.get("group_by")
                    interpretation.time_reference = inferred.get("time_reference")
                    interpretation.horizon = inferred.get("horizon")
                    interpretation.options.update(inferred.get("options", {}))

        interpretation.options = deepcopy(interpretation.options)
        if dataset_name is not None:
            interpretation.options.setdefault("dataset", dataset_name)
        interpretation.options.setdefault("plan_execution", True)
        if interpretation.prompt_family is None and plan.expected_result_name:
            interpretation.prompt_family = plan.expected_result_name
        if interpretation.intent_name is None:
            interpretation.intent_name = interpretation.prompt_family
        if profile is not None and interpretation.target is not None:
            if interpretation.target not in {column.name for column in profile.columns}:
                interpretation.target = None
        return interpretation

    def _interpretation_fields_from_step(self, step: object, plan: AnalysisPlan) -> dict[str, object]:
        if step.action == "row_count":
            return {
                "prompt_family": "row_count",
                "intent_name": "row_count",
                "aggregation": "count",
                "filters": deepcopy(step.parameters.get("filters")),
            }
        if step.action == "count_rows_by_group":
            prompt_family = "representation_ranking" if step.parameters.get("limit") else "grouped_entity_count"
            return {
                "prompt_family": prompt_family,
                "intent_name": "representation_ranking" if prompt_family == "representation_ranking" else None,
                "group_by": list(step.parameters.get("group_by") or []),
                "filters": deepcopy(step.parameters.get("filters")),
            }
        if step.action == "distinct_values":
            return {
                "prompt_family": "distinct_value_listing",
                "intent_name": "distinct_values",
                "target": step.parameters.get("target"),
                "filters": deepcopy(step.parameters.get("filters")),
            }
        if step.action == "distinct_value_count":
            return {
                "prompt_family": "distinct_value_count",
                "intent_name": "distinct_value_count",
                "target": step.parameters.get("target"),
                "filters": deepcopy(step.parameters.get("filters")),
            }
        if step.action == "tabular_query":
            return {
                "prompt_family": "tabular_record_retrieval",
                "intent_name": "tabular_query",
                "filters": deepcopy(step.parameters.get("filters")),
                "options": {
                    "selected_columns": list(step.parameters.get("selected_columns") or []),
                    "sort_by": step.parameters.get("sort_by"),
                    "sort_direction": step.parameters.get("sort_direction", "asc"),
                    "limit": step.parameters.get("limit"),
                    "page": step.parameters.get("page", 1),
                    "page_size": step.parameters.get("page_size", 50),
                },
            }
        if step.action == "grouped_tabular_query":
            return {
                "prompt_family": "grouped_tabular_query",
                "intent_name": "grouped_tabular_query",
                "target": step.parameters.get("target"),
                "aggregation": step.parameters.get("aggregation"),
                "group_by": list(step.parameters.get("group_by") or []),
                "filters": deepcopy(step.parameters.get("filters")),
                "options": {
                    "sort_by": step.parameters.get("sort_by"),
                    "sort_direction": step.parameters.get("sort_direction", "desc"),
                    "limit": step.parameters.get("limit"),
                    "page": step.parameters.get("page", 1),
                    "page_size": step.parameters.get("page_size", 50),
                    "intent_name": "grouped_tabular_query",
                },
            }
        if step.action == "column_type_inventory":
            target = step.parameters.get("target")
            return {
                "prompt_family": "column_type_lookup" if isinstance(target, str) else "column_type_inventory",
                "intent_name": "column_type_inventory",
                "target": target,
                "options": deepcopy(step.parameters),
            }
        if step.action == "time_bucket_counts":
            bucket = step.parameters.get("bucket", "year")
            return {
                "prompt_family": "time_bucket_counts",
                "intent_name": "time_bucket_counts",
                "target": step.parameters.get("time_column"),
                "options": {
                    **deepcopy(step.parameters),
                    "time_bucket": bucket,
                },
            }
        if step.action == "time_bucket_breakdown":
            bucket = step.parameters.get("bucket", "month")
            return {
                "prompt_family": "time_bucket_breakdown",
                "intent_name": "time_bucket_breakdown",
                "target": step.parameters.get("target"),
                "aggregation": step.parameters.get("aggregation"),
                "group_by": list(step.parameters.get("group_by") or []),
                "filters": deepcopy(step.parameters.get("filters")),
                "options": {
                    **deepcopy(step.parameters),
                    "time_bucket": bucket,
                },
            }
        if step.tool_family == "metadata":
            return {
                "prompt_family": step.action,
                "intent_name": step.action,
                "target": step.parameters.get("target"),
                "options": deepcopy(step.parameters),
            }
        if step.action == "aggregate_value":
            return {
                "prompt_family": "metric_aggregate",
                "target": step.parameters.get("target"),
                "aggregation": step.parameters.get("aggregation"),
                "filters": deepcopy(step.parameters.get("filters")),
            }
        if step.action == "ranked_rows":
            return {
                "prompt_family": "row_ranking",
                "intent_name": "row_ranking",
                "target": step.parameters.get("target"),
                "filters": deepcopy(step.parameters.get("filters")),
            }
        if step.action == "ranked_breakdown":
            return {
                "prompt_family": "group_ranking",
                "intent_name": "group_ranking",
                "target": step.parameters.get("target"),
                "aggregation": step.parameters.get("aggregation"),
                "group_by": list(step.parameters.get("group_by") or []),
                "filters": deepcopy(step.parameters.get("filters")),
            }
        if step.action == "row_existence":
            return {
                "prompt_family": "row_existence_check",
                "intent_name": "existence_check",
                "filters": deepcopy(step.parameters.get("filters")),
                "options": {"existence_mode": "row_existence"},
            }
        if step.action == "time_value_exists":
            return {
                "prompt_family": "time_value_verification",
                "intent_name": "existence_check",
                "filters": deepcopy(step.parameters.get("filters")),
                "time_reference": deepcopy(step.parameters.get("time_reference")),
                "options": {"existence_mode": "time_value"},
            }
        if step.action == "null_check":
            return {
                "prompt_family": "null_verification",
                "intent_name": "existence_check",
                "target": step.parameters.get("target"),
                "filters": deepcopy(step.parameters.get("filters")),
                "options": {"existence_mode": "null_check"},
            }
        if step.action == "threshold_check":
            return {
                "prompt_family": "threshold_verification",
                "intent_name": "existence_check",
                "target": step.parameters.get("target"),
                "filters": deepcopy(step.parameters.get("filters")),
                "options": {"existence_mode": "threshold_check"},
            }
        if step.action == "column_property_check":
            return {
                "prompt_family": "column_property_check",
                "intent_name": "existence_check",
                "target": step.parameters.get("target"),
                "options": {**deepcopy(step.parameters), "existence_mode": "column_property_check"},
            }
        if step.action == "column_presence_check":
            return {
                "prompt_family": "column_presence_check",
                "intent_name": "existence_check",
                "options": {**deepcopy(step.parameters), "existence_mode": "column_presence_check"},
            }
        return {
            "prompt_family": self._string_or_none(plan.expected_result_name),
            "intent_name": self._string_or_none(plan.metadata.get("intent_name")),
            "options": {},
        }

    def _interpretation_snapshot(self, interpretation: AnalysisInterpretation) -> dict[str, object]:
        return interpretation.to_dict()

    def _deterministic_plan_id(
        self,
        plan: AnalysisPlan,
        dataset: Dataset,
        interpretation: AnalysisInterpretation,
    ) -> str:
        action_signature = "-".join((step.method_id or step.action) for step in plan.steps[:3]) or plan.task_type
        family = interpretation.prompt_family or interpretation.intent_name or plan.task_type
        return f"{dataset.name}:{family}:{action_signature}"

    def _infer_expected_result_name(self, interpretation: AnalysisInterpretation, plan: AnalysisPlan) -> str | None:
        if interpretation.target and interpretation.aggregation and not interpretation.group_by:
            return f"{interpretation.target}_{interpretation.aggregation}"
        if interpretation.prompt_family == "tabular_record_retrieval":
            return "tabular_query"
        if interpretation.prompt_family == "grouped_tabular_query":
            return "grouped_tabular_query"
        if interpretation.prompt_family:
            return interpretation.prompt_family
        if plan.steps:
            return plan.steps[0].action
        return None

    def _infer_expected_result_shape(self, interpretation: AnalysisInterpretation, plan: AnalysisPlan) -> str | None:
        if interpretation.prompt_family:
            family_spec = get_prompt_family_catalog().get(interpretation.prompt_family)
            if family_spec is not None and family_spec.primary_result_shapes:
                return self._normalize_expected_result_shape(family_spec.primary_result_shapes[0])
        if plan.steps:
            method_spec = get_analytics_registry().get_method(plan.steps[0].method_id or plan.steps[0].action)
            if method_spec is not None and method_spec.output_shapes:
                return self._normalize_expected_result_shape(method_spec.output_shapes[0])
        if plan.steps:
            return "table"
        return None

    def _normalize_expected_result_shape(self, shape: str) -> str:
        if shape in {"count", "aggregate"}:
            return "scalar"
        if shape in {"recordset", "timeseries", "statistical_test"}:
            return "table"
        return shape

    def _infer_step_expected_output(self, step: object) -> dict[str, object] | None:
        method_spec = get_analytics_registry().get_method(step.method_id or step.action)
        if method_spec is not None and method_spec.output_shapes:
            logical_shape = method_spec.output_shapes[0]
            physical_shape = "scalar" if logical_shape in {"scalar", "count", "aggregate"} else "recordset"
            return {"output_id": step.step_id, "logical_shape": logical_shape, "physical_shape": physical_shape}
        return None

    def _string_or_none(self, value: object) -> str | None:
        return value if isinstance(value, str) else None

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

    def _build_summary(
        self,
        question: str,
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
