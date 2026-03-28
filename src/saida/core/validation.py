"""Validation helpers for datasets and plans."""

from __future__ import annotations

from numbers import Real

import pandas as pd

from saida.core.analytics_registry import AnalyticsMethodSpec, get_analytics_registry
from saida.exceptions import PlanningError, ValidationError
from saida.core.contracts import AnalysisPlan, Dataset, DatasetProfile


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

    def validate_plan(
        self,
        plan: AnalysisPlan,
        dataset: Dataset | None = None,
        profile: DatasetProfile | None = None,
        router: object | None = None,
    ) -> None:
        """Validate that the plan contains executable and coherent steps."""
        self._validate_plan(plan, dataset=dataset, profile=profile, router=router)

    def _validate_plan(
        self,
        plan: AnalysisPlan,
        dataset: Dataset | None = None,
        profile: DatasetProfile | None = None,
        router: object | None = None,
    ) -> None:
        """Validate that the plan contains executable and coherent steps."""
        if not plan.steps:
            raise PlanningError("Analysis plan contains no executable steps.")

        analytics_registry = get_analytics_registry()
        resolved_methods: list[tuple[object, AnalyticsMethodSpec, str]] = []
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
            resolved_methods.append((step, method_spec, method_id))

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
        if dataset is not None:
            if plan.dataset_refs and dataset.name not in set(plan.dataset_refs):
                raise PlanningError(
                    f"Analysis plan dataset_refs {plan.dataset_refs!r} do not include the provided dataset {dataset.name!r}."
                )
            dataset_inputs = [plan_input.ref for plan_input in plan.inputs if plan_input.kind == "dataset"]
            if dataset_inputs and dataset.name not in set(dataset_inputs):
                raise PlanningError(
                    f"Analysis plan inputs {dataset_inputs!r} do not reference the provided dataset {dataset.name!r}."
                )

        for step, method_spec, method_id in resolved_methods:
            self._validate_required_inputs(step.step_id, step.parameters, method_spec, dataset)
            self._validate_supported_parameters(step.step_id, step.parameters, method_spec)
            self._validate_parameter_shapes(step.step_id, step.parameters)
            self._validate_expected_output(step.step_id, step.expected_output, method_spec)
            if profile is not None:
                self._validate_parameter_fields(step.step_id, step.parameters, method_spec, profile)
            if router is not None:
                self._validate_backend_support(step.step_id, step.tool_family, method_id, router)

        self._validate_plan_result_expectation(plan, analytics_registry)

    def _validate_required_inputs(
        self,
        step_id: str,
        parameters: dict[str, object],
        method_spec: AnalyticsMethodSpec,
        dataset: Dataset | None,
    ) -> None:
        for required_input in method_spec.required_inputs:
            if required_input == "dataset" and dataset is None:
                raise PlanningError(f"Plan step {step_id!r} requires a dataset input.")
            if required_input == "target" and not isinstance(parameters.get("target"), str):
                raise PlanningError(f"Plan step {step_id!r} requires a target parameter.")
            if required_input == "aggregation" and not isinstance(parameters.get("aggregation"), str):
                raise PlanningError(f"Plan step {step_id!r} requires an aggregation parameter.")
            if required_input == "group_by" and not parameters.get("group_by"):
                raise PlanningError(f"Plan step {step_id!r} requires at least one group_by column.")
            if required_input == "time_column" and not isinstance(parameters.get("time_column"), str):
                raise PlanningError(f"Plan step {step_id!r} requires a time_column parameter.")
            if required_input == "time_reference" and not isinstance(parameters.get("time_reference"), dict):
                raise PlanningError(f"Plan step {step_id!r} requires a time_reference parameter.")

    def _validate_supported_parameters(
        self,
        step_id: str,
        parameters: dict[str, object],
        method_spec: AnalyticsMethodSpec,
    ) -> None:
        supported_parameters = {
            value
            for value in (*method_spec.required_inputs, *method_spec.allowed_configs)
            if value != "dataset"
        }
        unsupported_parameters = sorted(parameter for parameter in parameters if parameter not in supported_parameters)
        if unsupported_parameters:
            joined = ", ".join(unsupported_parameters)
            raise PlanningError(
                f"Plan step {step_id!r} declares unsupported parameters for method {method_spec.method_id!r}: {joined}."
            )

    def _validate_parameter_shapes(
        self,
        step_id: str,
        parameters: dict[str, object],
    ) -> None:
        self._validate_string_parameter(step_id, parameters, "target")
        self._validate_string_parameter(step_id, parameters, "aggregation")
        self._validate_string_parameter(step_id, parameters, "time_column")
        self._validate_string_parameter(step_id, parameters, "bucket")
        self._validate_string_parameter(step_id, parameters, "mode")
        self._validate_string_parameter(step_id, parameters, "sort_by")
        self._validate_string_parameter(step_id, parameters, "sort_direction")
        self._validate_string_parameter(step_id, parameters, "expected_property")
        self._validate_string_parameter(step_id, parameters, "requested_column")
        self._validate_string_parameter(step_id, parameters, "null_expectation")
        self._validate_string_parameter(step_id, parameters, "threshold_operator")
        self._validate_string_parameter(step_id, parameters, "group_column")

        self._validate_dict_parameter(step_id, parameters, "filters")
        self._validate_dict_parameter(step_id, parameters, "time_reference")

        self._validate_string_list_parameter(step_id, parameters, "group_by")
        self._validate_string_list_parameter(step_id, parameters, "selected_columns")
        self._validate_string_list_parameter(step_id, parameters, "feature_columns")
        self._validate_string_list_parameter(step_id, parameters, "comparison_columns")

        self._validate_integer_parameter(step_id, parameters, "limit", minimum=1)
        self._validate_integer_parameter(step_id, parameters, "page", minimum=1)
        self._validate_integer_parameter(step_id, parameters, "page_size", minimum=1)
        self._validate_integer_parameter(step_id, parameters, "horizon", minimum=1)
        self._validate_integer_parameter(step_id, parameters, "expected_year", minimum=1)

        self._validate_numeric_parameter(step_id, parameters, "alpha")
        self._validate_numeric_parameter(step_id, parameters, "confidence_level")
        self._validate_numeric_parameter(step_id, parameters, "desired_power")
        self._validate_numeric_parameter(step_id, parameters, "threshold_value")
        self._validate_numeric_parameter(step_id, parameters, "lower_bound")
        self._validate_numeric_parameter(step_id, parameters, "upper_bound")

    def _validate_string_parameter(
        self,
        step_id: str,
        parameters: dict[str, object],
        name: str,
    ) -> None:
        value = parameters.get(name)
        if value is None:
            return
        if not isinstance(value, str) or not value.strip():
            raise PlanningError(f"Plan step {step_id!r} parameter {name!r} must be a non-empty string.")

    def _validate_dict_parameter(
        self,
        step_id: str,
        parameters: dict[str, object],
        name: str,
    ) -> None:
        value = parameters.get(name)
        if value is None:
            return
        if not isinstance(value, dict):
            raise PlanningError(f"Plan step {step_id!r} parameter {name!r} must be a dictionary.")

    def _validate_string_list_parameter(
        self,
        step_id: str,
        parameters: dict[str, object],
        name: str,
    ) -> None:
        value = parameters.get(name)
        if value is None:
            return
        if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
            raise PlanningError(f"Plan step {step_id!r} parameter {name!r} must be a list of non-empty strings.")

    def _validate_integer_parameter(
        self,
        step_id: str,
        parameters: dict[str, object],
        name: str,
        *,
        minimum: int | None = None,
    ) -> None:
        value = parameters.get(name)
        if value is None:
            return
        if not isinstance(value, int) or isinstance(value, bool):
            raise PlanningError(f"Plan step {step_id!r} parameter {name!r} must be an integer.")
        if minimum is not None and value < minimum:
            raise PlanningError(f"Plan step {step_id!r} parameter {name!r} must be >= {minimum}.")

    def _validate_numeric_parameter(
        self,
        step_id: str,
        parameters: dict[str, object],
        name: str,
    ) -> None:
        value = parameters.get(name)
        if value is None:
            return
        if not isinstance(value, Real) or isinstance(value, bool):
            raise PlanningError(f"Plan step {step_id!r} parameter {name!r} must be numeric.")

    def _validate_expected_output(
        self,
        step_id: str,
        expected_output: dict[str, object] | None,
        method_spec: AnalyticsMethodSpec,
    ) -> None:
        if expected_output is None:
            return
        logical_shape = expected_output.get("logical_shape")
        if logical_shape is None or not method_spec.output_shapes:
            return
        if logical_shape not in set(method_spec.output_shapes):
            raise PlanningError(
                f"Plan step {step_id!r} expects logical_shape {logical_shape!r}, "
                f"but method {method_spec.method_id!r} supports {list(method_spec.output_shapes)!r}."
            )

    def _validate_parameter_fields(
        self,
        step_id: str,
        parameters: dict[str, object],
        method_spec: AnalyticsMethodSpec,
        profile: DatasetProfile,
    ) -> None:
        profile_columns = {column.name for column in profile.columns}
        time_columns = set(profile.time_columns)

        target = parameters.get("target")
        if (
            isinstance(target, str)
            and method_spec.method_id not in {"column_property_check"}
            and target not in profile_columns
        ):
            raise PlanningError(f"Plan step {step_id!r} references unknown target column {target!r}.")

        group_by = parameters.get("group_by")
        if isinstance(group_by, list):
            invalid_groups = [column for column in group_by if column not in profile_columns]
            if invalid_groups:
                raise PlanningError(f"Plan step {step_id!r} references unknown group_by columns: {invalid_groups}.")

        time_column = parameters.get("time_column")
        if isinstance(time_column, str):
            if time_column not in profile_columns:
                raise PlanningError(f"Plan step {step_id!r} references unknown time_column {time_column!r}.")
            if method_spec.family_id in {"time_series_time_bucketing", "period_comparison"} and time_column not in time_columns:
                raise PlanningError(f"Plan step {step_id!r} requires a profiled time column, received {time_column!r}.")

        selected_columns = parameters.get("selected_columns")
        if isinstance(selected_columns, list):
            invalid_selected = [column for column in selected_columns if column not in profile_columns]
            if invalid_selected:
                raise PlanningError(f"Plan step {step_id!r} references unknown selected columns: {invalid_selected}.")

        feature_columns = parameters.get("feature_columns")
        if isinstance(feature_columns, list):
            invalid_features = [column for column in feature_columns if column not in profile_columns]
            if invalid_features:
                raise PlanningError(f"Plan step {step_id!r} references unknown feature columns: {invalid_features}.")

        comparison_columns = parameters.get("comparison_columns")
        if isinstance(comparison_columns, list):
            invalid_comparisons = [column for column in comparison_columns if column not in profile_columns]
            if invalid_comparisons:
                raise PlanningError(f"Plan step {step_id!r} references unknown comparison columns: {invalid_comparisons}.")

        filters = parameters.get("filters")
        if isinstance(filters, dict):
            invalid_filters = [field_name for field_name in filters if field_name not in profile_columns]
            if invalid_filters:
                raise PlanningError(f"Plan step {step_id!r} references unknown filter fields: {invalid_filters}.")

    def _validate_backend_support(
        self,
        step_id: str,
        tool_family: str,
        method_id: str,
        router: object,
    ) -> None:
        adapter = router.route(tool_family)
        supports_method = getattr(adapter, "supports_method", None)
        if callable(supports_method) and not supports_method(method_id):
            raise PlanningError(
                f"Plan step {step_id!r} uses tool_family {tool_family!r}, which does not support method {method_id!r}."
            )

    def _validate_plan_result_expectation(self, plan: AnalysisPlan, analytics_registry: object) -> None:
        if plan.expected_result_shape is None:
            return
        step_shapes: set[str] = set()
        for step in plan.steps:
            method_spec = analytics_registry.get_method(step.method_id or step.action)
            if method_spec is not None:
                step_shapes.update(self._normalize_output_shape(shape) for shape in method_spec.output_shapes)
        if not step_shapes:
            return
        compatible_shapes = {
            "scalar": {"scalar"},
            "verification": {"verification"},
            "table": {"table", "recordset", "timeseries", "statistical_test"},
        }.get(plan.expected_result_shape, {plan.expected_result_shape})
        if plan.expected_result_shape == "scalar" and self._plan_can_project_scalar_from_table(plan):
            return
        if not compatible_shapes.intersection(step_shapes):
            raise PlanningError(
                f"Analysis plan expects result shape {plan.expected_result_shape!r}, "
                f"but step methods produce {sorted(step_shapes)!r}."
            )

    def _plan_can_project_scalar_from_table(self, plan: AnalysisPlan) -> bool:
        expected_result_name = plan.expected_result_name or ""
        method_ids = {step.method_id or step.action for step in plan.steps}
        if "column_type_inventory" in method_ids and expected_result_name.endswith("_dtype"):
            return True
        if "distinct_value_count" in method_ids and (
            expected_result_name == "distinct_value_count" or expected_result_name.endswith("_distinct_count")
        ):
            return True
        return False

    def _normalize_output_shape(self, shape: str) -> str:
        if shape in {"count", "aggregate"}:
            return "scalar"
        if shape in {"recordset", "timeseries", "statistical_test"}:
            return "table"
        return shape
