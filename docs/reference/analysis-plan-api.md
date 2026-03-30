# AnalysisPlan API Reference

This page is the contract-oriented reference for authoring a valid `AnalysisPlan` in SAIDA `0.3.0`.

Use this page when you want:

- the full field list for `AnalysisPlan`
- the full field list for `PlanStep`
- the allowed enum-like values used by the live runtime
- guidance on where values are free-form vs registry-backed
- a copyable minimal valid plan example

If you want workflow examples, see [API Usage](./api-usage.md).
If you want schema summaries for all runtime contracts, see [Schema Spec](./schema-spec.md).
If you want DAG authoring examples, see [DAG Plan Authoring](../guides/dag-plan-authoring.md).

## Contract Status

Most important rules:

- canonical executable input: `AnalysisPlan`
- execution model: strict DAG validation before compute
- current plan version: `saida.plan.v2`

The `AnalysisPlan` contract is defined in:

- [contracts.py](C:/Git Projects/saida/src/saida/core/contracts.py)
- [validation.py](C:/Git Projects/saida/src/saida/core/validation.py)
- [analytics_registry.py](C:/Git Projects/saida/src/saida/core/analytics_registry.py)

## Top-Level Types

The plan contract is composed of these dataclasses:

- `AnalysisPlan`
- `PlanInput`
- `PlanStep`
- `StepInputRef`
- `StepOutputSpec`

## AnalysisPlan

Represents one explicit executable analysis workflow.

### Fields

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `task_type` | `str` | yes | High-level workflow mode for the plan. |
| `rationale` | `str` | yes | Human-readable reason for the plan. |
| `steps` | `list[PlanStep]` | yes | Ordered declared steps. Execution is DAG-oriented, not merely positional. |
| `warnings` | `list[str]` | no | Non-fatal authoring warnings. |
| `plan_id` | `str \| None` | no | Optional stable plan identifier. |
| `version` | `str` | no | Plan schema version. Defaults to `saida.plan.v2`. |
| `dataset_refs` | `list[str]` | yes | Dataset refs used by the plan. |
| `inputs` | `list[PlanInput]` | yes | Declared plan-level inputs. |
| `expected_result_name` | `str \| None` | no | Intended primary result name. |
| `expected_result_shape` | `str \| None` | no | Intended primary result logical shape. |
| `final_output_ref` | `str \| None` | yes | Preferred terminal artifact to surface as the primary result. |
| `metadata` | `dict[str, Any]` | no | Optional plan-level metadata. |

### Allowed / expected values

#### `version`

Current expected value:

- `saida.plan.v2`

#### `task_type`

Current runtime-recognized values:

- `descriptive`
- `diagnostic`
- `statistical`
- `predictive`
- `forecasting`
- `clarification`
- `unavailable`

The most common authored value is `descriptive`.

#### `expected_result_shape`

Common runtime values:

- `scalar`
- `count`
- `aggregate`
- `table`
- `recordset`
- `verification`
- `timeseries`
- `distribution`
- `correlation_matrix`
- `statistical_test`

Notes:

- this value is advisory for packaging and validation alignment
- the final runtime result is ultimately selected from `final_output_ref`

### Validation expectations

A strict DAG-valid `AnalysisPlan` should:

- declare `dataset_refs`
- declare `inputs`
- declare `final_output_ref`
- ensure every step has explicit `inputs`
- ensure every step has explicit `outputs`
- ensure every step has explicit `output_refs`
- ensure every step has `method_id`, `family`, and `expected_output`
- ensure every step-output reference resolves to an earlier produced artifact or a plan input

## PlanInput

Represents one named input into the plan.

### Fields

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `input_id` | `str` | yes | Local plan input name. |
| `kind` | `str` | yes | Input kind. |
| `ref` | `str` | yes | External reference name. Usually the dataset name for dataset-backed plans. |
| `metadata` | `dict[str, Any]` | no | Optional metadata. |

### Allowed / expected values

#### `kind`

Current practical value:

- `dataset`

The runtime is artifact-capable, but plan-level inputs today are primarily dataset inputs.

### Typical example

```python
PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)
```

## PlanStep

Represents one executable node in the DAG.

