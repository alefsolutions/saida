"""Canonicalize backend outputs into top-level result objects."""

from __future__ import annotations

from dataclasses import asdict
import math
from typing import Any

import pandas as pd

from saida.core.artifacts import infer_semantic_kind
from saida.core.public_response import build_public_analysis_response, is_synthetic_plan_question
from saida.core.contracts import (
    AnalysisInterpretation,
    AnalysisPlan,
    AnalysisResult,
    DatasetProfile,
    ExecutionTraceEvent,
    ForecastAnalysisResult,
    ForecastResult,
    Metric,
    ModelTrainingResult,
    NodeExecutionResult,
    ExecutionArtifact,
    TableArtifact,
    TrainResult,
)


class ResultCanonicalizer:
    """Canonicalize structured outputs into analytical result schemas."""

    def build_analysis_result(
        self,
        summary: str,
        deterministic_summary: str | None,
        llm_summary: str | None,
        summary_source: str,
        metrics: list[Metric],
        tables: list[TableArtifact],
        warnings: list[str],
        plan: AnalysisPlan,
        request: AnalysisInterpretation,
        profile: DatasetProfile,
        trace: list[ExecutionTraceEvent],
        prompt_contract: object | None = None,
        node_results: list[NodeExecutionResult] | None = None,
        artifact_index: dict[str, ExecutionArtifact] | None = None,
    ) -> AnalysisResult:
        resolved_node_results = list(node_results or [])
        resolved_artifact_index = dict(artifact_index or {})
        artifacts = self._build_analysis_artifacts(
            metrics,
            tables,
            warnings,
            plan,
            request,
            profile,
            trace,
            deterministic_summary,
            llm_summary,
            summary_source,
            prompt_contract,
            resolved_node_results,
            resolved_artifact_index,
        )
        response = self._build_analysis_response(
            summary,
            metrics,
            tables,
            warnings,
            plan,
            request,
            profile,
            trace,
            deterministic_summary,
            llm_summary,
            summary_source,
            prompt_contract,
            resolved_node_results,
            resolved_artifact_index,
        )
        public_response = self._build_public_analysis_response(
            summary,
            llm_summary,
            plan,
            request,
            response,
        )
        return AnalysisResult(
            summary=summary,
            deterministic_summary=deterministic_summary,
            llm_summary=llm_summary,
            summary_source=summary_source,
            metrics=metrics,
            tables=tables,
            warnings=warnings,
            plan=plan,
            trace=trace,
            node_results=resolved_node_results,
            artifact_index=resolved_artifact_index,
            artifacts=artifacts,
            public_response=public_response,
            response=response,
        )

    def build_train_result(
        self,
        summary: str,
        training: ModelTrainingResult,
        trace: list[ExecutionTraceEvent],
    ) -> TrainResult:
        return TrainResult(summary=summary, training=training, trace=trace)

    def build_forecast_result(
        self,
        summary: str,
        forecast: ForecastResult,
        trace: list[ExecutionTraceEvent],
    ) -> ForecastAnalysisResult:
        return ForecastAnalysisResult(summary=summary, forecast=forecast, trace=trace)

    def _build_analysis_artifacts(
        self,
        metrics: list[Metric],
        tables: list[TableArtifact],
        warnings: list[str],
        plan: AnalysisPlan,
        request: AnalysisInterpretation,
        profile: DatasetProfile,
        trace: list[ExecutionTraceEvent],
        deterministic_summary: str | None,
        llm_summary: str | None,
        summary_source: str,
        prompt_contract: object | None,
        node_results: list[NodeExecutionResult],
        artifact_index: dict[str, ExecutionArtifact],
    ) -> dict[str, object]:
        metric_lookup = {metric.name: metric.value for metric in metrics}
        table_index = {
            table.name: {
                "rows": int(len(table.dataframe)),
                "columns": list(table.dataframe.columns),
                "description": table.description,
                "metadata": dict(table.metadata),
            }
            for table in tables
        }
        trace_stages = [event.stage for event in trace]

        return self._json_safe(
            {
            "request": asdict(request),
            "prompt_contract": self._contract_to_dict(prompt_contract),
            "profile": {
                "dataset_name": profile.dataset_name,
                "row_count": profile.row_count,
                "column_count": profile.column_count,
                "measure_columns": list(profile.measure_columns),
                "dimension_columns": list(profile.dimension_columns),
                "time_columns": list(profile.time_columns),
                "identifier_columns": list(profile.identifier_columns),
                "warnings": list(profile.warnings),
            },
            "metric_lookup": metric_lookup,
            "table_index": table_index,
            "warning_count": len(warnings),
            "trace_stages": trace_stages,
            "plan_step_ids": [step.step_id for step in plan.steps],
            "node_results": [result.to_dict() for result in node_results],
            "artifact_ids": list(artifact_index),
            "deterministic_summary": deterministic_summary,
            "llm_summary": llm_summary,
            "summary_source": summary_source,
            }
        )

    def _build_analysis_response(
        self,
        summary: str,
        metrics: list[Metric],
        tables: list[TableArtifact],
        warnings: list[str],
        plan: AnalysisPlan,
        request: AnalysisInterpretation,
        profile: DatasetProfile,
        trace: list[ExecutionTraceEvent],
        deterministic_summary: str | None,
        llm_summary: str | None,
        summary_source: str,
        prompt_contract: object | None,
        node_results: list[NodeExecutionResult],
        artifact_index: dict[str, ExecutionArtifact],
    ) -> dict[str, object]:
        operations = [
            {
                "step_id": step.step_id,
                "family": step.family,
                "method_id": step.method_id,
                "tool_family": step.tool_family,
                "action": step.action,
                "depends_on": list(step.depends_on),
                "output_refs": list(step.output_refs),
                "expected_output": dict(step.expected_output) if step.expected_output is not None else None,
                "description": step.description,
                "parameters": dict(step.parameters),
                "metadata": dict(step.metadata),
            }
            for step in plan.steps
        ]
        metric_lookup = {metric.name: metric.value for metric in metrics}
        output_declarations = self._output_declaration_map(plan)
        primary_result = self._select_primary_result(plan, request, metrics, tables, artifact_index, output_declarations)
        table_entries = [self._table_entry(table) for table in tables]
        terminal_ref = self._resolve_terminal_output_ref(plan, artifact_index)
        secondary_output_refs = self._secondary_output_refs(plan, artifact_index)
        serialized_artifact_index = {
            artifact_id: self._serialized_artifact_payload(
                artifact_id,
                artifact,
                plan,
                declaration=output_declarations.get(artifact_id),
                terminal_ref=terminal_ref,
                secondary_output_refs=secondary_output_refs,
            )
            for artifact_id, artifact in artifact_index.items()
        }
        secondary_outputs = self._secondary_terminal_outputs(plan, artifact_index, output_declarations)
        terminal_lineage = self._terminal_lineage(plan, terminal_ref)
        graph_summary = self._graph_execution_summary(plan, artifact_index, secondary_outputs, terminal_ref)
        execution_model = plan.metadata.get("execution_model") if isinstance(plan.metadata, dict) else None

        return self._json_safe(
            {
            "schema_version": "saida.response.v2",
            "status": self._resolve_status(plan),
            "request": {
                "question": request.question,
                "dataset": {
                    "name": profile.dataset_name,
                },
            },
            "interpretation": {
                "prompt_family": request.prompt_family,
                "intent_name": request.intent_name,
                "semantic_intent": dict(request.options.get("semantic_intent") or {}),
                "task_type": plan.task_type,
                "target": request.target,
                "aggregation": request.aggregation,
                "group_by": list(request.group_by or []),
                "filters": dict(request.filters or {}),
                "time_reference": dict(request.time_reference or {}),
                "horizon": request.horizon,
                "options": dict(request.options),
                "prompt_contract": self._contract_to_dict(prompt_contract),
            },
            "execution": {
                "status": self._resolve_status(plan),
                "plan_id": plan.plan_id,
                "plan_version": plan.version,
                "tool_families": sorted({step.tool_family for step in plan.steps}),
                "rationale": plan.rationale,
                "step_count": len(plan.steps),
                "dataset_refs": list(plan.dataset_refs),
                "inputs": [asdict(plan_input) for plan_input in plan.inputs],
                "expected_result_name": plan.expected_result_name,
                "expected_result_shape": plan.expected_result_shape,
                "steps": operations,
                "node_results": [result.to_dict() for result in node_results],
                "final_output_ref": plan.final_output_ref,
                "terminal_output_ref": terminal_ref,
                "terminal_output": primary_result,
                "secondary_outputs": secondary_outputs,
                "terminal_lineage": terminal_lineage,
                "graph_summary": graph_summary,
                "artifact_index": serialized_artifact_index,
                "execution_model": execution_model,
            },
            "result": primary_result,
            "tables": table_entries,
            "summary": {
                "summary": summary,
                "deterministic_summary": deterministic_summary,
                "llm_summary": llm_summary,
                "summary_source": summary_source,
            },
            "history": [asdict(event) for event in trace],
            "warnings": list(warnings),
            "errors": [],
            "meta": {
                "dataset": {
                    "name": profile.dataset_name,
                    "row_count": profile.row_count,
                    "column_count": profile.column_count,
                    "measure_columns": list(profile.measure_columns),
                    "dimension_columns": list(profile.dimension_columns),
                    "time_columns": list(profile.time_columns),
                    "identifier_columns": list(profile.identifier_columns),
                    "profile_warnings": list(profile.warnings),
                },
                "prompt_family": request.prompt_family,
                "prompt_contract_status": self._contract_status(prompt_contract),
                "plan_id": plan.plan_id,
                "plan_version": plan.version,
                "plan_warnings": list(plan.warnings),
                "warning_count": len(warnings),
                "metrics": [asdict(metric) for metric in metrics],
                "metric_lookup": metric_lookup,
                "artifact_ids": list(artifact_index),
                "artifact_index": serialized_artifact_index,
                "terminal_output_ref": terminal_ref,
                "secondary_output_refs": [output.get("name") for output in secondary_outputs],
                "terminal_lineage": terminal_lineage,
                "graph_summary": graph_summary,
                "execution_model": execution_model,
                "table_names": [table.name for table in tables],
            },
            }
        )

    def _build_public_analysis_response(
        self,
        summary: str,
        llm_summary: str | None,
        plan: AnalysisPlan,
        request: AnalysisInterpretation,
        debug_response: dict[str, object],
    ) -> dict[str, object]:
        return self._json_safe(
            build_public_analysis_response(
                summary=summary,
                llm_summary=llm_summary,
                plan=plan,
                request=request,
                debug_response=debug_response,
            )
        )

    def _is_synthetic_plan_question(self, plan: AnalysisPlan, request: AnalysisInterpretation) -> bool:
        return is_synthetic_plan_question(plan, request)

    def _resolve_status(self, plan: AnalysisPlan) -> str:
        if plan.task_type == "clarification":
            return "clarify"
        if plan.task_type == "unavailable":
            return "refuse"
        return "ok"

    def _select_primary_result(
        self,
        plan: AnalysisPlan,
        request: AnalysisInterpretation,
        metrics: list[Metric],
        tables: list[TableArtifact],
        artifact_index: dict[str, ExecutionArtifact],
        output_declarations: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, object]:
        if plan.final_output_ref and plan.final_output_ref in artifact_index:
            declaration = (output_declarations or {}).get(plan.final_output_ref)
            return self._execution_artifact_payload(artifact_index[plan.final_output_ref], declaration=declaration)

        candidate_keys = self._plan_result_candidate_keys(plan)

        for candidate_key in candidate_keys:
            primary_result = self._select_primary_result_for_key(candidate_key, plan, metrics, tables)
            if primary_result is not None:
                return primary_result

        return self._fallback_primary_result(plan, metrics, tables)

    def _select_primary_result_for_key(
        self,
        key: str,
        plan: AnalysisPlan,
        metrics: list[Metric],
        tables: list[TableArtifact],
    ) -> dict[str, object] | None:
        if key == "exploratory_metric_overview":
            return self._select_exploratory_metric_primary_result(plan, tables)

        direct_metric = self._metric_by_name(metrics, key)
        if direct_metric is not None:
            return self._metric_result_payload(direct_metric, logical_shape=self._logical_shape_for_metric(key))

        if key == "column_type_lookup" or key.endswith("_dtype"):
            return self._column_type_lookup_result(key, plan, tables)

        if key == "distinct_value_count" or key.endswith("_distinct_count"):
            result_name = key
            if key == "distinct_value_count":
                target = self._targeted_step_parameter(plan, {"distinct_value_count"}, "target")
                if target is not None:
                    result_name = f"{target}_distinct_count"
            return self._table_scalar_result(
                table_name="distinct_value_count",
                value_field="distinct_count",
                result_name=result_name,
                logical_shape="count",
                tables=tables,
            )

        direct_table = self._table_by_name(tables, key)
        if direct_table is not None:
            return self._table_result_payload(direct_table)

        table_aliases = self._table_aliases_for_key(key)
        if table_aliases:
            for table_name in table_aliases:
                table = self._table_by_name(tables, table_name)
                if table is None:
                    continue
                if key == "representation_ranking":
                    return self._table_head_result(table, head_rows=1)
                return self._table_result_payload(table)

        if key == "row_count":
            row_count_metric = self._metric_by_name(metrics, "row_count")
            if row_count_metric is not None:
                return self._metric_result_payload(row_count_metric, logical_shape="count")

        if plan.expected_result_shape == "scalar":
            scalar_table = self._scalar_table_for_result_key(key, tables)
            if scalar_table is not None:
                return scalar_table

        return None

    def _select_exploratory_metric_primary_result(self, plan: AnalysisPlan, tables: list[TableArtifact]) -> dict[str, object] | None:
        step_methods = {step.method_id or step.action for step in plan.steps}
        table_priority = [
            "grouped_period_comparison",
            "top_movers",
            "contribution_breakdown",
            "period_comparison",
            "group_breakdown",
            "ranked_breakdown",
            "time_trend",
            "distribution_summary",
            "numeric_summary",
            "anomaly_summary",
            "target_correlation",
        ]
        if "grouped_period_comparison" not in step_methods:
            table_priority.remove("grouped_period_comparison")
        if "top_movers" not in step_methods:
            table_priority.remove("top_movers")
        if "contribution_breakdown" not in step_methods:
            table_priority.remove("contribution_breakdown")
        if "period_comparison" not in step_methods:
            table_priority.remove("period_comparison")
        if "group_breakdown" not in step_methods:
            table_priority.remove("group_breakdown")
        if "ranked_breakdown" not in step_methods:
            table_priority.remove("ranked_breakdown")
        if "time_trend" not in step_methods:
            table_priority.remove("time_trend")
        if "distribution_summary" not in step_methods:
            table_priority.remove("distribution_summary")
        if "numeric_summary" not in step_methods:
            table_priority.remove("numeric_summary")
        if "anomaly_summary" not in step_methods:
            table_priority.remove("anomaly_summary")
        if "target_correlation" not in step_methods:
            table_priority.remove("target_correlation")
        for table_name in table_priority:
            table = self._table_by_name(tables, table_name)
            if table is not None:
                return self._table_result_payload(table)
        return None

    def _table_aliases_for_key(self, key: str) -> list[str]:
        if key == "tabular_record_retrieval":
            return ["tabular_query"]
        if key in {"grouped_metric_table", "grouped_tabular_query"}:
            return ["grouped_tabular_query"]
        if key == "grouped_entity_count":
            return ["grouped_tabular_query", "group_row_counts"]
        if key == "distinct_value_listing":
            return ["distinct_values"]
        if key == "representation_ranking":
            return ["group_row_counts"]
        if key == "row_ranking":
            return ["ranked_rows"]
        if key == "group_ranking":
            return ["ranked_breakdown"]
        if key == "row_existence_check":
            return ["row_existence"]
        if key == "time_value_verification":
            return ["time_value_exists"]
        if key == "null_verification":
            return ["null_check"]
        if key == "threshold_verification":
            return ["threshold_check"]
        if key == "column_presence_check":
            return ["column_presence_check"]
        if key == "column_property_check":
            return ["column_property_check"]
        if key == "time_period_comparison":
            return ["grouped_period_comparison", "period_comparison"]
        if key == "time_bucket_counts":
            return ["time_bucket_counts"]
        if key == "time_bucket_breakdown":
            return ["time_bucket_breakdown"]
        if key == "time_coverage":
            return ["time_coverage"]
        if key == "significance_inference":
            return ["significance_test"]
        if key == "chi_square":
            return ["chi_square_test"]
        if key == "anova":
            return ["anova_test"]
        if key == "mann_whitney":
            return ["mann_whitney_test"]
        return []

    def _column_type_lookup_result(
        self,
        key: str,
        plan: AnalysisPlan,
        tables: list[TableArtifact],
    ) -> dict[str, object] | None:
        result_name = key if key.endswith("_dtype") else "column_dtype"
        if key == "column_type_lookup":
            target = self._targeted_step_parameter(plan, {"column_type_inventory"}, "target")
            if target is not None:
                result_name = f"{target}_dtype"
        return self._table_scalar_result(
            table_name="column_type_inventory",
            value_field="dtype",
            result_name=result_name,
            logical_shape="scalar",
            tables=tables,
        )

    def _scalar_table_for_result_key(
        self,
        key: str,
        tables: list[TableArtifact],
    ) -> dict[str, object] | None:
        scalar_table_fields = {
            "column_count": ("column_count", "column_count", "count"),
            "numeric_column_count": ("numeric_column_count", "numeric_column_count", "count"),
            "categorical_column_count": ("categorical_column_count", "categorical_column_count", "count"),
            "measure_count": ("measure_count", "measure_count", "count"),
            "dimension_count": ("dimension_count", "dimension_count", "count"),
            "time_column_count": ("time_column_count", "time_column_count", "count"),
            "identifier_count": ("identifier_count", "identifier_count", "count"),
            "high_cardinality_count": ("high_cardinality_count", "high_cardinality_count", "count"),
        }
        spec = scalar_table_fields.get(key)
        if spec is None:
            return None
        table_name, value_field, logical_shape = spec
        return self._table_scalar_result(
            table_name=table_name,
            value_field=value_field,
            result_name=key,
            logical_shape=logical_shape,
            tables=tables,
        )

    def _table_scalar_result(
        self,
        table_name: str,
        value_field: str,
        result_name: str,
        logical_shape: str,
        tables: list[TableArtifact],
    ) -> dict[str, object] | None:
        table = self._table_by_name(tables, table_name)
        if table is None or table.dataframe.empty:
            return None
        row = table.dataframe.iloc[0]
        value = row.get(value_field)
        return {
            "name": result_name,
            "description": table.description,
            "physical_shape": "scalar",
            "logical_shape": logical_shape,
            "dtype": self._dtype_from_value(value),
            "schema": [],
            "dimensions": [],
            "row_count": None,
            "labels": [],
            "value": self._json_safe(value),
        }

    def _table_head_result(self, table: TableArtifact, head_rows: int) -> dict[str, object]:
        return self._table_result_payload(
            TableArtifact(
                name=table.name,
                description=table.description,
                dataframe=table.dataframe.head(head_rows).copy(),
                metadata=dict(table.metadata),
            )
        )

    def _output_declaration_map(self, plan: AnalysisPlan) -> dict[str, dict[str, Any]]:
        declarations: dict[str, dict[str, Any]] = {}
        for step in plan.steps:
            for output in step.outputs:
                declarations[output.output_id] = {
                    "output_id": output.output_id,
                    "kind": output.kind,
                    "logical_shape": output.logical_shape,
                    "physical_shape": output.physical_shape,
                    "semantic_kind": output.semantic_kind,
                    "is_primary": output.is_primary,
                    "step_id": step.step_id,
                    "metadata": dict(output.metadata),
                }
        return declarations

    def _declared_output_label(self, declaration: dict[str, Any] | None) -> str | None:
        if declaration is None:
            return None
        metadata = declaration.get("metadata")
        if not isinstance(metadata, dict):
            return None
        label = metadata.get("output_label") or metadata.get("display_name") or metadata.get("terminal_name")
        return str(label) if isinstance(label, str) and label else None

    def _resolve_terminal_output_ref(
        self,
        plan: AnalysisPlan,
        artifact_index: dict[str, ExecutionArtifact],
    ) -> str | None:
        if plan.final_output_ref and plan.final_output_ref in artifact_index:
            return plan.final_output_ref
        leaf_refs = self._leaf_output_refs(plan, artifact_index)
        return leaf_refs[0] if leaf_refs else None

    def _leaf_output_refs(
        self,
        plan: AnalysisPlan,
        artifact_index: dict[str, ExecutionArtifact],
    ) -> list[str]:
        produced_refs = [
            output_ref
            for step in plan.steps
            for output_ref in (*step.output_refs, *(output.output_id for output in step.outputs))
            if output_ref in artifact_index
        ]
        consumed_refs = {
            step_input.ref
            for step in plan.steps
            for step_input in step.inputs
            if step_input.source_type in {"step_output", "artifact"}
        }
        deduped_produced_refs: list[str] = []
        for output_ref in produced_refs:
            if output_ref not in deduped_produced_refs:
                deduped_produced_refs.append(output_ref)
        return [output_ref for output_ref in deduped_produced_refs if output_ref not in consumed_refs]

    def _secondary_terminal_outputs(
        self,
        plan: AnalysisPlan,
        artifact_index: dict[str, ExecutionArtifact],
        output_declarations: dict[str, dict[str, Any]],
    ) -> list[dict[str, object]]:
        secondary_refs = self._secondary_output_refs(plan, artifact_index)
        return [
            self._execution_artifact_payload(artifact_index[output_ref], declaration=output_declarations.get(output_ref))
            for output_ref in secondary_refs
        ]

    def _secondary_output_refs(
        self,
        plan: AnalysisPlan,
        artifact_index: dict[str, ExecutionArtifact],
    ) -> list[str]:
        terminal_ref = self._resolve_terminal_output_ref(plan, artifact_index)
        return [
            output_ref
            for output_ref in self._leaf_output_refs(plan, artifact_index)
            if output_ref != terminal_ref
        ]

    def _terminal_lineage(self, plan: AnalysisPlan, terminal_ref: str | None) -> dict[str, object] | None:
        if terminal_ref is None:
            return None
        step_by_output: dict[str, str] = {}
        step_lookup = {step.step_id: step for step in plan.steps}
        for step in plan.steps:
            for output_ref in (*step.output_refs, *(output.output_id for output in step.outputs)):
                step_by_output.setdefault(output_ref, step.step_id)

        producer_step_id = step_by_output.get(terminal_ref)
        if producer_step_id is None:
            return None

        visited_steps: set[str] = set()
        upstream_output_refs: list[str] = []

        def visit(step_id: str) -> None:
            if step_id in visited_steps:
                return
            visited_steps.add(step_id)
            step = step_lookup[step_id]
            for step_input in step.inputs:
                if step_input.source_type in {"step_output", "artifact"}:
                    upstream_output_refs.append(step_input.ref)
                    parent_step_id = step_by_output.get(step_input.ref)
                    if parent_step_id is not None:
                        visit(parent_step_id)
            for dependency_step_id in step.depends_on:
                if dependency_step_id in step_lookup:
                    visit(dependency_step_id)

        visit(producer_step_id)
        ordered_upstream_steps = [
            step.step_id
            for step in plan.steps
            if step.step_id in visited_steps and step.step_id != producer_step_id
        ]
        path_step_ids = [*ordered_upstream_steps, producer_step_id]

        return {
            "terminal_output_ref": terminal_ref,
            "producer_step_id": producer_step_id,
            "upstream_step_ids": ordered_upstream_steps,
            "upstream_output_refs": upstream_output_refs,
            "path_step_ids": path_step_ids,
        }

    def _graph_execution_summary(
        self,
        plan: AnalysisPlan,
        artifact_index: dict[str, ExecutionArtifact],
        secondary_outputs: list[dict[str, object]],
        terminal_ref: str | None,
    ) -> dict[str, object]:
        leaf_output_refs = self._leaf_output_refs(plan, artifact_index)
        return {
            "step_count": len(plan.steps),
            "artifact_count": len(artifact_index),
            "leaf_output_count": len(leaf_output_refs),
            "leaf_output_refs": leaf_output_refs,
            "terminal_output_ref": terminal_ref,
            "secondary_output_count": len(secondary_outputs),
        }

    def _serialized_artifact_payload(
        self,
        artifact_id: str,
        artifact: ExecutionArtifact,
        plan: AnalysisPlan,
        *,
        declaration: dict[str, Any] | None,
        terminal_ref: str | None,
        secondary_output_refs: list[str],
    ) -> dict[str, object]:
        if self._should_expose_artifact_fully(artifact_id, plan, terminal_ref, secondary_output_refs):
            return self._execution_artifact_payload(artifact, declaration=declaration)
        return self._execution_artifact_summary_payload(artifact, declaration=declaration)

    def _should_expose_artifact_fully(
        self,
        artifact_id: str,
        plan: AnalysisPlan,
        terminal_ref: str | None,
        secondary_output_refs: list[str],
    ) -> bool:
        if artifact_id == terminal_ref:
            return True
        if artifact_id in set(secondary_output_refs):
            return True
        plan_input_ids = {plan_input.input_id for plan_input in plan.inputs}
        if artifact_id in plan_input_ids:
            return False
        return True

    def _execution_artifact_summary_payload(
        self,
        artifact: ExecutionArtifact,
        *,
        declaration: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        payload = self._execution_artifact_payload(artifact, declaration=declaration)
        payload["value"] = self._artifact_value_summary(artifact)
        payload["summarized"] = True
        return payload

    def _artifact_value_summary(self, artifact: ExecutionArtifact) -> dict[str, object] | object:
        value = artifact.value
        if artifact.kind == "scalar":
            return self._json_safe(value)
        if isinstance(value, list):
            row_count = len(value)
            columns: list[str] = []
            if value and isinstance(value[0], dict):
                columns = [str(column) for column in value[0].keys()]
            return {
                "row_count": row_count,
                "column_count": len(columns),
                "columns": columns,
            }
        if isinstance(value, dict):
            return {
                "field_count": len(value),
                "fields": [str(field_name) for field_name in value.keys()],
            }
        return {"kind": artifact.kind}

    def _logical_shape_for_metric(self, metric_name: str) -> str:
        if metric_name == "row_count" or metric_name.endswith("_count"):
            return "count"
        if any(metric_name.endswith(suffix) for suffix in ("_sum", "_mean", "_max", "_min")):
            return "aggregate"
        return "scalar"

    def _plan_result_candidate_keys(self, plan: AnalysisPlan) -> list[str]:
        candidate_keys: list[str] = []
        if isinstance(plan.expected_result_name, str) and plan.expected_result_name:
            candidate_keys.append(plan.expected_result_name)
        for step in plan.steps:
            for value in (*step.output_refs, *self._derived_result_keys_for_step(step)):
                if isinstance(value, str) and value and value not in candidate_keys:
                    candidate_keys.append(value)
        return candidate_keys

    def _derived_result_keys_for_step(self, step: object) -> list[str]:
        method_id = step.method_id or step.action
        parameters = dict(step.parameters)
        keys: list[str] = [method_id, step.action, step.step_id]

        if method_id == "aggregate_value":
            target = parameters.get("target")
            aggregation = parameters.get("aggregation")
            if isinstance(target, str) and isinstance(aggregation, str):
                keys.insert(0, f"{target}_{aggregation}")
        if method_id == "count_rows_by_group":
            keys.insert(0, "group_row_counts")
        if method_id == "distinct_value_count":
            target = parameters.get("target")
            if isinstance(target, str):
                keys.insert(0, f"{target}_distinct_count")
            keys.insert(0, "distinct_value_count")
        if method_id == "column_type_inventory":
            target = parameters.get("target")
            if isinstance(target, str):
                keys.insert(0, f"{target}_dtype")
        if method_id == "dataset_summary":
            keys.insert(0, "dataset_preview")
        statistical_output_aliases = {
            "significance_inference": "significance_test",
            "chi_square": "chi_square_test",
            "anova": "anova_test",
            "mann_whitney": "mann_whitney_test",
        }
        alias = statistical_output_aliases.get(method_id)
        if alias is not None:
            keys.insert(0, alias)
        deduped: list[str] = []
        for value in keys:
            if value not in deduped:
                deduped.append(value)
        return deduped

    def _fallback_primary_result(
        self,
        plan: AnalysisPlan,
        metrics: list[Metric],
        tables: list[TableArtifact],
    ) -> dict[str, object]:
        if plan.expected_result_shape == "scalar" and metrics:
            return self._metric_result_payload(metrics[-1], logical_shape=self._logical_shape_for_metric(metrics[-1].name))
        if plan.expected_result_shape == "verification":
            for table in tables:
                if self._logical_shape_for_table(table.name) == "verification":
                    return self._table_result_payload(table)
        if plan.expected_result_shape == "table":
            for step in plan.steps:
                for candidate in self._derived_result_keys_for_step(step):
                    table = self._table_by_name(tables, candidate)
                    if table is not None:
                        return self._table_result_payload(table)
            if tables:
                return self._table_result_payload(tables[0])
        if tables:
            return self._table_result_payload(tables[0])
        if metrics:
            return self._metric_result_payload(metrics[-1], logical_shape=self._logical_shape_for_metric(metrics[-1].name))
        return {
            "name": "empty_result",
            "description": "No primary result was produced.",
            "physical_shape": "object",
            "logical_shape": "empty",
            "dtype": "null",
            "schema": [],
            "dimensions": [],
            "row_count": 0,
            "labels": [],
            "value": None,
        }

    def _contract_to_dict(self, prompt_contract: object | None) -> dict[str, object] | None:
        if prompt_contract is None:
            return None
        to_dict = getattr(prompt_contract, "to_dict", None)
        if callable(to_dict):
            payload = to_dict()
            return payload if isinstance(payload, dict) else None
        return None

    def _contract_status(self, prompt_contract: object | None) -> object | None:
        if prompt_contract is None:
            return None
        return getattr(prompt_contract, "status", None)

    def _metric_result_payload(self, metric: Metric, logical_shape: str) -> dict[str, object]:
        return {
            "name": metric.name,
            "description": metric.description,
            "physical_shape": "scalar",
            "logical_shape": logical_shape,
            "semantic_kind": infer_semantic_kind(kind="scalar", logical_shape=logical_shape, metadata={"metric_name": metric.name}),
            "dtype": self._dtype_from_value(metric.value),
            "schema": [],
            "dimensions": [],
            "row_count": None,
            "labels": [],
            "value": self._json_safe(metric.value),
        }

    def _execution_artifact_payload(
        self,
        artifact: ExecutionArtifact,
        *,
        declaration: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        display_name = self._declared_output_label(declaration) or artifact.artifact_id
        payload = {
            "name": artifact.artifact_id,
            "display_name": display_name,
            "description": None,
            "physical_shape": artifact.physical_shape or "object",
            "logical_shape": artifact.logical_shape or artifact.kind,
            "semantic_kind": artifact.semantic_kind or infer_semantic_kind(
                kind=artifact.kind,
                logical_shape=artifact.logical_shape,
                metadata=dict(artifact.metadata),
                value=artifact.value,
            ),
            "dtype": artifact.kind,
            "schema": [],
            "dimensions": [],
            "row_count": None,
            "labels": [],
            "producer_step_id": artifact.producer_step_id,
            "metadata": self._json_safe(dict(artifact.metadata)),
            "value": self._json_safe(artifact.value),
        }
        if declaration is not None:
            payload["declared_output"] = self._json_safe(dict(declaration))
        return payload

    def _table_entry(self, table: TableArtifact) -> dict[str, object]:
        return {
            "name": table.name,
            "description": table.description,
            "metadata": dict(table.metadata),
            "result": self._table_result_payload(table),
        }

    def _table_result_payload(self, table: TableArtifact) -> dict[str, object]:
        dataframe = table.dataframe
        physical_shape, value, dimensions, labels = self._table_value_shape(dataframe)
        return {
            "name": table.name,
            "description": table.description,
            "physical_shape": physical_shape,
            "logical_shape": self._logical_shape_for_table(table.name),
            "semantic_kind": infer_semantic_kind(
                kind="frame",
                logical_shape=self._logical_shape_for_table(table.name),
                metadata={"table_name": table.name, **dict(table.metadata)},
                value=dataframe,
            ),
            "dtype": self._dtype_for_table_result(dataframe, physical_shape),
            "schema": self._schema_for_dataframe(dataframe),
            "dimensions": dimensions,
            "row_count": int(len(dataframe)),
            "labels": labels,
            "pagination": self._json_safe(table.metadata.get("pagination")) if table.metadata.get("pagination") else None,
            "metadata": self._json_safe(dict(table.metadata)) if table.metadata else {},
            "value": value,
        }

    def _table_value_shape(self, dataframe: pd.DataFrame) -> tuple[str, object, list[int], list[str]]:
        if dataframe.empty:
            return "recordset", [], [0, int(len(dataframe.columns))], list(dataframe.columns)
        if len(dataframe) == 1 and len(dataframe.columns) == 1:
            scalar_value = self._json_safe(dataframe.iloc[0, 0])
            return "scalar", scalar_value, [], list(dataframe.columns)
        if len(dataframe.columns) == 1:
            values = [self._json_safe(value) for value in dataframe.iloc[:, 0].tolist()]
            return "vector", values, [len(values)], list(dataframe.columns)
        if len(dataframe) == 1:
            value = {column: self._json_safe(dataframe.iloc[0][column]) for column in dataframe.columns}
            return "object", value, [len(dataframe.columns)], list(dataframe.columns)
        records = [
            {column: self._json_safe(value) for column, value in row.items()}
            for row in dataframe.to_dict(orient="records")
        ]
        return "recordset", records, [int(len(dataframe)), int(len(dataframe.columns))], list(dataframe.columns)

    def _logical_shape_for_table(self, table_name: str) -> str:
        mapping = {
            "dataset_preview": "table",
            "distinct_values": "table",
            "tabular_query": "recordset",
            "grouped_tabular_query": "table",
            "time_value_exists": "verification",
            "row_existence": "verification",
            "column_presence_check": "verification",
            "null_check": "verification",
            "threshold_check": "verification",
            "column_property_check": "verification",
            "group_row_counts": "table",
            "time_bucket_counts": "timeseries",
            "time_bucket_breakdown": "timeseries",
            "group_breakdown": "table",
            "ranked_breakdown": "table",
            "ranked_rows": "table",
            "contribution_breakdown": "table",
            "grouped_period_comparison": "table",
            "top_movers": "table",
            "numeric_summary": "table",
            "missingness_summary": "table",
            "anomaly_summary": "table",
            "group_mean_comparison": "table",
            "time_series_diagnostics": "table",
            "column_inventory": "table",
            "column_count": "count",
            "column_type_inventory": "table",
            "numeric_column_count": "count",
            "numeric_column_inventory": "table",
            "categorical_column_count": "count",
            "categorical_column_inventory": "table",
            "measure_count": "count",
            "measure_inventory": "table",
            "dimension_count": "count",
            "dimension_inventory": "table",
            "time_column_count": "count",
            "time_column_inventory": "table",
            "missing_value_inventory": "table",
            "identifier_count": "count",
            "identifier_inventory": "table",
            "high_cardinality_count": "count",
            "high_cardinality_inventory": "table",
            "distinct_value_count": "count",
            "time_trend": "timeseries",
            "period_comparison": "timeseries",
            "time_coverage": "timeseries",
            "correlation_matrix": "correlation_matrix",
            "target_correlation": "correlation_matrix",
            "distribution_summary": "distribution",
            "t_test": "statistical_test",
            "chi_square_test": "statistical_test",
            "anova_test": "statistical_test",
            "mann_whitney_test": "statistical_test",
            "confidence_interval": "statistical_test",
            "regression_significance": "statistical_test",
            "significance_test": "statistical_test",
            "power_analysis": "statistical_test",
            "sample_size_estimate": "statistical_test",
        }
        return mapping.get(table_name, "table")

    def _dtype_for_table_result(self, dataframe: pd.DataFrame, physical_shape: str) -> str:
        if physical_shape == "scalar":
            return self._dtype_from_value(dataframe.iloc[0, 0])
        if physical_shape == "vector":
            return self._dtype_from_series(dataframe.iloc[:, 0])
        if physical_shape == "object":
            return "object"
        return "record"

    def _schema_for_dataframe(self, dataframe: pd.DataFrame) -> list[dict[str, object]]:
        return [
            {
                "name": column_name,
                "dtype": self._dtype_from_series(dataframe[column_name]),
            }
            for column_name in dataframe.columns
        ]

    def _dtype_from_series(self, series: pd.Series) -> str:
        if pd.api.types.is_bool_dtype(series):
            return "boolean"
        if pd.api.types.is_integer_dtype(series):
            return "integer"
        if pd.api.types.is_float_dtype(series):
            return "float"
        if pd.api.types.is_datetime64_any_dtype(series):
            return "datetime"
        return "string"

    def _dtype_from_value(self, value: Any) -> str:
        if hasattr(value, "item"):
            try:
                return self._dtype_from_value(value.item())
            except Exception:
                pass
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int) and not isinstance(value, bool):
            return "integer"
        if isinstance(value, float):
            if not math.isfinite(value):
                return "null"
            return "float"
        if value is None:
            return "null"
        return "string"

    def _json_safe(self, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._json_safe(item) for item in value]
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        if hasattr(value, "item"):
            try:
                return self._json_safe(value.item())
            except Exception:
                pass
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass
        return str(value)

    def _metric_by_name(self, metrics: list[Metric], name: str) -> Metric | None:
        return next((metric for metric in reversed(metrics) if metric.name == name), None)

    def _table_by_name(self, tables: list[TableArtifact], name: str) -> TableArtifact | None:
        return next((table for table in tables if table.name == name), None)

    def _targeted_step_parameter(
        self,
        plan: AnalysisPlan,
        method_ids: set[str],
        parameter_name: str,
    ) -> str | None:
        for step in plan.steps:
            if (step.method_id or step.action) not in method_ids:
                continue
            value = step.parameters.get(parameter_name)
            if isinstance(value, str) and value:
                return value
        return None


ResultBuilder = ResultCanonicalizer

