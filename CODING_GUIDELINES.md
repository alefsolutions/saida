![SAIDA Banner](assets/github-banner.png)

# SAIDA 0.3.0 Coding Guidelines

## Purpose

These guidelines are intended specifically for **SAIDA 0.3.0**.

These guidelines define how SAIDA code should be written so the library remains:

- lightweight
- contract-first
- modular
- easy to test
- easy for LLMs and humans to extend

SAIDA is a canonical analytics framework.
It should stay simple, readable, and practical rather than becoming a heavy platform.

---

## Core Engineering Principles

### 1. Meaning first, execution second
SAIDA defines analytical meaning.
Backends perform computation.

Any numerical fact, metric, statistical output, model score, or forecast must come from backend execution or deterministic normalization logic, not from prompt interpretation or free-form LLM output.

Prompt understanding should use modern transformer-based NLP, optionally combined with deterministic rules.
That stage is allowed to extract structured request data or structured plans, but it is not the source of analytical truth.

LLMs may:
- interpret
- summarize
- explain
- plan

LLMs must not:
- invent statistics
- fabricate metrics
- override computed facts

### 2. Boring code is better than academic code
Choose human-readable code over clever, compressed, or overly abstract code every time.

SAIDA should prefer implementation styles that are easy to read, explain, debug, and extend.

This follows the Zen of Python:

- explicit is better than implicit
- simple is better than complex
- flat is better than nested
- sparse is better than dense
- readability counts
- in the face of ambiguity, refuse the temptation to guess
- if the implementation is hard to explain, it is a bad idea

Prefer:
- obvious control flow
- descriptive names
- straightforward branching
- small helper functions
- plain data structures when they are enough

Avoid:
- clever compression
- academic abstractions without a practical payoff
- dense one-liners that hide intent
- indirection that makes debugging harder

### 3. Lightweight by default
Prefer small, focused modules.

Avoid:
- unnecessary abstractions
- framework-heavy patterns
- deep inheritance trees
- hidden magic

Prefer:
- simple classes
- small pure functions
- explicit inputs and outputs
- composition over inheritance

### 4. Contract-first design
The public interface must be organized around clear canonical contracts.

Good:
```python
plan = canonicalize_input(payload)
result = execute_plan(plan)
```

Prefer:
- explicit `AnalysisPlan`
- explicit `AnalyticalResult`
- explicit adapter boundaries
- explicit backend routing

Avoid:
- hidden backend-specific meaning
- transport-layer concepts leaking into the core contracts
- public interfaces that depend on one source type or one backend

### 5. Structured analysis first, reasoning second
Core analytical workflows must function without LLMs.

Reasoning should be optional and additive.

Prompt understanding should be separated from reasoning.
Use transformer-based NLP or transformer-assisted canonicalization to produce structured plans or structured planning signals before routing.

### 6. Strong typing and explicit schemas
Use dataclasses or Pydantic consistently for shared domain objects.

Every major boundary should have typed objects for:
- plan
- result
- source metadata
- schema metadata
- model metadata where needed

### 7. Testability
Every adapter, validator, router, and result normalizer should be easy to unit test.

Prefer:
- pure functions where possible
- isolated compute modules
- minimal hidden state

---

## Repository Conventions

## Directory intent

For 0.3.0, the intended architecture should be kept clear in code organization:

- `core/` owns canonical meaning, validation, routing, and result normalization
- `sources/` owns source access and schema discovery
- `adapters/` owns backend translation
- `outputs/` owns delivery formatting
- `llm/` owns optional LLM integrations
- `tests/` verifies each layer

If the current repository is in transition, new code should move toward this structure rather than deepen the older shape.

---

## Python Style

### Version target
Use Python 3.11+ unless a lower version is explicitly needed.

### Naming
Use:
- `snake_case` for functions and modules
- `PascalCase` for classes
- `UPPER_SNAKE_CASE` for constants

### Function design
Functions should:
- do one thing well
- have explicit parameters
- return typed objects where practical
- avoid mutating external state unless necessary
- be easy for another engineer to understand quickly

Bad:
```python
def process_data(x):
    ...
```

Better:
```python
def canonicalize_prompt_input(payload: PromptPayload) -> AnalysisPlan:
    ...
```

### Class design
Prefer small service classes with explicit responsibilities.

Good examples:
- `InputCanonicalizer`
- `PlanValidator`
- `BackendRouter`
- `ResultCanonicalizer`

Avoid giant god classes.
Avoid clever object models when a simple function or plain class is clearer.

---

## Error Handling

Use library-specific exceptions.

Examples:
- `SaidaError`
- `AdapterError`
- `ContextError`
- `ProfileError`
- `PlanningError`
- `ComputeError`
- `ModelTrainingError`
- `ReasoningError`

Raise meaningful exceptions with actionable messages.

Bad:
```python
raise Exception("failed")
```

Better:
```python
raise PlanningError("Forecasting requires a datetime column and at least 12 observations.")
```

---

## Logging

