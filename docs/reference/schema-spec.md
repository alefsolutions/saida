![SAIDA Banner](../../assets/github-banner.png)

# SAIDA Schema Spec

[![Version](https://img.shields.io/badge/version-0.3.0-1f6feb)](../../pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-2ea043)](../../LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)](../../pyproject.toml)

This page summarizes the main live contracts in SAIDA.

If you need the exhaustive plan-authoring reference, see [AnalysisPlan API Reference](./analysis-plan-api.md).

Most important rule:

- canonical input: `AnalysisPlan`
- canonical output: `AnalysisResult`

## Main Runtime Contracts

- `Dataset`
- `DatasetProfile`
- `PlanInput`
- `StepInputRef`
- `StepOutputSpec`
- `PlanStep`
- `ExecutionArtifact`
- `NodeExecutionResult`
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

## `StepInputRef`

Represents one directed input edge into a plan step.

Main fields:

- `input_id`
- `source_type`
- `ref`
- `alias`
- `required`
- `expected_kind`
- `metadata`

## `StepOutputSpec`

Represents one declared step output.

Main fields:

- `output_id`
- `kind`
- `logical_shape`
- `physical_shape`
- `is_primary`
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
- `inputs`
- `outputs`
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
- `final_output_ref`
- `warnings`
- `metadata`

Notes:

- `version` is currently `saida.plan.v2`
- execution is DAG-oriented even when a plan is authored as a simple ordered step list
- `expected_result_name` and `expected_result_shape` tell SAIDA what the primary result should be
- `final_output_ref` identifies the preferred terminal artifact for canonical result selection
- `to_dict()` returns a JSON-friendly representation of the plan

## `ExecutionArtifact`

Represents one serialized runtime artifact exposed after execution.

Main fields:

- `artifact_id`
- `kind`
- `value`
- `logical_shape`
- `physical_shape`
- `producer_step_id`
- `metadata`

## `NodeExecutionResult`

Represents one executed step in the runtime graph.

Main fields:

- `step_id`
- `status`
- `consumed_inputs`
- `produced_outputs`
- `metadata`

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
- `node_results`
- `artifact_index`

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

The execution and meta sections now also expose artifact lineage and graph execution metadata.

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
- `node_results`
- `final_output_ref`
- `artifact_index`

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

### `PromptPlanContract`

Represents prompt-side validation between interpretation and planning.

Use these only if you are working on the optional prompt-generation layer.
