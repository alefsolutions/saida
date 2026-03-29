from __future__ import annotations

import json
from typing import Any

import pandas as pd

from saida.core.analytics_registry import get_analytics_registry
from saida.core.contracts import AnalysisPlan, Dataset, PlanStep
from saida.core.contracts import PlanInput, StepInputRef, StepOutputSpec


def build_sales_dataset() -> Dataset:
    return Dataset(
        name="sales",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "posted_at": [
                    "2025-10-01",
                    "2025-11-01",
                    "2025-12-01",
                    "2026-01-01",
                    "2026-02-01",
                    "2026-03-01",
                ],
                "revenue": [100.0, 120.0, 90.0, 80.0, 110.0, 130.0],
                "region": ["West", "East", "West", "East", "West", "East"],
                "segment": ["SMB", "Enterprise", "SMB", "Enterprise", "SMB", "Enterprise"],
            }
        ),
    )


def build_support_dataset() -> Dataset:
    return Dataset(
        name="support",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "ticket_id": ["T1", "T2", "T3", "T4", "T5", "T6", "T7"],
                "created_at": [
                    "2026-01-01",
                    "2026-01-12",
                    "2026-02-03",
                    "2026-02-14",
                    "2026-03-05",
                    "2026-04-16",
                    "2026-05-07",
                ],
                "resolution_hours": [2.1, 5.4, 6.8, 4.2, 7.1, 8.0, 3.5],
                "csat_score": [4.7, None, 3.6, 4.1, 3.5, 3.2, 4.4],
                "team": ["Support", "Support", "Platform", "Platform", "Support", "Platform", "Support"],
                "priority": ["Low", "Medium", "High", "Low", "High", "Medium", "Low"],
                "reopened_flag": ["no", "no", "yes", "yes", "no", "yes", "no"],
            }
        ),
    )


def build_recurring_time_dataset() -> Dataset:
    return Dataset(
        name="tickets",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "ticket_id": [f"T{index}" for index in range(1, 17)],
                "created_at": [
                    "2026-01-01",
                    "2026-01-03",
                    "2026-01-05",
                    "2026-01-15",
                    "2026-01-30",
                    "2026-01-31",
                    "2026-02-01",
                    "2026-02-02",
                    "2026-02-15",
                    "2026-02-27",
                    "2026-02-28",
                    "2026-03-01",
                    "2026-03-02",
                    "2026-03-15",
                    "2026-03-27",
                    "2026-03-31",
                ],
                "priority": [
                    "Low",
                    "Low",
                    "Medium",
                    "High",
                    "Medium",
                    "Low",
                    "Low",
                    "Medium",
                    "High",
                    "Medium",
                    "Low",
                    "Low",
                    "Medium",
                    "High",
                    "Medium",
                    "Low",
                ],
            }
        ),
    )


def build_support_schema_dataset() -> Dataset:
    return Dataset(
        name="support",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "created_at": ["2026-01-01", "2026-01-02"],
                "team": ["Support", "Platform"],
                "priority": ["High", "Low"],
                "channel": ["Email", "Phone"],
                "resolution_hours": [4.2, 6.1],
                "csat_score": [4.8, 4.1],
                "reopened_flag": ["no", "yes"],
            }
        ),
    )


def build_statistical_dataset() -> Dataset:
    return Dataset(
        name="statistical_sales",
        source_type="pandas",
        data=pd.DataFrame(
            {
                "team": ["Alpha"] * 6 + ["Beta"] * 6 + ["Gamma"] * 6,
                "segment": ["Retail", "Retail", "Wholesale", "Wholesale", "Retail", "Wholesale"] * 3,
                "region": ["North", "North", "South", "South", "North", "South"] * 3,
                "revenue": [100, 104, 98, 102, 101, 99, 135, 138, 132, 140, 136, 134, 160, 158, 162, 159, 161, 157],
                "cost": [70, 72, 69, 71, 70, 68, 88, 90, 87, 91, 89, 88, 95, 94, 96, 95, 97, 93],
                "units": [10, 11, 10, 12, 11, 10, 14, 15, 14, 15, 16, 14, 18, 17, 19, 18, 20, 17],
            }
        ),
    )


def build_basic_row_count_plan(dataset_name: str = "support") -> AnalysisPlan:
    return build_explicit_single_step_plan(
        dataset_name=dataset_name,
        task_type="descriptive",
        rationale="Count rows deterministically for core execution tests.",
        step_id="row_count",
        tool_family="duckdb",
        method_id="row_count",
        family="aggregation_grouping",
        parameters={},
        description="Count all rows.",
        expected_result_name="row_count",
        expected_result_shape="scalar",
    )


def build_explicit_single_step_plan(
    *,
    dataset_name: str,
    task_type: str,
    rationale: str,
    step_id: str,
    tool_family: str,
    method_id: str,
    family: str,
    parameters: dict[str, Any],
    description: str,
    expected_result_name: str,
    expected_result_shape: str,
) -> AnalysisPlan:
    method_spec = get_analytics_registry().get_method(method_id)
    logical_shape = method_spec.output_shapes[0] if method_spec is not None and method_spec.output_shapes else expected_result_shape
    default_output_kind = method_spec.default_output_kind if method_spec is not None else None
    physical_shape = "scalar" if logical_shape in {"scalar", "count", "aggregate"} else "recordset"
    output_kind = default_output_kind or ("scalar" if physical_shape == "scalar" else "frame")

    return AnalysisPlan(
        task_type=task_type,
        rationale=rationale,
        dataset_refs=[dataset_name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset_name)],
        expected_result_name=expected_result_name,
        expected_result_shape=expected_result_shape,
        final_output_ref=expected_result_name,
        steps=[
            PlanStep(
                step_id=step_id,
                tool_family=tool_family,
                action=method_id,
                method_id=method_id,
                family=family,
                parameters=dict(parameters),
                description=description,
                inputs=[
                    StepInputRef(
                        input_id="dataset_input",
                        source_type="plan_input",
                        ref="primary_dataset",
                        expected_kind="dataset",
                    )
                ],
                output_refs=[expected_result_name],
                outputs=[
                    StepOutputSpec(
                        output_id=expected_result_name,
                        kind=output_kind,
                        logical_shape=logical_shape,
                        physical_shape=physical_shape,
                    )
                ],
                expected_output={
                    "output_id": expected_result_name,
                    "logical_shape": logical_shape,
                    "physical_shape": physical_shape,
                },
            )
        ],
    )


def json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))
