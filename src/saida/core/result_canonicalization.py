"""Canonicalize backend outputs into top-level result objects."""

from __future__ import annotations

from dataclasses import asdict
import math
from typing import Any
from typing import TYPE_CHECKING

import pandas as pd

from saida.core.contracts import (
    AnalysisPlan,
    AnalysisRequest,
    AnalysisResult,
    DatasetProfile,
    ExecutionTraceEvent,
    ForecastAnalysisResult,
    ForecastResult,
    Metric,
    ModelTrainingResult,
    TableArtifact,
    TrainResult,
)
from saida.core.prompt_family_catalog import (
    PromptFamilyResultSpec,
    derive_prompt_family,
    get_prompt_family_catalog,
)

if TYPE_CHECKING:
    from saida.core.prompt_capability_contract import PromptCapabilityContract


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
        request: AnalysisRequest,
        profile: DatasetProfile,
        trace: list[ExecutionTraceEvent],
        capability_contract: PromptCapabilityContract | None = None,
    ) -> AnalysisResult:
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
            capability_contract,
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
            capability_contract,
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
            artifacts=artifacts,
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
        request: AnalysisRequest,
        profile: DatasetProfile,
        trace: list[ExecutionTraceEvent],
        deterministic_summary: str | None,
        llm_summary: str | None,
        summary_source: str,
        capability_contract: PromptCapabilityContract | None,
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
            "prompt_capability_contract": capability_contract.to_dict() if capability_contract is not None else None,
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
        request: AnalysisRequest,
        profile: DatasetProfile,
        trace: list[ExecutionTraceEvent],
        deterministic_summary: str | None,
        llm_summary: str | None,
        summary_source: str,
        capability_contract: PromptCapabilityContract | None,
    ) -> dict[str, object]:
        operations = [
            {
                "step_id": step.step_id,
                "tool_family": step.tool_family,
                "action": step.action,
                "description": step.description,
                "parameters": dict(step.parameters),
            }
            for step in plan.steps
        ]
        metric_lookup = {metric.name: metric.value for metric in metrics}
        primary_result = self._select_primary_result(request, metrics, tables)
        table_entries = [self._table_entry(table) for table in tables]

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
                "task_type": plan.task_type,
                "target": request.target,
                "aggregation": request.aggregation,
                "group_by": list(request.group_by or []),
                "filters": dict(request.filters or {}),
                "time_reference": dict(request.time_reference or {}),
                "horizon": request.horizon,
                "options": dict(request.options),
                "capability_contract": capability_contract.to_dict() if capability_contract is not None else None,
            },
            "execution": {
                "status": self._resolve_status(plan),
                "tool_families": sorted({step.tool_family for step in plan.steps}),
                "rationale": plan.rationale,
                "step_count": len(plan.steps),
                "steps": operations,
            },
            "result": primary_result,
            "tables": table_entries,
            "reasoning": {
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
                "capability_contract_status": capability_contract.status if capability_contract is not None else None,
                "plan_warnings": list(plan.warnings),
                "warning_count": len(warnings),
                "metrics": [asdict(metric) for metric in metrics],
                "metric_lookup": metric_lookup,
                "table_names": [table.name for table in tables],
            },
            }
        )

    def _resolve_status(self, plan: AnalysisPlan) -> str:
        if plan.task_type == "clarification":
            return "clarify"
        if plan.task_type == "unavailable":
            return "refuse"
        return "ok"

    def _select_primary_result(
        self,
        request: AnalysisRequest,
        metrics: list[Metric],
        tables: list[TableArtifact],
    ) -> dict[str, object]:
        prompt_family = request.prompt_family or derive_prompt_family(request)
        family_spec = get_prompt_family_catalog().get(prompt_family)
        if family_spec is not None and family_spec.primary_result is not None:
            primary_result = self._compile_family_primary_result(
                family_spec.primary_result,
                request,
                metrics,
                tables,
            )
            if primary_result is not None:
                issues = family_spec.result_invariant_issues(primary_result)
                if issues:
                    raise ValueError(
                        f"Prompt family {family_spec.family_id!r} produced an invalid primary result: {' '.join(issues)}"
                    )
                return primary_result

        if prompt_family == "exploratory_metric_overview":
            primary_result = self._select_exploratory_metric_primary_result(request, tables)
            if primary_result is not None:
                return primary_result

        if prompt_family == "metric_aggregate" or (request.target and request.aggregation and not request.group_by):
            metric_name = f"{request.target}_{request.aggregation}"
            aggregate_metric = self._metric_by_name(metrics, metric_name)
            if aggregate_metric is not None:
                logical_shape = {
                    "sum": "aggregate",
                    "mean": "aggregate",
                    "max": "aggregate",
                    "min": "aggregate",
                    "count": "count",
                }.get(request.aggregation, "scalar")
                return self._metric_result_payload(aggregate_metric, logical_shape=logical_shape)

        table_priority = [
            "grouped_tabular_query",
            "tabular_query",
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
            "time_value_exists",
            "row_existence",
            "column_presence_check",
            "null_check",
            "threshold_check",
            "column_property_check",
            "ranked_rows",
            "ranked_breakdown",
            "group_row_counts",
            "time_bucket_counts",
            "time_bucket_breakdown",
            "distinct_values",
            "time_coverage",
            "significance_test",
            "t_test",
            "chi_square_test",
            "anova_test",
            "mann_whitney_test",
            "confidence_interval",
            "regression_significance",
            "power_analysis",
            "sample_size_estimate",
            "group_breakdown",
            "period_comparison",
            "time_trend",
            "grouped_period_comparison",
            "top_movers",
            "contribution_breakdown",
            "target_correlation",
            "correlation_matrix",
            "distribution_summary",
            "numeric_summary",
            "missingness_summary",
            "anomaly_summary",
            "time_series_diagnostics",
            "group_mean_comparison",
            "dataset_preview",
        ]
        for table_name in table_priority:
            table = self._table_by_name(tables, table_name)
            if table is not None:
                return self._table_result_payload(table)

        if metrics:
            return self._metric_result_payload(metrics[-1], logical_shape="scalar")
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

    def _select_exploratory_metric_primary_result(
        self,
        request: AnalysisRequest,
        tables: list[TableArtifact],
    ) -> dict[str, object] | None:
        table_priority: list[str]
        if request.group_by and request.time_reference:
            table_priority = [
                "grouped_period_comparison",
                "top_movers",
                "contribution_breakdown",
                "group_breakdown",
                "period_comparison",
                "time_trend",
                "ranked_breakdown",
                "distribution_summary",
                "numeric_summary",
            ]
        elif request.group_by:
            table_priority = [
                "group_breakdown",
                "ranked_breakdown",
                "time_trend",
                "distribution_summary",
                "numeric_summary",
            ]
        elif request.time_reference:
            table_priority = [
                "period_comparison",
                "time_trend",
                "contribution_breakdown",
                "distribution_summary",
                "numeric_summary",
            ]
        else:
            table_priority = [
                "time_trend",
                "distribution_summary",
                "numeric_summary",
                "anomaly_summary",
                "target_correlation",
            ]
        for table_name in table_priority:
            table = self._table_by_name(tables, table_name)
            if table is not None:
                return self._table_result_payload(table)
        return None

    def _compile_family_primary_result(
        self,
        result_spec: PromptFamilyResultSpec,
        request: AnalysisRequest,
        metrics: list[Metric],
        tables: list[TableArtifact],
    ) -> dict[str, object] | None:
        if result_spec.source == "metric":
            metric_name = self._render_result_template(result_spec.metric_name_template, request)
            if metric_name is None:
                return None
            metric = self._metric_by_name(metrics, metric_name)
            if metric is None:
                return None
            return self._metric_result_payload(metric, logical_shape=result_spec.logical_shape or "scalar")

        if result_spec.source == "table":
            table = self._table_by_name(tables, result_spec.table_name)
            if table is None:
                return None
            return self._table_result_payload(table)

        if result_spec.source == "table_head":
            table = self._table_by_name(tables, result_spec.table_name)
            if table is None or table.dataframe.empty:
                return None
            return self._table_result_payload(
                TableArtifact(
                    name=table.name,
                    description=table.description,
                    dataframe=table.dataframe.head(result_spec.head_rows).copy(),
                    metadata=dict(table.metadata),
                )
            )

        if result_spec.source == "table_scalar_field":
            table = self._table_by_name(tables, result_spec.table_name)
            if table is None or table.dataframe.empty or result_spec.value_field is None:
                return None
            row = table.dataframe.iloc[0]
            value = row.get(result_spec.value_field)
            return {
                "name": self._render_result_template(result_spec.result_name_template, request) or "scalar_result",
                "description": self._render_result_template(result_spec.description_template, request),
                "physical_shape": "scalar",
                "logical_shape": result_spec.logical_shape or "scalar",
                "dtype": self._dtype_from_value(value),
                "schema": [],
                "dimensions": [],
                "row_count": None,
                "labels": [],
                "value": self._json_safe(value),
            }

        return None

    def _render_result_template(self, template: str | None, request: AnalysisRequest) -> str | None:
        if template is None:
            return None
        values = {
            "target": request.target or "",
            "aggregation": request.aggregation or "",
            "prompt_family": request.prompt_family or "",
        }
        return template.format(**values)

    def _metric_result_payload(self, metric: Metric, logical_shape: str) -> dict[str, object]:
        return {
            "name": metric.name,
            "description": metric.description,
            "physical_shape": "scalar",
            "logical_shape": logical_shape,
            "dtype": self._dtype_from_value(metric.value),
            "schema": [],
            "dimensions": [],
            "row_count": None,
            "labels": [],
            "value": self._json_safe(metric.value),
        }

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
            "column_type_inventory": "table",
            "numeric_column_inventory": "table",
            "categorical_column_inventory": "table",
            "measure_inventory": "table",
            "dimension_inventory": "table",
            "time_column_inventory": "table",
            "missing_value_inventory": "table",
            "identifier_inventory": "table",
            "high_cardinality_inventory": "table",
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


ResultBuilder = ResultCanonicalizer
