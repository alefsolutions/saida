![SAIDA Banner](../../assets/github-banner.png)

# Relational Sources

[![Version](https://img.shields.io/badge/version-0.3.0-1f6feb)](../../pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-2ea043)](../../LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)](../../pyproject.toml)

This page documents the relational source lifecycle that sits outside the SAIDA core.

The important boundary is:

- source adapters own relational discovery and query synthesis
- the core still receives only a canonical `Dataset`

## What Exists Today

Built-in SQL-backed sources:

- `SQLiteSource`
- `PostgreSQLSource`
- `MySQLSource`

These sources now support three layers of behavior:

1. explicit query loading
2. schema discovery
3. deterministic relational access planning and materialization

## Core Boundary

Relational source behavior does **not** change the core contracts.

The core still works with:

- `Dataset`
- `AnalysisPlan`
- `AnalysisResult`

That means relational logic stays in `src/saida/sources/` and prompt/frontend orchestration, not in the compute core.

## Schema Discovery

SQL-backed sources can introspect a database with SQLAlchemy and normalize it into a canonical relational schema model.

Main source-side model types:

- `RelationalSchemaModel`
- `RelationalTableModel`
- `RelationalColumnModel`
- `RelationalRelationshipModel`

Example:

```python
from saida.sources import SQLiteSource

source = SQLiteSource(
    "warehouse.sqlite",
    'SELECT * FROM "orders"',
    name="warehouse_sales",
)

schema = source.discover_schema()
print([table.name for table in schema.tables])
print([relationship.name for relationship in schema.relationships])
```

## Deterministic Access Planning

SQL-backed sources can convert required relational fields into a deterministic source-side access plan.

Main access-plan types:

- `RelationalAccessPlan`
- `RelationalProjectionSpec`
- `RelationalJoinSpec`

Example:

```python
plan = source.plan_access(
    required_columns=["order_id", "country", "total_sales"],
    preferred_base_table="orders",
)

print(plan.base_table)
print(plan.required_tables)
print(plan.joins)
```

The access planner currently handles:

- deterministic base-table choice
- shortest foreign-key join paths
- required projection selection
- ambiguity rejection for duplicate column names

## Query Rendering And Materialization

Once a relational access plan exists, the source can synthesize SQL and materialize a normal `Dataset`.

Example:

```python
dataset = source.load_from_access_plan(plan)

print(dataset.name)
print(dataset.metadata["materialization_mode"])
print(dataset.metadata["generated_query"])
```

Convenience helper:

```python
dataset = source.load_for_columns(
    required_columns=["order_id", "country", "total_sales"],
    preferred_base_table="orders",
)
```

## Prompt Frontend Integration

`PromptAnalysisFrontend` now supports source-aware prompt execution for relational SQL sources.

Use:

- `prepare_source_analysis(...)`
- `plan_source(...)`
- `analyze_source(...)`

Example:

```python
from saida import PromptAnalysisFrontend
from saida.sources import SQLiteSource

source = SQLiteSource(
    "warehouse.sqlite",
    'SELECT * FROM "orders"',
    name="warehouse_sales",
)

frontend = PromptAnalysisFrontend()
result = frontend.analyze_source(source, "Show a table of total_sales by country")
```

That flow is:

1. discover relational schema
2. build a planning-time schema dataset
3. normalize the prompt
4. derive a source materialization request
5. build a relational access plan
6. render and execute SQL
7. hand the resulting `Dataset` to the unchanged core runtime

## CLI Entry Point

The CLI now exposes a source-aware SQLite command:

```powershell
python -m saida.cli.main analyze-sqlite `
  --database path/to/warehouse.sqlite `
  --table orders `
  --question "Show a table of total_sales by country" `
  --json
```

`--table` defines the base table exposed to the source-aware planning flow. SAIDA can still join to related tables as needed during materialization.

## Debug Provenance

Source-aware prompt runs now include debug-only provenance in `to_debug_response_dict()`:

- `execution.source_provenance`
- `meta.source_provenance`

That provenance includes:

- source name and type
- planning mode
- materialization mode
- required columns
- required tables
- base table
- joins used
- generated SQL
- clarification details when source materialization could not be resolved safely

## Current Limitations

Current relational materialization is strongest for:

- deterministic column projection
- straightforward foreign-key joins
- prompt-driven grouped and retrieval workflows

It does not yet automatically handle every complex warehouse scenario, including:

- highly ambiguous schemas without clarification
- advanced pushdown of every filter/aggregation shape
- semantic join discovery beyond the canonical FK graph

## Related Docs

- [Architecture](../overview/architecture.md)
- [API Usage](./api-usage.md)
- [AnalysisPlan API Reference](./analysis-plan-api.md)
