![SAIDA Banner](../../assets/github-banner.png)

# SAIDA Architecture

[![Version](https://img.shields.io/badge/version-0.3.0-1f6feb)](../../pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-2ea043)](../../LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)](../../pyproject.toml)

SAIDA is a plan-first analytics framework.

The core runtime is:

- `Dataset`
- `AnalysisPlan`
- execution DAG validation
- execution artifact store
- validation
- execution
- `AnalysisResult`

Everything else is built around that.

## Core Principle

SAIDA is designed so the same dataset and the same `AnalysisPlan` produce the same `AnalysisResult`.

That makes it useful for:

- BI dashboards
- backend analytics APIs
- internal reporting tools
- regression testing for analytics jobs

## High-Level Flow

Core flow:

- `Source -> Dataset -> AnalysisPlan -> Validate -> Execute -> AnalysisResult -> OutputAdapter`

Optional frontend flow:

- `Prompt -> Plan generator -> candidate AnalysisPlan -> Validate -> Execute -> AnalysisResult`
- `Relational SQL Source -> schema discovery -> access planning -> Dataset -> candidate AnalysisPlan -> Validate -> Execute -> AnalysisResult`

The optional frontend can use rules or an LLM, but the framework itself executes only validated plans.

## Main Layers

### 1. Sources

Purpose:

- load external data into a canonical `Dataset`
- parse optional source context
- build deterministic `DatasetProfile`

Main abstractions and built-ins:

- `SourceInterface`
- `CSVSource`
- `ExcelSource`
- `JSONSource`
- `PandasSource`
- `SQLiteSource`
- `PostgreSQLSource`
- `MySQLSource`
- `SourceContextParser`
- `SchemaDiscoveryService`

Relational SQL sources can now also do source-side work before the core ever sees a dataset:

- discover schema metadata with SQLAlchemy
- normalize tables, columns, and foreign-key relationships
- build deterministic relational access plans
- render materialization SQL
- return a canonical `Dataset` to the unchanged core

### 2. Plan Generation

Purpose:

- generate a candidate `AnalysisPlan`

Important note:

- this layer is optional
- authored plans can skip it entirely

Main abstractions:

- `AnalysisPlanGeneratorInterface`
- `PromptAnalysisFrontend`
- rule-based generators
- LLM-assisted generators

For relational SQL sources, prompt planning now has a source-aware path:

- `PromptAnalysisFrontend.prepare_source_analysis(...)`
- `PromptAnalysisFrontend.plan_source(...)`
- `PromptAnalysisFrontend.analyze_source(...)`

### 3. Validation

Purpose:

- reject bad plans before execution

The validator checks:

- step structure
- graph structure
- method support
- required parameters
- field references
- dataset compatibility
- backend compatibility
- expected output and expected result shape
- step input refs
- step output refs
- cycle safety
- `final_output_ref`

Main component:

- `PlanValidator`

### 4. Analytics Registry

Purpose:

- define the supported analytics families and methods

The analytics registry is the single source of truth for:

- family ids
- method ids
- required inputs
- allowed configs
- output shapes
- input artifact kinds
- output artifact kinds
- node kinds
- default tool families

### 5. Compute

Purpose:

- execute validated plan steps through a deterministic DAG scheduler

Main abstractions and built-ins:

- `ComputeInterface`
- `DuckDBAdapter`
- `MetadataComputeAdapter`
- `StatsModelsAdapter`
- `MlAdapter`
- `BackendRouter`

Execution behavior:

- steps are scheduled in topological order
- single-step authored plans remain valid
- explicit artifact refs can connect one step output to another step input
- execution stays deterministic and single-threaded in the current release
- runtime artifacts are registered in an execution-scoped artifact store

### 6. Results

Purpose:

- standardize execution output into `AnalysisResult`

Main components:

- `ResultCanonicalizer`
- `SummaryFormatter`

The portable JSON contract is:

- `saida.response.v2`

Important result behavior:

- `final_output_ref` is the first-class selector for the primary result
- `artifact_index` and `node_results` expose graph execution lineage
- legacy flat `metrics` and `tables` remain available for compatibility

### 7. Outputs

Purpose:

- render `AnalysisResult` into delivery formats

Main abstractions and built-ins:

- `OutputInterface`
- `JsonOutputAdapter`
- `SummaryOutputAdapter`

## Core Contracts

### `Dataset`

Represents loaded data plus optional semantic context.

### `DatasetProfile`

Represents deterministic dataset understanding:

- columns
- measures
- dimensions
- time columns
- identifiers
- warnings

### `AnalysisPlan`

Represents the work SAIDA should execute.

Important fields include:

- `plan_id`
- `task_type`
- `rationale`
- `steps`
- `dataset_refs`
- `inputs`
- `final_output_ref`
- `expected_result_name`
- `expected_result_shape`

Each `PlanStep` can now carry:

- explicit `inputs`
- explicit `outputs`
- `depends_on`
- `output_refs`

### `AnalysisResult`

Represents the standardized analytical output.

It carries:

- primary result
- supporting tables
- warnings
- execution metadata
- node execution records
- artifact lineage
- summaries
- canonical response payload

## What Is Optional

Prompt and LLM functionality are optional.

They can be used for:

- prompt-to-plan generation
- optional summary enhancement

They are not:

- the compute layer
- the validation layer
- the source of analytical truth

## Code Areas

Main packages:

- `src/saida/core/`
- `src/saida/sources/`
- `src/saida/adapters/`
- `src/saida/outputs/`
- `src/saida/plan_generation/`
- `src/saida/llm/`

Important boundary:

- relational schema discovery and source materialization live in `src/saida/sources/` and prompt/frontend orchestration
- `src/saida/core/` still stays centered on `Dataset`, `AnalysisPlan`, and `AnalysisResult`