### Fields

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `step_id` | `str` | yes | Stable local step id. |
| `tool_family` | `str` | yes | Compute backend family that executes the step. |
| `action` | `str` | yes | Action name used by the backend. Usually matches `method_id`. |
| `parameters` | `dict[str, Any]` | yes | Method-specific parameter payload. |
| `description` | `str` | yes | Human-readable description. |
| `family` | `str \| None` | yes | Analytics family id for the method. |
| `method_id` | `str \| None` | yes | Canonical analytics method id. |
| `depends_on` | `list[str]` | no | Optional dependency step ids. |
| `output_refs` | `list[str]` | yes | Output refs produced by the step. |
| `expected_output` | `dict[str, Any] \| None` | yes | Primary declared output summary. |
| `inputs` | `list[StepInputRef]` | yes | Directed declared inputs into the step. |
| `outputs` | `list[StepOutputSpec]` | yes | Declared output specs. |
| `metadata` | `dict[str, Any]` | no | Optional step metadata. |

### Allowed values

#### `tool_family`

Current runtime values:

- `duckdb`
- `metadata`
- `stats`
- `ml`

Notes:

- `ml` is reserved and not the strongest current stable area
- most authored plans today use `duckdb`, `metadata`, or `stats`

#### `family`

Current analytics family ids from the live registry:

- `selection_filtering`
- `projection_field_selection`
- `transformation`
- `joining`
- `aggregation_grouping`
- `ranking`
- `validation_verification`
- `schema_metadata_inspection`
- `distinct_cardinality_analysis`
- `time_series_time_bucketing`
- `period_comparison`
- `statistical_inference`
- `diagnostic_workflows`
- `predictive_forecasting`
- `output_preparation`

#### `method_id`

Current method ids from the live registry:

##### Selection / projection / transforms

- `tabular_query`
- `filter_frame`
- `select_columns`
- `sort_frame`
- `limit_frame`
- `distinct_frame`
- `derive_column`
- `group_frame`
- `aggregate_frame`
- `time_bucket_frame`
- `join_frame`
- `union_frame`

##### Aggregation / ranking / verification

- `row_count`
- `count_rows_by_group`
- `aggregate_value`
- `group_breakdown`
- `grouped_tabular_query`
- `rank_frame`
- `ranked_rows`
- `ranked_breakdown`
- `row_existence`
- `time_value_exists`
- `null_check`
- `threshold_check`
- `column_property_check`
- `column_presence_check`

##### Metadata / distinct / time

- `column_count`
- `column_inventory`
- `column_type_inventory`
- `numeric_column_inventory`
- `numeric_column_count`
- `categorical_column_inventory`
- `categorical_column_count`
- `measure_inventory`
- `measure_count`
- `dimension_inventory`
- `dimension_count`
- `time_column_inventory`
- `time_column_count`
- `missing_value_inventory`
- `identifier_inventory`
- `identifier_count`
- `high_cardinality_inventory`
- `high_cardinality_count`
- `distinct_values`
- `distinct_value_count`
- `time_coverage`
- `time_bucket_counts`
- `time_bucket_breakdown`
- `time_trend`
- `period_comparison`
- `grouped_period_comparison`
- `top_movers`
- `contribution_breakdown`

##### Statistical / diagnostic / forecasting

- `significance_inference`
- `t_test`
- `chi_square`
- `anova`
- `mann_whitney`
- `confidence_interval`
- `regression_significance`
- `power_analysis`
- `sample_size_estimate`
- `dataset_summary`
- `missingness_summary`
- `numeric_summary`
- `distribution_summary`
- `target_correlation`
- `anomaly_summary`
- `time_series_diagnostics`
- `group_mean_comparison`
- `forecast`

### `action`

Current recommendation:

- use the same value as `method_id`

The runtime keeps both for compatibility with planner and adapter conventions, but authored plans should generally align them.

## StepInputRef

Represents one directed input edge into a step.

### Fields

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `input_id` | `str` | yes | Local input name inside the step. |
| `source_type` | `str` | yes | Where the input comes from. |
| `ref` | `str` | yes | Referenced plan input id or upstream output ref. |
| `alias` | `str \| None` | no | Optional backend alias. |
| `required` | `bool` | no | Whether the input is required. Defaults to `True`. |
| `expected_kind` | `str \| None` | no | Expected artifact kind. |
| `metadata` | `dict[str, Any]` | no | Optional edge metadata. |

### Allowed / expected values

#### `source_type`

Current runtime values:

- `plan_input`
- `step_output`
- `artifact`

