# Prompt Capability Architecture Note

## Purpose

This note captures the current live SAIDA prompt-to-plan architecture, compares it to the capability-graph direction proposed in `saida_capability_graph_codex_analysis_plan.md`, and introduces the first concrete scaffolding for a `PromptCapabilityContract` and capability registry.

The goal is to improve determinism, explainability, and validation without forcing an immediate rewrite of the existing planner.

## Current Live Pipeline

The current execution path is:

1. dataset validation
2. dataset profiling
3. prompt normalization into `AnalysisRequest`
4. deterministic plan building into `AnalysisPlan`
5. backend execution
6. canonical result packaging

The important implementation detail is that the live code is **not** a pure `prompt -> LLM -> executable plan` system.

Today the flow is closer to:

`prompt -> optional LLM proposal + deterministic normalization -> AnalysisRequest -> deterministic PlanBuilder -> AnalysisPlan -> execution`

Key files:

- `src/saida/engine.py`
- `src/saida/core/canonicalization.py`
- `src/saida/core/planning.py`
- `src/saida/core/capability_contract.py`
- `src/saida/core/discovery.py`

## What Already Exists

The current codebase already contains several building blocks that fit the capability-graph direction.

### 1. Strong dataset profiling

`DatasetProfile` and `ColumnProfile` already capture:

- measure candidates
- dimension candidates
- time candidates
- identifier candidates
- null ratios
- distinct ratios
- simple ML readiness

This is a strong base for a future data-feasibility layer.

### 2. Deterministic plan compilation

`PlanBuilder` already acts like a deterministic compiler from normalized request shape to executable plan steps.

This is valuable and should be preserved.

### 3. Descriptive capability inventory

`capability_contract.py` already lists:

- supported task types
- supported intent families
- accepted inputs
- expected result shapes

This is useful, but today it is mostly descriptive and prompt-facing rather than executable.

### 4. Optional bounded LLM prompting

The optional LLM interpreter returns a narrow `IntentProposal` object instead of directly generating the final plan.

That is already aligned with the principle that the LLM should assist interpretation but should not be the sole authority over executable structure.

## Main Gaps In The Current Design

### 1. Single-intent compression

`AnalysisRequest` carries one main `intent_name`.

This makes the interpretation layer flatter than real analytical requests, which often combine:

- ranking
- comparison
- trend
- segmentation
- verification

### 2. Heuristic routing is monolithic

`InputCanonicalizer` currently mixes together:

- intent detection
- target resolution
- grouping extraction
- filter extraction
- time extraction
- ranking logic
- tabular routing
- statistical workflow inference

This creates hidden coupling between prompt wording and final plan shape.

### 3. Capability contract is not yet executable

The current capability contract is not used as a real planning registry.

It does not currently drive:

- node activation
- dependency satisfaction
- compatibility checking
- subgraph validation
- deterministic graph-to-plan compilation

### 4. Data feasibility is partial and scattered

The current planner validates some feasibility conditions, such as:

- target column existence
- numeric target requirements
- grouping requirements
- time-column presence
- some statistical preconditions

However, it does not yet provide a separate first-class feasibility stage with structured statuses such as:

- supported but data infeasible
- supported but data insufficient
- supported with fallback

### 5. Silent fallback remains risky

The current normalization path can still default to the first measure when the prompt is underspecified.

That behavior keeps the pipeline moving, but it can create prompt-to-capability mismatch and plan mismatch.

## Recommended Architectural Direction

The recommended target is:

`prompt -> candidate capability signals -> PromptCapabilityContract -> capability validation -> data-feasibility validation -> deterministic plan compilation`

The contract should become the explicit handoff between interpretation and planning.

## New Scaffolding Added In This Change

This change introduces two additive core modules:

- `src/saida/core/prompt_capability_contract.py`
- `src/saida/core/capability_registry.py`

These modules are intentionally not wired into the live planner yet. They are scaffolding for incremental adoption.

### PromptCapabilityContract

The new contract object captures:

- candidate capabilities
- selected capabilities
- resolved parameters
- missing parameters
- unsupported capabilities
- ambiguity flags
- validation issues
- data-feasibility checks
- a derived contract status

This makes prompt interpretation inspectable and testable before plan compilation.

### Capability Registry

The new registry introduces explicit graph-style concepts:

- capability nodes
- typed edges
- categories:
  - domain
  - pattern
  - primitive
  - constraint
- relations:
  - specializes
  - requires
  - uses
  - compatible_with
  - incompatible_with
  - implies

The first-pass registry is grounded in the current live system rather than an aspirational future state.

Its pattern layer includes examples such as:

- `top_n_by_metric`
- `grouped_breakdown`
- `grouped_trend`
- `period_over_period_comparison`
- `tabular_record_retrieval`
- `null_verification`
- `significance_inference`

Its primitive layer is seeded from the current executable planner actions, such as:

- `ranked_breakdown`
- `group_breakdown`
- `time_bucket_breakdown`
- `period_comparison`
- `tabular_query`
- `null_check`

## Incremental Adoption Path

### Stage 1

Use the new registry and contract objects for documentation, testing, and internal inspection only.

### Stage 2

Build a bridge from `AnalysisRequest` into `PromptCapabilityContract`.

This change already includes a bootstrap helper that derives a first-pass contract from the current normalized request and dataset profile.

### Stage 3

Move current planner requirements into executable registry metadata, especially:

- required parameters
- compatibility rules
- output-shape expectations
- data-feasibility checks

### Stage 4

Refactor `PlanBuilder` so that intent-specific `if` branches are gradually replaced by:

- selected pattern nodes
- validated requirements
- deterministic pattern-to-plan compilation

### Stage 5

Split current composite planner actions into smaller canonical primitives only where it adds real value.

The first pass does not require that split yet.

## Recommendation

The capability-graph direction is a strong fit for SAIDA, but the best migration path is incremental.

The current deterministic planner, dataset profiling layer, and capability metadata should be treated as reusable assets, not discarded.

The immediate next step is not a full graph rewrite.

The immediate next step is to make prompt interpretation explicit, typed, and inspectable through `PromptCapabilityContract`, backed by an executable capability registry.
