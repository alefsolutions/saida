# SAIDA Schema Spec

This page summarizes the main live contracts in SAIDA.

Most important rule:

- canonical input: `AnalysisPlan`
- canonical output: `AnalysisResult`

## Main Runtime Contracts

- `Dataset`
- `DatasetProfile`
- `PlanInput`
- `PlanStep`
- `AnalysisPlan`
- `AnalysisResult`

Optional frontend contracts still exist for prompt generation, but they are not the core execution contract.

## `Dataset`

Represents one loaded dataset.

Main fields:

- `name`
- `source_type`
- `data`
- `metadata`
- `context`

## `DatasetProfile`

Represents deterministic dataset understanding.

Main fields:

- `dataset_name`
- `row_count`
- `column_count`
- `columns`
- `measure_columns`
- `dimension_columns`
- `time_columns`
- `identifier_columns`
- `warnings`
- `ml_readiness`

## `PlanInput`

Represents a declared plan input.

Main fields:

- `input_id`
- `kind`
- `ref`
- `metadata`

## `PlanStep`

Represents one executable step inside an `AnalysisPlan`.

Main fields:

- `step_id`
- `tool_family`
- `action`
- `method_id`
- `family`
- `parameters`
- `depends_on`
- `output_refs`
- `expected_output`
- `description`
- `metadata`

## `AnalysisPlan`

Represents the work SAIDA should execute.

Main fields:

- `plan_id`
- `version`
- `task_type`
- `rationale`
- `dataset_refs`
- `inputs`
- `steps`
- `expected_result_name`
- `expected_result_shape`
- `warnings`
- `metadata`

Notes:

- `version` is currently `saida.plan.v2`
- `expected_result_name` and `expected_result_shape` tell SAIDA what the primary result should be
- `to_dict()` returns a JSON-friendly representation of the plan

## `AnalysisResult`

Represents the standardized output of plan execution.

Main fields:

- `summary`
- `deterministic_summary`
- `llm_summary`
- `summary_source`
- `metrics`
- `tables`
- `warnings`
- `plan`
- `trace`
- `artifacts`
- `response`

## Response Envelope

The portable JSON payload is:

- `saida.response.v2`

Main top-level fields:

- `schema_version`
- `status`
- `request`
- `interpretation`
- `execution`
- `result`
- `tables`
- `summary`
- `history`
- `warnings`
- `errors`
- `meta`

## `execution` Block

Shows what SAIDA actually ran.

Main fields:

- `plan_id`
- `plan_version`
- `rationale`
- `step_count`
- `dataset_refs`
- `inputs`
- `expected_result_name`
- `expected_result_shape`
- `steps`

## `result` Block

Represents the primary result in canonical form.

Main fields:

- `name`
- `description`
- `physical_shape`
- `logical_shape`
- `dtype`
- `schema`
- `dimensions`
- `row_count`
- `labels`
- `pagination`
- `metadata`
- `value`

This same structure is used for:

- scalar values
- counts
- aggregates
- verification results
- recordsets
- grouped tables
- time-series tables
- statistical outputs

## Optional Frontend Contracts

These contracts are still useful for prompt-driven usage, but they are optional.

### `AnalysisRequest`

Represents normalized prompt interpretation before plan generation.

### `PromptCapabilityContract`

Represents prompt-side validation between interpretation and planning.

Use these only if you are working on the optional prompt-generation layer.
