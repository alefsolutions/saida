![SAIDA Banner](assets/github-banner.png)

# SAIDA Schema Spec

This document summarizes the live canonical contracts used by the current SAIDA codebase.

If you want the system flow, see [ARCHITECTURE.md](./ARCHITECTURE.md).

## Main Live Contracts

The current runtime is centered on these core objects:

- `Dataset`
- `DatasetProfile`
- `AnalysisRequest`
- `PromptCapabilityContract`
- `AnalysisPlan`
- `AnalysisResult`

## `Dataset`

`Dataset` is the engine input after loading through a source adapter.

Fields:

- `name`
- `source_type`
- `data`
- `metadata`
- `context`

`context` is optional and holds parsed markdown business context.

## `DatasetProfile`

`DatasetProfile` is the deterministic schema-and-surface understanding of a dataset.

Fields include:

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

This profile is used heavily by normalization, validation, and planning.

## `AnalysisRequest`

`AnalysisRequest` is the normalized analytical request produced before planning.

Live fields:

- `question`
- `prompt_family`
- `intent_name`
- `task_type_hint`
- `target`
- `aggregation`
- `horizon`
- `filters`
- `group_by`
- `time_reference`
- `options`

### Request Semantics

Important distinctions in the live code:

- `target` is not a generic "all referenced columns" field
- row-level tabular retrieval typically carries selected fields in `options["selected_columns"]`
- `group_by` is `None` internally when no grouping is resolved
- `filters` and `time_reference` are optional and may be absent internally

### Rich `options`

The `options` dictionary carries many request-level extensions, including:

- `selected_columns`
- `sort_by`
- `sort_direction`
- `limit`
- `page`
- `page_size`
- `ranking_direction`
- `ranking_limit`
- `statistical_test`
- `comparison_columns`
- `feature_columns`
- `regression_target`
- `canonical_question`
- `canonical_question_used`
- `prompt_family_hint`
- `llm_confidence`
- `semantic_intent`
- `analysis_outcome`
- `llm_message`

### `semantic_intent`

The live request contract can now carry a semantic intent object in `options["semantic_intent"]`.

This is used to express operation/object semantics such as:

- `operation`
- `object_kind`
- `object_ref`
- `expected_result_shape`
- `source`

Example:

```json
{
  "operation": "count",
  "object_kind": "rows",
  "expected_result_shape": "count",
  "source": "rules"
}
```

## `PromptCapabilityContract`

`PromptCapabilityContract` is the structured bridge between prompt interpretation and deterministic planning.

It captures:

- `question`
- `dataset_name`
- `status`
- `prompt_family`
- `task_type_hint`
- `intent_name`
- `family_spec`
- `candidate_capabilities`
- `selected_capabilities`
- `resolved_parameters`
- `missing_parameters`
- `unsupported_capabilities`
- `ambiguity_flags`
- `validation_issues`
- `data_feasibility`
- `warnings`
- `notes`

Representative contract statuses include:

- `supported_and_data_feasible`
- `supported_but_data_infeasible`
- `supported_but_data_insufficient`
- `unsupported_capability`

## `AnalysisPlan`

`AnalysisPlan` is the canonical executable plan.

Fields:

- `task_type`
- `rationale`
- `steps`
- `warnings`

Each `PlanStep` includes:

- `step_id`
- `tool_family`
- `action`
- `parameters`
- `description`

## `AnalysisResult`

`AnalysisResult` is the main output object returned by `Saida.analyze()`.

Fields:

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

The portable JSON contract is stored in `response` and exposed through:

```python
result.to_response_dict()
```

## Live JSON Envelope

The live schema version is:

- `saida.response.v2`

Top-level envelope fields:

- `schema_version`
- `status`
- `request`
- `interpretation`
- `execution`
- `result`
- `tables`
- `reasoning`
- `history`
- `warnings`
- `errors`
- `meta`

## `request` Block

The top-level `request` block currently includes:

- `question`
- `dataset.name`

It is intentionally compact and user-facing.

## `interpretation` Block

The `interpretation` block is the most important explainability surface.

Current fields:

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

Important normalization note:

- `group_by` is emitted as `[]` in response JSON when no grouping is present
- `filters` is emitted as `{}`
- `time_reference` is emitted as `{}`

That JSON canonicalization is intentional even when the internal request uses `None`.

## `execution` Block

The `execution` block summarizes the deterministic plan that ran.

Fields:

- `status`
- `tool_families`
- `rationale`
- `step_count`
- `steps`

Each step entry includes:

- `step_id`
- `tool_family`
- `action`
- `description`
- `parameters`

## Primary `result` Object

The primary `result` object is a canonical self-describing result surface.

Current fields:

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

## Current Physical Shapes

The live code emits these physical shapes:

- `scalar`
- `vector`
- `object`
- `recordset`

## Current Logical Shapes

The live code emits these logical shapes:

- `empty`
- `scalar`
- `count`
- `aggregate`
- `table`
- `recordset`
- `timeseries`
- `verification`
- `distribution`
- `correlation_matrix`
- `statistical_test`

## Current Dtypes

Top-level result dtypes currently include:

- `null`
- `boolean`
- `integer`
- `float`
- `datetime`
- `string`
- `object`
- `record`

Structured table schemas currently use:

- `boolean`
- `integer`
- `float`
- `datetime`
- `string`

Non-finite numeric values are normalized to `null` in the response contract.

## `tables` Block

The `tables` block contains secondary structured outputs.

Each table entry is normalized with:

- name
- description
- canonical schema
- row count
- shape metadata
- pagination metadata when relevant
- JSON-safe row values

## Pagination Contract

Paginated tabular outputs currently expose:

- `page`
- `page_size`
- `total_rows`
- `returned_rows`
- `has_next_page`
- `has_previous_page`
- `offset`
- `next_page_token`

These appear in:

- `result.pagination` when the primary result is paginated
- `result.metadata.pagination`
- the relevant table entry metadata

## `reasoning` Block

The reasoning block contains summary-level explanation fields:

- `summary`
- `deterministic_summary`
- `llm_summary`
- `summary_source`

This lets consumers distinguish:

- deterministic wording
- optional LLM wording
- final chosen summary source

## `history` Block

`history` is the execution trace.

Each event includes:

- `stage`
- `message`
- `payload`

Typical stages include:

- adapter
- context
- profiling
- llm
- nlp
- contract
- planning
- compute
- results

## `meta` Block

The `meta` block carries extra inspection details, including:

- dataset summary
- prompt family
- capability contract status
- plan warnings
- warning count
- metrics
- metric lookup
- table names

## Result Shape Examples

### Count Result

Example shape for row counts or metadata counts:

- `physical_shape = scalar`
- `logical_shape = count`
- `dtype = integer`

### Aggregate Result

Example shape for sum/mean/min/max:

- `physical_shape = scalar`
- `logical_shape = aggregate`
- `dtype = float` or `integer`

### Verification Result

Example shape for presence/null/property checks:

- `physical_shape = object`
- `logical_shape = verification`

### Tabular Retrieval Result

Example shape for row retrieval:

- `physical_shape = recordset`
- `logical_shape = recordset`

### Time-Series Result

Example shape for counts or metrics by month/quarter/year:

- `physical_shape = recordset`
- `logical_shape = timeseries`

## Stability Notes

The current schema is designed to be stable enough for applications to integrate with:

- `result`
- `tables`
- `interpretation`
- `meta`

The most important public integration targets today are:

- `AnalysisResult`
- `saida.response.v2`

Those are the contracts developers should treat as the live surface.
