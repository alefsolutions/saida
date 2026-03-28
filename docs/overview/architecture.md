![SAIDA Banner](assets/github-banner.png)

# SAIDA Architecture

This document describes the live `0.2.x` SAIDA architecture.

The core direction is:

- `Dataset + AnalysisPlan -> Validate -> Execute -> AnalysisResult`

Optional frontend direction:

- `Natural language -> AnalysisPlanGenerator -> candidate AnalysisPlan -> Validate -> Execute -> AnalysisResult`

That distinction matters.

SAIDA is now centered on:

- canonical plans
- deterministic execution
- standardized results

Prompt handling and LLM usage are still supported, but they are optional frontend subsystems rather than the heart of the framework.

The execution core can be stated very plainly:

- `Dataset`
- `AnalysisPlan`
- validation
- execution
- `AnalysisResult`

## Architectural Principles

### Determinism

The core guarantee is:

- same dataset
- same `AnalysisPlan`
- same adapter behavior
- same `AnalysisResult`

### Contracts First

The canonical contracts are:

- `Dataset`
- `DatasetProfile`
- `AnalysisPlan`
- `AnalysisResult`

Optional frontend contracts exist too, such as:

- `AnalysisRequest`
- `PromptCapabilityContract`
- plan generator proposals

But those support the frontend path. They are not the framework source of truth.

### Clear Layer Separation

SAIDA now has explicit layers for:

- sourcing
- plan generation
- validation
- analytics family registry
- compute execution
- result standardization
- output rendering

### Replaceable Adapters

DuckDB, metadata-backed execution, statsmodels-backed execution, and JSON output are the built-in defaults.

They are important implementations, but they are not the architecture.

## Live High-Level Layers

### 1. Source Layer

Responsibility:

- standardize how data enters SAIDA

Live abstraction:

- `SourceInterface`

Live built-ins:

- `CSVSource`
- `ExcelSource`
- `JSONSource`
- `PandasSource`
- SQL sources such as `SQLiteSource`, `PostgreSQLSource`, and `MySQLSource`

Output of this layer:

- canonical `Dataset`

### 2. Plan Generation Layer

Responsibility:

- produce a candidate `AnalysisPlan`

Live abstraction:

- `AnalysisPlanGeneratorInterface`

Live generators:

- `RuleBasedPlanGenerator`
- `LlmAssistedPlanGenerator`
- `OpenAIPlanGenerator`

Important note:

- this layer is optional
- authored plans can skip it entirely

### 3. Validation Layer

Responsibility:

- reject invalid or incompatible plans before execution

Live component:

- `PlanValidator`

The validator now checks:

- step structure
- duplicate ids
- step dependencies
- analytics method validity
- required method inputs
- dataset reference compatibility
- field existence
- backend compatibility
- expected output compatibility
- expected result compatibility

### 4. Analytics Family Layer

Responsibility:

- define what SAIDA supports analytically

Live registries:

- analytics family and method registry
- prompt family catalog
- capability registry

The analytics registry is the compute-oriented definition:

- family ids
- method ids
- required inputs
- allowed configs
- output shapes
- default tool families

The prompt family catalog remains useful for optional prompt-to-plan generation and result shaping.

### 5. Compute Layer

Responsibility:

- execute validated plan steps

Live abstraction:

- `ComputeInterface`

Live built-ins:

- `DuckDBAdapter`
- `MetadataComputeAdapter`
- `StatsModelsAdapter`
- `MlAdapter`

Execution routing happens through:

- `BackendRouter`

Each `PlanStep` selects a `tool_family`, and the router chooses the appropriate adapter.

### 6. Result Layer

Responsibility:

- collect raw compute outputs
- standardize them into `AnalysisResult`
- produce the portable JSON response envelope

Live components:

- `ResultCanonicalizer`
- `SummaryFormatter`

The standardized JSON contract is:

- `saida.response.v2`

### 7. Output Layer

Responsibility:

- render `AnalysisResult` into delivery formats

Live abstraction:

- `OutputInterface`

Live built-ins:

- `JsonOutputAdapter`
- `SummaryOutputAdapter`

This keeps `AnalysisResult` as the source of truth while allowing different delivery targets.

## Main Runtime Flows

### Core Plan-First Flow

1. Load data through a source adapter.
2. Validate the dataset.
3. Profile the dataset.
4. Supply an `AnalysisPlan`.
5. Validate the plan with dataset/profile/backend context.
6. Execute plan steps through compute adapters.
7. Canonicalize the final result into `AnalysisResult`.
8. Render through an output adapter if needed.

### Optional Prompt-First Flow

1. Load and profile the dataset.
2. Use an optional plan generator to build a candidate plan.
3. Build optional frontend artifacts such as `AnalysisRequest`, `AnalysisInterpretation`, and `PromptCapabilityContract`.
4. Bind the plan to the dataset.
5. Validate the plan.
6. Execute it deterministically.
7. Return the standardized result.

The prompt-first path is still useful, but it now sits on top of the plan-first core.

## Core Live Contracts

### `Dataset`

Represents loaded source data plus optional business context.

### `DatasetProfile`

Represents deterministic schema and surface understanding:

- columns
- measures
- dimensions
- time columns
- identifiers
- warnings
- ML-readiness hints

### `AnalysisPlan`

The executable workflow contract.

Key fields include:

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

Each `PlanStep` includes:

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

### `AnalysisResult`

The standardized analytical output contract.

It includes:

- summaries
- metrics
- tables
- warnings
- plan
- trace
- artifacts
- response payload

## Where Prompt Handling Fits Now

Prompt handling remains part of SAIDA, but in a narrower role.

It is now best understood as:

- optional plan generation
- optional clarification support
- optional response wording support

It is not:

- the compute layer
- the execution contract
- the main architectural identity of SAIDA

## Main Code Areas

The current architecture is implemented mainly across:

- `src/saida/core/`
- `src/saida/adapters/`
- `src/saida/sources/`
- `src/saida/outputs/`
- `src/saida/plan_generation/`
- `src/saida/llm/`

## Current Strengths

The strongest parts of the current architecture are:

- the richer `AnalysisPlan` contract
- stronger validation before execution
- formal source, compute, and output interfaces
- deterministic compute routing
- standardized `AnalysisResult`
- growing plan-centric test coverage

## Remaining Cleanup Area

The main remaining cleanup work is removing prompt-first deadweight that still exists for backward compatibility inside:

- `canonicalization`
- `planning`
- engine-side prompt reconstruction helpers

That cleanup is separate from the core architecture, which is already moving in the right direction.
