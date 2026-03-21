![SAIDA Banner](assets/github-banner.png)

# SAIDA 0.2.0 File Structure

This document reflects the target **SAIDA 0.2.0** structure described in `ARCHITECTURE.md`.

## Target 0.2.0 Layout

```text
saida/
|-- core/
|-- adapters/
|-- sources/
|-- outputs/
|-- llm/
`-- tests/
```

## Directory Intent

### `core/`

Owns canonical meaning and orchestration.

Expected responsibilities:

- canonical plan construction
- validation
- routing
- result canonicalization

### `adapters/`

Owns translation between canonical plans and execution backends.

Examples:

- DuckDB adapter
- pandas adapter
- statsmodels adapter
- GeoPandas adapter

### `sources/`

Owns source access and schema discovery.

Examples:

- CSV
- Excel
- PostgreSQL
- MySQL
- MS Access
- GIS sources

### `outputs/`

Owns presentation and delivery transforms for canonical results.

Examples:

- JSON
- CSV
- Excel
- XML
- SQL

### `llm/`

Owns optional LLM integrations.

Rule:

- LLM helps with structured plans or output wording
- LLM does not execute

### `tests/`

Owns per-layer verification.

Examples:

- input tests
- validation tests
- adapter execution tests
- result normalization tests

## Important Note

The current repository may still be in transition.

This file describes the target 0.2.0 architecture layout, not necessarily every current folder exactly as it exists today.
