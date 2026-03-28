![SAIDA Banner](assets/github-banner.png)

# SAIDA Schema Spec

This document summarizes the live canonical contracts used by SAIDA.

The most important design point is:

- `AnalysisPlan` is the main executable contract
- `AnalysisResult` is the main standardized output contract

Prompt-side contracts still exist, but they are optional frontend contracts rather than the execution core.

## Core Runtime Contracts

The main live contracts are:

- `Dataset`
- `DatasetProfile`
- `PlanInput`
- `PlanStep`
- `AnalysisPlan`
- `AnalysisResult`

Optional frontend contracts include:

- `AnalysisRequest`
- `PromptCapabilityContract`
- plan generation proposals

These remain available for optional prompt-generation workflows, not as the primary core framework API.

## `Dataset`

Represents one loaded dataset after passing through a source adapter.

Fields:

- `name`
- `source_type`
- `data`
- `metadata`
- `context`

Notes:

- `data` is typically a pandas `DataFrame`
- `context` is optional parsed business markdown

## `DatasetProfile`

Represents deterministic dataset understanding.

Important fields:

- `dataset_name`
- `row_count`
- `column_count`
- `columns`
- `measure_columns`
- `dimension_columns`
- `time_columns`
- `identifier_columns`
- `duplicate_row_count`
- `warnings`
- `ml_readiness`

This contract is used by:

- plan generation
- validation
- compute routing

## `PlanInput`

Represents a declared plan input.

Live fields:

- `input_id`
- `kind`
- `ref`
- `metadata`

Typical use:

- dataset inputs
- future external artifacts or named upstream outputs

## `PlanStep`

Represents one executable step inside an `AnalysisPlan`.

Live fields:

- `step_id`
- `tool_family`
- `action`
- `parameters`
- `description`
- `family`
- `method_id`
- `depends_on`
- `output_refs`
- `expected_output`
- `metadata`

### Meaning Of Key Fields

- `tool_family`
  - which compute adapter should execute the step

- `family`
  - canonical analytics family

- `action`
  - executable action name

- `method_id`
  - canonical analytics method id

- `depends_on`
  - ordered dependency references to earlier steps

- `output_refs`
  - named outputs exposed by the step

- `expected_output`
  - optional step-level expected output contract, such as logical shape

## `AnalysisPlan`

This is the canonical executable workflow contract.

Live fields:

- `plan_id`
- `version`
- `task_type`
- `rationale`
- `steps`
- `warnings`
- `dataset_refs`
- `inputs`
- `expected_result_name`
- `expected_result_shape`
- `metadata`

### Key design notes

- `version` is currently `saida.plan.v2`
- `dataset_refs` and `inputs` allow the plan to be explicit about its source dependencies
- `expected_result_name` and `expected_result_shape` describe the intended primary result
- result canonicalization uses those expected-result fields first, then step metadata and produced artifacts, to decide the primary `AnalysisResult.result`
- `metadata` carries execution and provenance hints such as:
  - dataset name
  - prompt family
  - interpretation snapshot
  - profile summary

### `AnalysisPlan.to_dict()`

Plans can be serialized through:

```python
plan.to_dict()
```

This returns a JSON-friendly representation of the canonical plan contract.

## `AnalysisResult`

This is the main standardized output object returned by SAIDA execution.

Live fields:

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

### Result intent

`AnalysisResult` is meant to be:

- deterministic
- inspectable
- portable
- application-friendly

## JSON Response Contract

The portable JSON response schema is:

- `saida.response.v2`

Top-level fields:

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

## `request` Block

The top-level `request` block is intentionally compact and user-facing.

Current fields:

- `question`
- `dataset.name`

## `interpretation` Block

This block describes how SAIDA understood the work.

Current fields include:

- `prompt_family`
- `intent_name`
- `semantic_intent`
- `task_type`
- `target`
- `aggregation`
- `group_by`
- `filters`
- `time_reference`
- `horizon`
- `options`
- `capability_contract`

Normalization notes:

- `group_by` is emitted as `[]` in response JSON when absent
- `filters` is emitted as `{}`
- `time_reference` is emitted as `{}`

Internally these may still be `None`.

## `execution` Block

This block describes what SAIDA actually executed.

Current fields include:

- `task_type`
- `rationale`
- `plan_id`
- `plan_version`
- `dataset_refs`
- `inputs`
- `expected_result_name`
- `expected_result_shape`
- `steps`

Each step in the response includes:

- `step_id`
- `tool_family`
- `family`
- `action`
- `method_id`
- `parameters`
- `depends_on`
- `output_refs`
- `expected_output`
- `description`
- `metadata`

## `result` Block

This is the primary standardized result.

Fields include:

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

This shape is used consistently across:

- scalar values
- counts
- aggregates
- verification objects
- recordsets
- grouped tables
- timeseries
- statistical result tables

## Supporting Tables

The `tables` array carries non-primary `TableArtifact` payloads in canonical JSON form.

This keeps the framework useful for:

- dashboard tables
- drill-down UIs
- statistical output
- supporting explainability artifacts

## Optional Frontend Contracts

These still matter for prompt-driven usage, but they are not the main execution identity.

### `AnalysisRequest`

Represents normalized prompt interpretation before planning.

Important fields:

- `question`
- `prompt_family`
- `intent_name`
- `task_type_hint`
- `target`
- `aggregation`
- `filters`
- `group_by`
- `time_reference`
- `options`

### `PromptCapabilityContract`

Represents structured validation between prompt interpretation and planning.

Important fields:

- `status`
- `prompt_family`
- `intent_name`
- `selected_capabilities`
- `resolved_parameters`
- `missing_parameters`
- `validation_issues`
- `data_feasibility`
- `warnings`

These contracts are most useful when SAIDA is used as a prompt-to-plan frontend.
