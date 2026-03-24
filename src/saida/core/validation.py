"""Validation helpers for datasets and plans."""

from __future__ import annotations

import pandas as pd

from saida.core.analytics_registry import get_analytics_registry
from saida.exceptions import PlanningError, ValidationError
from saida.core.contracts import AnalysisPlan, Dataset


class PlanValidator:
    """Validate datasets and canonical plans before execution."""

    def validate_dataset(self, dataset: Dataset) -> None:
        """Validate the incoming dataset payload."""
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

    def validate_plan(self, plan: AnalysisPlan) -> None:
        """Validate that the plan contains executable and coherent steps."""
        if not plan.steps:
            raise PlanningError("Analysis plan contains no executable steps.")

        analytics_registry = get_analytics_registry()
        seen_step_ids: set[str] = set()
        duplicate_step_ids: list[str] = []
        for step in plan.steps:
            if not step.step_id.strip():
                raise PlanningError("Analysis plan contains a step with an empty step_id.")
            if step.step_id in seen_step_ids and step.step_id not in duplicate_step_ids:
                duplicate_step_ids.append(step.step_id)
            seen_step_ids.add(step.step_id)
            if not step.tool_family.strip():
                raise PlanningError(f"Plan step {step.step_id!r} is missing a tool_family.")
            if not step.action.strip():
                raise PlanningError(f"Plan step {step.step_id!r} is missing an action.")
            if not isinstance(step.parameters, dict):
                raise PlanningError(f"Plan step {step.step_id!r} parameters must be a dictionary.")
            if step.method_id is not None and not step.method_id.strip():
                raise PlanningError(f"Plan step {step.step_id!r} has an empty method_id.")
            method_id = step.method_id or step.action
            method_spec = analytics_registry.get_method(method_id)
            if method_spec is None:
                raise PlanningError(f"Plan step {step.step_id!r} references unknown analytics method {method_id!r}.")
            if step.family is not None and step.family != method_spec.family_id:
                raise PlanningError(
                    f"Plan step {step.step_id!r} declares family {step.family!r}, expected {method_spec.family_id!r}."
                )
            if len(step.output_refs) != len(set(step.output_refs)):
                raise PlanningError(f"Plan step {step.step_id!r} contains duplicate output_refs.")
            if step.step_id in step.depends_on:
                raise PlanningError(f"Plan step {step.step_id!r} cannot depend on itself.")

        if duplicate_step_ids:
            joined = ", ".join(sorted(duplicate_step_ids))
            raise PlanningError(f"Analysis plan contains duplicate step_ids: {joined}")

        prior_step_ids: set[str] = set()
        for step in plan.steps:
            missing_dependencies = [dependency for dependency in step.depends_on if dependency not in seen_step_ids]
            if missing_dependencies:
                joined = ", ".join(missing_dependencies)
                raise PlanningError(f"Plan step {step.step_id!r} depends on unknown steps: {joined}")
            out_of_order_dependencies = [dependency for dependency in step.depends_on if dependency not in prior_step_ids]
            if out_of_order_dependencies:
                joined = ", ".join(out_of_order_dependencies)
                raise PlanningError(
                    f"Plan step {step.step_id!r} depends on steps that appear later in the ordered plan: {joined}"
                )
            prior_step_ids.add(step.step_id)

        seen_input_ids: set[str] = set()
        duplicate_input_ids: list[str] = []
        for plan_input in plan.inputs:
            if not plan_input.input_id.strip():
                raise PlanningError("Analysis plan contains an input with an empty input_id.")
            if not plan_input.kind.strip():
                raise PlanningError(f"Analysis plan input {plan_input.input_id!r} is missing a kind.")
            if not plan_input.ref.strip():
                raise PlanningError(f"Analysis plan input {plan_input.input_id!r} is missing a ref.")
            if plan_input.input_id in seen_input_ids and plan_input.input_id not in duplicate_input_ids:
                duplicate_input_ids.append(plan_input.input_id)
            seen_input_ids.add(plan_input.input_id)

        if duplicate_input_ids:
            joined = ", ".join(sorted(duplicate_input_ids))
            raise PlanningError(f"Analysis plan contains duplicate input ids: {joined}")

        if len(plan.dataset_refs) != len(set(plan.dataset_refs)):
            raise PlanningError("Analysis plan contains duplicate dataset_refs.")
