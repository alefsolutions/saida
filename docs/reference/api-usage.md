# SAIDA API Usage

This page shows the practical Python surface for using SAIDA in an application.

If you want the system design first, see [Architecture](../overview/architecture.md).

## Main Imports

Core framework:

```python
from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanStep
from saida.sources import CSVSource
```

Optional frontend:

```python
from saida import PromptAnalysisFrontend
```

## Recommended Core Workflow

1. load a dataset
2. create or receive an `AnalysisPlan`
3. execute it with `Saida.execute_plan(...)`
4. use the returned `AnalysisResult`

Example:

```python
from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanStep
from saida.sources import CSVSource

dataset = CSVSource("examples/datasets/support_tickets_500.csv").load()

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
```

## Core Methods

### `Saida().execute_plan(dataset, plan)`

Primary framework API.

Use this when you already have an authored or generated `AnalysisPlan`.

It:

- profiles the dataset
- validates the plan
- routes each step to the right compute adapter
- returns a canonical `AnalysisResult`

### `Saida().profile(dataset)`

Returns a deterministic `DatasetProfile`.

Use it to inspect:

- measures
- dimensions
- time columns
- identifier candidates
- dataset warnings

### `Saida().render_output(result, output_format="json", adapter=None)`

Renders an `AnalysisResult` through an output adapter.

Built-in formats:

- `json`
- `summary`

### `Saida().load_context(markdown)`

Parses markdown into a canonical `SourceContext`.

Useful for:

- metric definitions
- business rules
- trusted date fields
- caveats

### `Saida().capabilities()`

Returns a runtime capability snapshot.

Useful for:

- feature checks
- tests
- integration diagnostics

## Source Loading Examples

### CSV

```python
from saida.sources import CSVSource

dataset = CSVSource("examples/datasets/support_tickets_500.csv").load()
```

### pandas

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

### SQL

```python
from saida.sources import PostgreSQLSource

dataset = PostgreSQLSource(
    uri="postgresql+psycopg://user:pass@host:5432/dbname",
    query="select * from public.sales",
    name="sales",
).load()
```

## Working With `AnalysisResult`

The main fields most application code uses are:

- `summary`
- `deterministic_summary`
- `llm_summary`
- `metrics`
- `tables`
- `warnings`
- `plan`
- `trace`
- `response`

Typical access patterns:

```python
payload = result.to_response_dict()
print(payload["result"]["name"])
print(payload["result"]["value"])
print(payload["execution"]["plan_id"])
```

```python
for table in result.tables:
    print(table.name)
    print(table.dataframe.head())
```

## Optional Prompt Frontend

If you want SAIDA to generate a plan from a prompt, use `PromptAnalysisFrontend`.

### Build a plan from a prompt

```python
from saida import PromptAnalysisFrontend

frontend = PromptAnalysisFrontend()
plan = frontend.plan(dataset, "How many tickets do we have by team?")
```

### Analyze from a prompt

```python
from saida import PromptAnalysisFrontend

frontend = PromptAnalysisFrontend()
result = frontend.analyze(dataset, "How many tickets do we have by team?")
```

This path is optional. The framework itself is still centered on authored or generated `AnalysisPlan` execution.

## Reserved APIs

These surfaces still exist, but they are not the main stable feature area today:

- `train(...)`
- `predict(...)`
- `forecast(...)`
