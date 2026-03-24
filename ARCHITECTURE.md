![SAIDA Banner](assets/github-banner.png)

# SAIDA Architecture

This document describes the live `0.2.x` SAIDA architecture as it exists in the current codebase.

SAIDA is a contract-first analytics engine:

- prompts are input
- SAIDA normalizes meaning
- deterministic execution produces the result
- optional LLMs can assist interpretation and summary wording, but they do not execute analysis directly

## Core Goal

SAIDA exists to make prompt-driven analytics reliable enough for developers to build on.

That means the architecture is optimized for:

- deterministic planning
- inspectable interpretation
- stable response contracts
- safe clarification and refusal behavior
- reproducible routing across paraphrased prompts

## Live Runtime Flow

The main runtime entry point is `Saida.analyze(dataset, question)`.

The live execution flow is:

1. **Dataset validation**
   - SAIDA validates that the dataset is present and structurally usable.

2. **Dataset profiling**
   - SAIDA builds a `DatasetProfile` with:
   - row count
   - column count
   - measure columns
   - dimension columns
   - time columns
   - identifier columns
   - warnings and ML-readiness hints

3. **Prompt interpretation**
   - SAIDA converts the prompt into an `AnalysisRequest`.
   - This stage is handled by the canonicalizer and may use:
   - deterministic rule-based normalization
   - optional LLM prompt interpretation
   - optional LLM `canonical_question` condensation
   - optional LLM semantic proposal fields such as:
     - `operation`
     - `object_kind`
     - `object_ref`
     - `expected_result_shape`

4. **Prompt family derivation**
   - SAIDA maps the request into a supported prompt family such as:
   - `row_count`
   - `column_count`
   - `distinct_value_count`
   - `tabular_record_retrieval`
   - `grouped_entity_count`
   - `exploratory_metric_overview`

5. **Prompt capability contract**
   - SAIDA builds a `PromptCapabilityContract` that records:
   - selected capabilities
   - resolved parameters
   - missing parameters
   - ambiguity flags
   - validation issues
   - data-feasibility issues
   - overall contract status

6. **Deterministic planning**
   - SAIDA compiles the request into an `AnalysisPlan`.
   - For governed prompt families, plan compilation is increasingly template-driven from the prompt family catalog.
   - For other families, manual deterministic planning still applies.

7. **Backend execution**
   - SAIDA executes plan steps through adapters.
   - The live default backends are primarily:
   - metadata/profile-backed execution
   - DuckDB-backed analytical execution
   - stats-backed statistical execution

8. **Summary generation**
   - SAIDA generates a deterministic summary first.
   - If enabled, an optional LLM can rewrite the final summary, but the analysis result remains grounded in deterministic execution.

9. **Result canonicalization**
   - SAIDA packages everything into `AnalysisResult` plus a stable `saida.response.v2` JSON envelope.

In one line:

- `prompt -> AnalysisRequest -> prompt family -> PromptCapabilityContract -> AnalysisPlan -> execution -> AnalysisResult`

## Main Contracts

### `Dataset`

Represents one loaded dataset with:

- `name`
- `source_type`
- `data`
- `metadata`
- optional parsed `SourceContext`

### `DatasetProfile`

Represents deterministic understanding of the dataset surface:

- columns
- measures
- dimensions
- time columns
- identifiers
- warnings
- ML-readiness hints

### `AnalysisRequest`

Represents the normalized analytical request.

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

The `options` dictionary is where SAIDA carries richer interpretation details such as:

- `selected_columns`
- sorting and pagination
- statistical test settings
- `canonical_question`
- `prompt_family_hint`
- `semantic_intent`
- clarification/refusal metadata

### `PromptCapabilityContract`

Represents the validation bridge between interpretation and planning.

It answers:

- what SAIDA thinks the request is asking for
- whether that request is supported
- whether the dataset can satisfy it safely
- whether clarification or refusal is required

### `AnalysisPlan`

Represents deterministic executable steps.

It includes:

- `task_type`
- `rationale`
- ordered `PlanStep`s
- warnings

### `AnalysisResult`

Represents the final analytical product returned by `analyze()`.

It includes:

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

## Prompt Interpretation Model

The prompt layer is deliberately hybrid:

- deterministic rules remain the source of truth for supported execution
- optional LLMs can help interpret awkward or paraphrased prompts
- LLM output is validated and merged into deterministic normalization

The LLM layer can currently assist with:

- prompt interpretation
- canonical prompt condensation
- semantic operation/object hints
- final response wording

The LLM layer does **not** directly execute analysis.

## Prompt Family Model

Prompt families are now first-class.

They define:

- supported request shape
- required parameters
- allowed plan actions
- expected primary result shapes
- forbidden result mismatches
- governance level

The live catalog is documented in [PROMPT_FAMILY_CATALOG.md](./PROMPT_FAMILY_CATALOG.md).

Examples of governed families:

- `row_count`
- `column_count`
- `distinct_value_count`
- `column_type_lookup`
- `tabular_record_retrieval`
- `grouped_entity_count`
- `representation_ranking`

Examples of partial families:

- `metric_aggregate`
- `exploratory_metric_overview`
- `time_bucket_counts`

## Safe Failure Behavior

SAIDA does not try to answer every prompt at any cost.

The live architecture supports:

- `ok`
- `clarify`
- `refuse`

This is intentional.

If a prompt is ambiguous, unsupported, or unsafe to guess, SAIDA should clarify or refuse rather than fabricate a plausible but wrong analytical path.

## Compute Layer

The current execution layer is centered on:

- metadata/profile-backed operations
- DuckDB analytical execution
- StatsModels-backed statistical execution

Live prompt families cover:

- metadata inventories and counts
- scalar metric aggregates
- grouped entity counts
- grouped metric tables
- distinct value listing and counting
- tabular row retrieval
- verification workflows
- ranking workflows
- time coverage and time buckets
- adjacent period comparison
- several statistical workflows

## Optional And Deferred APIs

The public `Saida` object also exposes:

- `profile()`
- `capabilities()`
- `load_context()`
- `train()`
- `predict()`
- `forecast()`

The ML-facing methods currently reserve API surface only:

- `train`
- `predict`
- `forecast`

They are not the current strength of the codebase.

The live production surface today is primarily prompt-to-analysis.

## Source Adapters

The current source layer exports:

- `CSVSource`
- `ExcelSource`
- `JSONSource`
- `PandasSource`
- `SQLSource`

These load external data into the canonical `Dataset` contract used by the engine.

## Output Contract

The live JSON response contract is `saida.response.v2`.

Top-level fields include:

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

The `interpretation` section now exposes key internal routing data such as:

- `prompt_family`
- `intent_name`
- `semantic_intent`
- `capability_contract`

## Testing Strategy

The repository uses `spec_tests/` to validate behavior across layers, including:

- normalizer behavior
- prompt-family routing
- planner invariants
- engine behavior
- result shaping
- playground behavior
- paraphrase reproducibility
- acceptance matrices

The practical goal is not just “does it run,” but:

- does the same need map to the same plan
- does the same plan produce the same result shape
- do unsupported prompts fail safely

## Summary

The live SAIDA architecture is no longer just prompt parsing plus compute.

It is now a layered prompt-to-analysis system built around:

- `AnalysisRequest`
- prompt families
- `PromptCapabilityContract`
- deterministic `AnalysisPlan`
- canonical `AnalysisResult`

That is the foundation the current codebase is actually using today.
