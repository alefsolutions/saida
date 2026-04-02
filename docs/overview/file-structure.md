![SAIDA Banner](../../assets/github-banner.png)

# SAIDA File Structure

[![Version](https://img.shields.io/badge/version-0.3.0-1f6feb)](../../pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-2ea043)](../../LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)](../../pyproject.toml)

This document describes the live repository structure and the role of each major package.

## Main Package Layout

```text
src/saida/
|-- adapters/
|-- core/
|-- llm/
|-- outputs/
|-- plan_generation/
`-- sources/

tests/
playground/
```

## Package Roles

### `src/saida/core/`

Owns the plan-first framework core.

Main responsibilities:

- contracts
- analytics registry
- validation
- routing
- result canonicalization

This is the center of the framework runtime.

### `src/saida/sources/`

Owns how external data sources are loaded into canonical `Dataset` objects.

Live responsibilities:

- source interfaces
- source-side context parsing
- dataset profiling and schema discovery
- CSV loading
- Excel loading
- JSON loading
- pandas loading
- SQL-backed loading through `src/saida/sources/sql/`

### `src/saida/sources/sql/`

Owns relational SQL source implementation details.

Live responsibilities:

- shared SQL source base implementations
- SQLite / PostgreSQL / MySQL source modules
- SQLAlchemy-backed schema introspection
- relational schema models
- deterministic access planning
- SQL rendering for source-side materialization

### `src/saida/adapters/`

Owns canonical compute execution through formal compute interfaces.

Live responsibilities:

- `ComputeInterface`
- DuckDB-backed execution
- metadata/profile-backed execution
- statsmodels-backed execution
- reserved ML adapter surface

### `src/saida/outputs/`

Owns output rendering from `AnalysisResult`.

Live responsibilities:

- `OutputInterface`
- JSON output adapter
- summary output adapter
- summary formatting

### `src/saida/plan_generation/`

Owns optional plan generation.

Live responsibilities:

- `AnalysisPlanGeneratorInterface`
- prompt normalization / canonicalization
- prompt family catalog
- prompt plan contract
- plan building / prompt-family routing
- rule-based plan generation
- LLM-assisted plan generation
- OpenAI plan generation

This package supports the prompt-first convenience path without defining the execution core.

### `src/saida/llm/`

Owns optional LLM integrations.

Live responsibilities:

- provider abstractions
- OpenAI provider
- Ollama provider
- plan/summary proposal models

Rule:

- LLMs may generate candidate plans or summaries
- LLMs do not execute analysis directly

## Tests

### `tests/`

Owns automated verification for the live codebase.

Current testing emphasis includes:

- unit tests
- validator contract tests
- adapter tests
- plan-centric end-to-end execution tests
- plan reproducibility tests
- optional prompt generation tests

The test suite is centered on:

- `AnalysisPlan + Dataset -> AnalysisResult`

## Supporting Folders

### `playground/`

Contains local scripts and scenario-based sample data for trying SAIDA manually.

These are useful for experimentation, but they are not the framework contract itself.

## Architectural Reading Guide

If you want to understand the codebase quickly, start here:

1. `src/saida/core/contracts.py`
2. `src/saida/core/validation.py`
3. `src/saida/adapters/interfaces.py`
4. `src/saida/outputs/interfaces.py`
5. `src/saida/plan_generation/interfaces.py`
6. `src/saida/engine.py`

## Direction Note

Prompt-oriented modules remain because prompt-driven usage is still supported.

But the framework itself is centered on:

- sources
- canonical plans
- validation
- compute adapters
- standardized results
- output adapters
