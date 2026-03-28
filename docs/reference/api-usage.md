![SAIDA Banner](assets/github-banner.png)

# SAIDA API Usage

This document describes the live public Python surface in SAIDA.

If you want the system design, see [architecture.md](../overview/architecture.md).

## Main Entry Point

```python
from saida import Saida
```

The most important public methods are:

- `execute_plan(dataset, plan)`
- `profile(dataset)`
- `render_output(result, output_format="json", adapter=None)`
- `load_context(markdown)`
- `capabilities()`

Optional frontend helpers:

- `plan(dataset, question)`
- `analyze(dataset, question)`

## Recommended Core Workflow

The recommended framework-first workflow is:

1. load a dataset
2. create or receive an `AnalysisPlan`
3. execute it with `execute_plan`
4. use the standardized `AnalysisResult`

This is the primary framework path.

If you use prompt or LLM features, treat them as optional plan-generation utilities that sit before this path.

### Execute An Authored Plan

```python
from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanStep
from saida.sources import CSVSource

dataset = CSVSource(
    "examples/datasets/support_tickets_500.csv",
    context_path="examples/contexts/support_tickets_500.md",
).load()

plan = AnalysisPlan(
    task_type="descriptive",
    rationale="Count tickets by team.",
    expected_result_name="group_row_counts",
    expected_result_shape="table",
    steps=[
        PlanStep(
            step_id="count_rows_by_group",
            tool_family="duckdb",
            action="count_rows_by_group",
            method_id="count_rows_by_group",
            family="aggregation_grouping",
            parameters={"group_by": ["team"]},
            description="Count tickets by team.",
        )
    ],
)

engine = Saida()
result = engine.execute_plan(dataset, plan)

print(result.response["result"]["name"])
print(result.response["result"]["value"])
```

## Optional Prompt Workflow

If you want a prompt frontend, SAIDA still supports it.

But this is a convenience layer, not the framework source of truth.

### Build A Plan From A Prompt

```python
from saida import PromptAnalysisFrontend

engine = PromptAnalysisFrontend()
plan = engine.plan(dataset, "How many tickets do we have by team?")

print(plan.plan_id)
print(plan.expected_result_name)
for step in plan.steps:
    print(step.step_id, step.tool_family, step.method_id, step.parameters)
```

### Analyze From A Prompt

```python
from saida import PromptAnalysisFrontend

engine = PromptAnalysisFrontend()
result = engine.analyze(dataset, "How many tickets do we have by team?")

print(result.summary)
print(result.response["interpretation"]["prompt_family"])
print(result.response["execution"]["plan_id"])
```

`analyze()` is still useful, but it is best understood as a convenience path that sits on top of the plan-first core.

## Public Methods

### `Saida().execute_plan(dataset, plan)`

Core execution API.

Use this when you already have a valid `AnalysisPlan`.

This is the primary SAIDA framework API.

What it does:

- validates the dataset
- profiles the dataset
- validates the plan against dataset/profile/backend context
- executes plan steps
- returns a canonical `AnalysisResult`

### `PromptAnalysisFrontend().plan(dataset, question)`

Optional frontend helper.

Use this when you want SAIDA to generate a candidate `AnalysisPlan` from a prompt without executing it yet.

### `PromptAnalysisFrontend().analyze(dataset, question)`

Optional end-to-end convenience method.

Use this when you want:

- prompt interpretation
- plan generation
- validation
- execution
- final result

in one call.

### `Saida().profile(dataset)`

Returns a deterministic `DatasetProfile`.

Typical uses:

- inspect schema
- inspect measures and dimensions
- inspect time columns
- inspect identifier columns
- inspect warnings before planning

### `Saida().render_output(result, output_format="json", adapter=None)`

Renders an `AnalysisResult` through an output adapter.

Built-in formats:

- `json`
- `summary`

Example:

```python
json_payload = engine.render_output(result, output_format="json")
summary_text = engine.render_output(result, output_format="summary")
```

### `Saida().load_context(markdown)`

Parses markdown into a canonical `SourceContext`.

Use it when you want to attach:

- metric definitions
- business rules
- trusted time fields
- dataset caveats

### `Saida().capabilities()`

Returns the current public capability surface.

This is useful for:

- adapter-aware integration checks
- UI capability checks
- testing what is enabled in a given runtime

## Loading Data

SAIDA currently ships source loaders for:

- CSV
- Excel
- JSON
- pandas
- SQL

### CSV Example

```python
from saida.sources import CSVSource

dataset = CSVSource("examples/datasets/support_tickets_500.csv").load()
```

### pandas Example

```python
import pandas as pd

from saida.sources import PandasSource

df = pd.DataFrame(
    {
        "posted_at": ["2026-01-01", "2026-02-01", "2026-03-01"],
        "revenue": [100.0, 120.0, 80.0],
        "region": ["West", "West", "East"],
    }
)

dataset = PandasSource(df, name="sales").load()
```

### SQL Example

```python
from saida.sources import PostgreSQLSource

dataset = PostgreSQLSource(
    uri="postgresql+psycopg://user:pass@host:5432/dbname",
    query="select * from public.sales",
    name="sales",
).load()
```

## What `AnalysisResult` Gives You

The object returned by `execute_plan()` and `analyze()` includes:

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

Most application code will use:

- `result.response`
- or `result.to_response_dict()`

## Response Envelope

The live response schema is:

- `saida.response.v2`

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

### Common Access Patterns

#### Primary scalar

```python
payload = result.to_response_dict()
print(payload["result"]["name"])
print(payload["result"]["value"])
```

#### Supporting tables

```python
for table in result.tables:
    print(table.name)
    print(table.dataframe.head())
```

#### Executed plan

```python
for step in result.plan.steps:
    print(step.step_id, step.tool_family, step.method_id, step.parameters)
```

#### Execution metadata

```python
payload = result.to_response_dict()
print(payload["execution"]["plan_id"])
print(payload["execution"]["expected_result_shape"])
```

## Reserved APIs

These methods exist, but they are not the main stable feature area today:

- `train(dataset, target, problem_type="regression", feature_columns=None)`
- `predict(dataset, artifact_path)`
- `forecast(dataset, target, horizon=3)`

Treat them as reserved ML-facing API surface for now.
