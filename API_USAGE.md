![SAIDA Banner](assets/github-banner.png)

# SAIDA API Usage

This document describes the live public Python surface in the current SAIDA codebase.

If you want the high-level system design, see [ARCHITECTURE.md](./ARCHITECTURE.md).

## Main Entry Point

The main public object is:

```python
from saida import Saida
```

The live primary workflow is:

```python
result = Saida().analyze(dataset, question)
```

## Public Methods

### `Saida().analyze(dataset, question)`

Runs the full prompt-to-analysis workflow and returns an `AnalysisResult`.

Use this for:

- prompt-driven analytics
- schema questions
- grouped summaries
- tabular retrieval
- verification checks
- time-oriented analysis
- statistical workflows

### `Saida().profile(dataset)`

Returns a deterministic `DatasetProfile`.

Use this when you want to inspect:

- row count
- column count
- measure columns
- dimension columns
- time columns
- identifier columns
- profile warnings

### `Saida().capabilities()`

Returns the currently available public capabilities.

Typical use:

```python
engine = Saida()
print(engine.capabilities())
```

This reports whether prompt analysis, context loading, prompt capability contracts, optional LLM use, and reserved ML APIs are available.

### `Saida().load_context(markdown)`

Parses a markdown context file into a `SourceContext`.

Use this when you want to attach business definitions, caveats, trusted date fields, identifiers, or freshness notes to a dataset.

### Reserved APIs

These methods exist, but they are not the current core product surface:

- `train(dataset, target, problem_type="regression", feature_columns=None)`
- `predict(dataset, artifact_path)`
- `forecast(dataset, target, horizon=3)`

Treat them as reserved ML-facing API surface, not the main stable feature area today.

## Loading Data

SAIDA currently ships source loaders for:

- CSV
- Excel
- JSON
- pandas
- SQL

### CSV Example

```python
from saida import Saida
from saida.sources import CSVSource

dataset = CSVSource(
    "examples/datasets/support_tickets_500.csv",
    context_path="examples/contexts/support_tickets_500.md",
).load()

engine = Saida()
result = engine.analyze(dataset, "How many tickets were created by quarter?")

print(result.summary)
print(result.response["result"])
```

### pandas Example

```python
import pandas as pd

from saida import Saida
from saida.sources import PandasSource

df = pd.DataFrame(
    {
        "created_at": ["2026-01-01", "2026-02-01", "2026-03-01"],
        "revenue": [100.0, 120.0, 80.0],
        "region": ["West", "West", "East"],
    }
)

dataset = PandasSource(df, name="sales").load()
result = Saida().analyze(dataset, "Show revenue by month")

print(result.response["interpretation"]["prompt_family"])
print(result.response["tables"])
```

### JSON Example

```python
from saida import Saida
from saida.sources import JSONSource

dataset = JSONSource("examples/datasets/support_tickets_500.json").load()
result = Saida().analyze(dataset, "What are the columns in the dataset?")

print(result.response["result"]["name"])
```

## What `analyze()` Returns

`analyze()` returns an `AnalysisResult` object.

Important attributes:

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

Most application code will use either:

- `result.response`
- or `result.to_response_dict()`

## Response Envelope

The live JSON contract is `saida.response.v2`.

Top-level fields:

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

### Useful Interpretation Fields

The `interpretation` block includes the current normalized routing state:

- `prompt_family`
- `intent_name`
- `semantic_intent`
- `task_type`
- `target`
- `aggregation`
- `group_by`
- `filters`
- `time_reference`
- `options`
- `capability_contract`

Example:

```python
payload = result.to_response_dict()

print(payload["interpretation"]["prompt_family"])
print(payload["interpretation"]["semantic_intent"])
print(payload["interpretation"]["capability_contract"]["status"])
```

## Common Result Access Patterns

### Primary Scalar Result

```python
result = Saida().analyze(dataset, "How many rows are in Q1?")
payload = result.to_response_dict()

print(payload["result"]["name"])
print(payload["result"]["value"])
```

### Primary Table Result

```python
result = Saida().analyze(dataset, "What are the data types of each field?")
payload = result.to_response_dict()

print(payload["result"]["name"])
print(payload["result"]["row_count"])
print(payload["result"]["value"][:3])
```

### Inspect Supporting Tables

```python
result = Saida().analyze(dataset, "Show revenue by region")

for table in result.tables:
    print(table.name, table.dataframe.head())
```

### Inspect the Deterministic Plan

```python
result = Saida().analyze(dataset, "Count total rows in dataset for Q1")

for step in result.plan.steps:
    print(step.step_id, step.tool_family, step.action, step.parameters)
```

### Inspect Internal Artifacts

```python
result = Saida().analyze(dataset, "Count total unique team values in dataset")

print(result.artifacts["request"])
print(result.artifacts["prompt_capability_contract"])
```

## Optional LLM Usage

SAIDA can optionally use an LLM for:

- prompt interpretation
- canonical prompt condensation
- semantic operation/object proposals
- final response wording

This is configured through `SaidaConfig`.

Example:

```python
from saida import Saida
from saida.config import SaidaConfig, LlmConfig

config = SaidaConfig(
    llm=LlmConfig(
        enabled=True,
        provider="openai",
        model="gpt-5.4-mini",
        use_for_prompting=True,
        use_for_reasoning=False,
    )
)

engine = Saida(config=config)
```

Important:

- the LLM can help interpret prompts
- the LLM does not directly execute analysis
- deterministic validation still decides whether the request is safe and supported

## Live Capability Areas

The current codebase supports live prompt-driven workflows including:

- schema inventories
- metadata counts
- scalar aggregates
- grouped counts and grouped metric tables
- distinct value listing and counting
- row retrieval with sorting and pagination
- verification prompts
- ranking prompts
- time coverage, time buckets, and period comparison
- recurring and calendar-aware time filters
- several statistical workflows

## Clarify And Refuse Behavior

You should expect `status` to be one of:

- `ok`
- `clarify`
- `refuse`

This is intentional.

If SAIDA cannot safely interpret a prompt, it may clarify or refuse instead of guessing.

## Prompt Examples That Work Well

- `How many rows are in Q1?`
- `What are the columns in the dataset?`
- `What is the data type of created_at?`
- `How many unique team values are there?`
- `Give me total tickets per channel.`
- `Show ticket_id and priority rows sorted by created_at`
- `Does created_at exist as a column?`
- `Is csat_score numeric?`
- `Show all tickets created on the first Monday of every month`

## Design Guidance For Developers

When building on top of SAIDA:

- prefer reading `result.response` for app integration
- use `result.plan` and `result.artifacts` for debugging
- use `result.response["interpretation"]` when you need explainability
- treat `train`, `predict`, and `forecast` as reserved APIs for now

In practice, the stable developer surface today is:

- `Dataset`
- `Saida`
- `AnalysisResult`
- `saida.response.v2`
