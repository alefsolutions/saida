# SAIDA API Usage

This page shows the practical Python surface for using SAIDA in an application.

If you want the system design first, see [Architecture](../overview/architecture.md).

## Main Imports

Core framework:

```python
from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec
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
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec
from saida.sources import CSVSource

dataset = CSVSource("examples/datasets/support_tickets_500.csv").load()

plan = AnalysisPlan(
    task_type="descriptive",
    rationale="Count tickets by team.",
    inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset.name)],
    expected_result_name="group_row_counts",
    expected_result_shape="table",
    final_output_ref="group_row_counts",
    steps=[
        PlanStep(
            step_id="count_rows_by_group",
            tool_family="duckdb",
            action="count_rows_by_group",
            method_id="count_rows_by_group",
            family="aggregation_grouping",
            parameters={"group_by": ["team"]},
            description="Count tickets by team.",
            inputs=[
                StepInputRef(
                    input_id="dataset_input",
                    source_type="plan_input",
                    ref="primary_dataset",
                    expected_kind="dataset",
                )
            ],
            output_refs=["group_row_counts"],
            outputs=[
                StepOutputSpec(
                    output_id="group_row_counts",
                    kind="frame",
                    logical_shape="table",
                    physical_shape="recordset",
                )
            ],
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
- resolves plan inputs and step-output refs
- routes each step through the deterministic DAG scheduler
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
print(payload["execution"]["final_output_ref"])
print(payload["execution"]["plan"].get("metadata", {}).get("graph_template_id"))
```

```python
for table in result.tables:
    print(table.name)
    print(table.dataframe.head())
```

```python
for node_result in result.node_results:
    print(node_result.step_id, node_result.produced_outputs)

print(result.artifact_index.keys())
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

Prompt-generated plans now use the same DAG-ready plan contract as authored plans, so you can inspect `plan.inputs`, `plan.steps[*].inputs`, `plan.steps[*].outputs`, and `plan.final_output_ref` before execution.

## Reserved APIs

These surfaces still exist, but they are not the main stable feature area today:

- `train(...)`
- `predict(...)`
- `forecast(...)`
