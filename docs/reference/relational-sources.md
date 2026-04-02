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
- `RelationalFilterSpec`
- `RelationalOrderSpec`

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
- semantic table-role inference (`fact`, `dimension`, `bridge`, `view`)
- required projection selection
- ambiguity rejection for duplicate column names
- bound source-side filters
- bound source-side ordering
- row-window limits for record retrieval flows

Example with pushdown:

```python
plan = source.plan_access(
    required_columns=["order_id", "country", "order_date", "total_sales"],
    preferred_base_table="orders",
    filters={"total_sales": {"op": "gt", "value": 90.0}},
    sort_by="order_date",
    sort_direction="desc",
    limit=5,
)

print(plan.filters)
print(plan.order_by)
print(plan.limit)
```

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

The same helper also accepts safe pushdown parameters:

```python
dataset = source.load_for_columns(
    required_columns=["order_id", "country", "order_date", "total_sales"],
    preferred_base_table="orders",
    filters={"total_sales": {"op": "gt", "value": 90.0}},
    sort_by="order_date",
    sort_direction="desc",
    limit=5,
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
from saida.sources import PostgreSQLSource

source = PostgreSQLSource(
    "postgresql+psycopg://user:pass@host:5432/warehouse",
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

When clarification is required, debug provenance now also includes richer hints such as:

- candidate tables
- suggested qualified fields
- candidate connected join paths when available
- similar column suggestions for unknown fields

Example clarification payload excerpt:

```json
{
  "reason": "ambiguous_relational_column",
  "candidate_tables": ["customers", "shipments"],
  "suggested_qualified_fields": ["customers.country", "shipments.country"]
}
```

## Direct Authored Plans Against Source-Materialized Datasets

Relational source intelligence stays outside the core, so the direct `AnalysisPlan` path still works cleanly.

Example:

```python
from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec
from saida.sources import SQLiteSource

source = SQLiteSource(
    "warehouse.sqlite",
    'SELECT * FROM "orders"',
    name="warehouse_sales",
)

dataset = source.load_for_columns(
    required_columns=["country", "total_sales"],
    preferred_base_table="orders",
)

plan = AnalysisPlan(
    task_type="descriptive",
    rationale="Aggregate materialized relational sales by country.",
    inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
    expected_result_name="grouped_totals",
    expected_result_shape="table",
    final_output_ref="grouped_totals",
    steps=[
        PlanStep(
            step_id="grouped_totals",
            tool_family="duckdb",
            action="aggregate_frame",
            method_id="aggregate_frame",
            family="transformation",
            parameters={"target": "total_sales", "aggregation": "sum", "group_by": ["country"]},
            description="Aggregate sales totals by country.",
            inputs=[
                StepInputRef(
                    input_id="dataset_input",
                    source_type="plan_input",
                    ref="primary_dataset",
                    expected_kind="dataset",
                )
            ],
            output_refs=["grouped_totals"],
            outputs=[
                StepOutputSpec(
                    output_id="grouped_totals",
                    kind="frame",
                    logical_shape="table",
                    physical_shape="recordset",
                )
            ],
        )
    ],
)

result = Saida().execute_plan(dataset, plan)
```

## Richer Examples

The repo now includes a richer relational playground scenario:

- [`playground/example4/run/run_prompt_analysis.py`](../../playground/example4/run/run_prompt_analysis.py)

That example uses a multi-table warehouse schema:

- `customers`
- `products`
- `orders`
- `order_items`

and is a good place to try prompts like:

- `Show a table of total_sales by country`
- `Show a table of line_total by product_category`
- `Show the latest 2 rows`

## Current Limitations

Current relational materialization is strongest for:

- deterministic column projection
- straightforward foreign-key joins
- prompt-driven grouped and retrieval workflows
- source-aware record retrieval with safe filter/order/limit pushdown

It does not yet automatically handle every complex warehouse scenario, including:

- highly ambiguous schemas without clarification
- advanced pushdown of every filter/aggregation shape
- semantic join discovery beyond the canonical FK graph

## Related Docs

- [Architecture](../overview/architecture.md)
- [API Usage](./api-usage.md)
- [AnalysisPlan API Reference](./analysis-plan-api.md)
