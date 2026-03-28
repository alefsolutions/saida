![SAIDA Banner](assets/github-banner.png)

# SAIDA File Structure

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

spec_tests/
playground/
examples/
```

## Package Roles

### `src/saida/core/`

Owns the canonical framework contracts and orchestration helpers.

Main responsibilities:

- `Dataset`, `DatasetProfile`, `AnalysisPlan`, `AnalysisResult`
- analytics registry
- validation
- routing
- result canonicalization
- schema discovery

This is the closest thing to SAIDA's core engine surface.

### `src/saida/sources/`

Owns how external data sources are loaded into canonical `Dataset` objects.

Live responsibilities:

- source interfaces
- CSV loading
- Excel loading
- JSON loading
- pandas loading
- SQL-backed loading

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
- prompt capability contract
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
- prompt/response proposal models

Rule:

- LLMs may generate candidate plans or summaries
- LLMs do not execute analysis directly

## Tests

### `spec_tests/`

Owns automated verification for the live codebase.

Current testing emphasis includes:

- unit tests
- validator contract tests
- adapter tests
- plan-centric end-to-end execution tests
- plan reproducibility tests
- optional prompt generation tests

The test suite is increasingly centered on:

- `AnalysisPlan + Dataset -> AnalysisResult`

## Supporting Folders

### `examples/`

Contains sample datasets and dataset context markdown files.

### `playground/`

Contains local scripts for trying SAIDA manually.

These are useful for experimentation, but they are not the framework contract itself.

## Architectural Reading Guide

If you want to understand the codebase quickly, start here:

1. `src/saida/core/contracts.py`
2. `src/saida/core/validation.py`
3. `src/saida/adapters/interfaces.py`
4. `src/saida/outputs/interfaces.py`
5. `src/saida/plan_generation/interfaces.py`
6. `src/saida/engine.py`

## Important Direction Note

The repository still contains prompt-oriented modules because prompt-driven analysis remains supported.

But the structural center of the project is now shifting toward:

- source interfaces
- canonical plans
- validation
- compute adapters
- standardized results
- output adapters