#### `expected_kind`

Common runtime values:

- `dataset`
- `frame`
- `scalar`
- `verification`
- `model`

In practice, most current plans use:

- `dataset` for plan inputs
- `frame` or `scalar` for upstream step outputs

## StepOutputSpec

Represents one declared output produced by a step.

### Fields

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `output_id` | `str` | yes | Produced output ref. |
| `kind` | `str` | yes | Physical artifact kind. |
| `logical_shape` | `str \| None` | no | Logical result shape. |
| `physical_shape` | `str \| None` | no | Physical payload form. |
| `semantic_kind` | `str \| None` | no | Rich semantic artifact type. |
| `is_primary` | `bool` | no | Whether this output is the primary output for the step. Defaults to `True`. |
| `metadata` | `dict[str, Any]` | no | Optional output metadata. |

### Allowed / expected values

#### `kind`

Current common values:

- `frame`
- `scalar`
- `verification`
- `model`

#### `logical_shape`

Current common values:

- `scalar`
- `count`
- `aggregate`
- `table`
- `recordset`
- `verification`
- `timeseries`
- `distribution`
- `correlation_matrix`
- `statistical_test`

#### `physical_shape`

Current common values:

- `scalar`
- `recordset`
- `vector`
- `object`

#### `semantic_kind`

Current known semantic kinds in the runtime:

- `table`
- `scalar`
- `grouped_table`
- `ranked_table`
- `time_series`
- `verification_result`
- `statistical_test`
- `feature_matrix`
- `prediction_series`

Notes:

- `semantic_kind` may be omitted in authored plans and inferred by the runtime when appropriate
- for high-control authored plans, declaring it explicitly is valid

## Parameter Conventions

`PlanStep.parameters` is intentionally method-specific rather than globally fixed.

Common parameter keys across many methods include:

- `filters`
- `selected_columns`
- `sort_by`
- `sort_direction`
- `limit`
- `page`
- `page_size`
- `target`
- `aggregation`
- `group_by`
- `time_column`
- `bucket`
- `time_reference`

Examples:

```python
parameters={"filters": {"country": "Japan"}}
```

```python
parameters={"target": "total_sales", "aggregation": "sum", "group_by": ["country"]}
```

```python
parameters={"sort_by": "order_date", "sort_direction": "desc", "page": 1, "page_size": 5}
```

For the authoritative method-by-method surface, the live source of truth is the analytics registry:

- [analytics_registry.py](C:/Git Projects/saida/src/saida/core/analytics_registry.py)

## Minimal Valid Example

```python
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec

plan = AnalysisPlan(
    task_type="descriptive",
    rationale="Return the first five rows.",
    dataset_refs=["sales_sqlite_40"],
    inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref="sales_sqlite_40")],
    expected_result_name="first_five_rows",
    expected_result_shape="recordset",
    final_output_ref="first_five_rows",
    steps=[
        PlanStep(
            step_id="first_five_rows",
            tool_family="duckdb",
            action="tabular_query",
            method_id="tabular_query",
            family="projection_field_selection",
            parameters={
                "sort_by": "order_date",
                "sort_direction": "asc",
                "page": 1,
                "page_size": 5,
            },
            description="Return the first five rows ordered by date ascending.",
            inputs=[
                StepInputRef(
                    input_id="dataset_input",
                    source_type="plan_input",
                    ref="primary_dataset",
                    expected_kind="dataset",
                )
            ],
            output_refs=["first_five_rows"],
            outputs=[
                StepOutputSpec(
                    output_id="first_five_rows",
                    kind="frame",
                    logical_shape="recordset",
                    physical_shape="recordset",
                )
            ],
            expected_output={
                "output_id": "first_five_rows",
                "logical_shape": "recordset",
                "physical_shape": "recordset",
            },
        )
    ],
)
```

## Best Practices

- prefer explicit DAG plans over implicit sequencing assumptions
- keep `action == method_id` unless you have a specific adapter reason not to
- declare `final_output_ref` explicitly
- declare `outputs` and `expected_output` explicitly
- use registry-backed `family` and `method_id` values
- validate authored plans before storing or reusing them

## Related References

- [API Usage](./api-usage.md)
- [Schema Spec](./schema-spec.md)
- [DAG Plan Authoring](../guides/dag-plan-authoring.md)
- [Prompt Family Catalog](./prompt-family-catalog.md)