Logging should be:
- minimal
- optional
- useful for debugging

Do not spam logs.

Log:
- source loading start/end
- plan canonicalization
- validation decisions
- backend routing
- compute stage transitions
- model training start/end
- important warnings

Do not log:
- full datasets
- secrets
- API keys
- excessive row-level data

---

## Dependencies

Keep dependencies minimal.

### Preferred core dependencies
- duckdb
- pandas
- polars
- numpy
- scipy
- sentence-transformers, transformers, or equivalent modern NLP tooling
- statsmodels
- scikit-learn
- geopandas
- tensorflow
- pydantic or dataclasses
- optional ollama or SDK integrations

### Avoid unless clearly justified
- large orchestration frameworks
- distributed systems dependencies
- heavyweight deep learning stacks in V1

---

## Source And Adapter Rules

Source access and backend adaptation are separate concerns.

Source layers must:
- connect to external data safely
- inspect schema
- expose metadata
- fail clearly when data is invalid

Source layers should not:
- perform analytics
- train models
- define analytical meaning

Backend adapters must:
- translate canonical plans into backend-specific logic
- keep backend-specific syntax out of the core meaning layer
- return enough structure for result canonicalization

Backend adapters should not:
- redefine the user intent
- bypass validation
- leak backend-specific result shapes directly as public contracts

---

## Semantic Context Rules

Markdown context should be treated as structured semantic hints.

Supported context categories may include:
- source summary
- table descriptions
- metric definitions
- business rules
- freshness expectations
- caveats
- trusted date fields
- preferred identifiers

Context parsers should:
- preserve raw markdown
- extract structured sections
- validate known sections
- tolerate partial context files

---

## Profiling Rules

Schema discovery and profiling must be deterministic.

It should inspect:
- column types
- null rates
- unique counts
- source schema
- likely IDs
- dimensions
- measures
- datetime columns
- backend suitability hints
- ML readiness hints where relevant

Profiling should not:
- guess business meaning beyond evidence
- perform full forecasting
- perform heavy ML training

---

## Planning Rules

Canonicalization and planning must prefer explicit structured plans first.

Optional LLM planning may be layered on top.

Prompts, API payloads, and direct plan input should all converge toward canonical `AnalysisPlan`.

Plans should always be represented as structured objects.

Each plan must define:
- task type
- ordered steps
- intended analytical meaning
- compute family used
- rationale
- validation warnings

A plan must be validated before execution.

---

## Compute Rules

Backends should be chosen because they are a good execution fit, not because they define the framework.

Examples of backend families:
- DuckDB for SQL analytics
- pandas / Polars for dataframe operations
- statsmodels for statistical models
- GeoPandas for spatial work
- ML backends for training, prediction, and forecasting

Rules:
- keep execution backend-agnostic at the core layer
- keep backend-specific logic inside adapters
- do not let backend constraints silently redefine canonical meaning
- keep ML training explicit
- do not auto-train on ingestion by default

---

## Reasoning Rules

Reasoning is optional.

Reasoning may:
- explain canonical results
- summarize results
- suggest next questions
- help resolve ambiguity when explicitly enabled

Reasoning must not:
- invent facts
- override computed metrics
- bypass validations
- execute plans

Reasoning integrations should remain LLM-provider agnostic.

---

## NLP Rules

NLP is responsible for structured signal extraction at the input boundary.

The default expectation for SAIDA is modern transformer-based NLP rather than legacy rule-only parsing.

NLP may:
- classify user intent
- extract metrics, targets, and dimensions
- extract dates, periods, filters, and grouping hints
- help normalize raw prompt text into canonical plan structure

NLP must not:
- compute metrics
- explain results as if they were computed facts
- bypass plan validation
- execute plans

---

## Results Rules

Every public result should be self-describing enough for downstream use.

Canonical results should include at least:
- `result_type`
- `schema`
- `data`
- `metadata`

Results should be useful both to:
- humans
- calling Python code
- output formatters
- plugins

---

## Testing Strategy

Minimum testing expectations:

### Unit tests
For:
- input canonicalization
- validation
- source adapters
- backend adapters
- routing
- result normalization

### Integration tests
For:
- prompt to plan flow
- API payload to plan flow
- plan to backend execution flow
- backend result to canonical result flow

### Golden tests
Useful for:
- stable canonical outputs
- plan generation outputs
- output formatting outputs

---

## Documentation Standards

Every public class and function should have:
- a clear docstring
- typed parameters
- typed returns where practical

Important modules should also include:
- short usage examples
- edge cases
- assumptions
- architectural boundary notes where useful

---

## Codex Guidance

When generating code for SAIDA:

- choose boring, readable code over clever code
- keep files small
- keep responsibilities narrow
- prefer explicit schemas
- avoid speculative abstractions
- avoid premature optimization
- preserve the separation between meaning and execution
- preserve canonical plan and canonical result boundaries
- treat LLM integration as optional

---

## Final Rule

If there is a choice between:
- cleverness
- clarity

choose clarity.
