![SAIDA Banner](assets/github-banner.png)

# SAIDA

[![Version](https://img.shields.io/badge/version-0.3.0-1f6feb)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-2ea043)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)](pyproject.toml)

SAIDA is a Python framework for deterministic data analysis.

Its core contract is simple:

- input: `AnalysisPlan`
- output: `AnalysisResult`

I built SAIDA to make BI dashboarding and day-to-day analysis easier to automate, easier to test, and easier to plug into apps.

## What You Get

- canonical `AnalysisPlan` execution
- deterministic validation before compute
- standardized `AnalysisResult` output
- pluggable source, compute, and output adapters
- optional prompt and LLM helpers that sit on top of the core

The main runtime flow is:

- `Dataset -> AnalysisPlan -> Validate -> Execute -> AnalysisResult`

## Quick Start

### 1. Load a dataset

```python
from saida.sources import CSVSource

dataset = CSVSource(
    "examples/datasets/support_tickets_500.csv",
    context_path="examples/contexts/support_tickets_500.md",
).load()
```

### 2. Execute an authored plan

```python
from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanStep

engine = Saida()

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

result = engine.execute_plan(dataset, plan)

print(result.response["result"]["name"])
print(result.response["result"]["value"])
```

### 3. Render the result

```python
json_payload = engine.render_output(result, output_format="json")
summary_text = engine.render_output(result, output_format="summary")
```

## Optional Prompt Frontend

Prompt handling is supported, but it is optional.

If you want prompt-to-plan generation:

```python
from saida import PromptAnalysisFrontend

frontend = PromptAnalysisFrontend()
plan = frontend.plan(dataset, "How many tickets do we have by team?")
result = frontend.analyze(dataset, "How many tickets do we have by team?")
```

Prompt and LLM features are not the compute layer. They are convenience tooling that generates candidate plans or optional summaries.

## Built-In Interfaces

### Sources

- CSV
- Excel
- JSON
- pandas
- SQL sources such as SQLite, PostgreSQL, and MySQL

### Compute

- DuckDB
- metadata/profile-backed execution
- statsmodels-backed execution

### Output

- JSON
- summary text

## Current Scope

SAIDA is strongest today as a framework for:

- aggregation and grouping
- tabular retrieval
- ranking
- verification checks
- schema and metadata inspection
- distinct value analysis
- time-based analysis
- period comparison
- statistical inference
- diagnostic workflows

Reserved ML-facing APIs still exist, but forecasting and model training are not the main stable feature area yet.

## Read Next

- [Docs Index](./docs/README.md)
- [AnalysisPlan API Reference](./docs/reference/analysis-plan-api.md)
- [Architecture](./docs/overview/architecture.md)
- [API Usage](./docs/reference/api-usage.md)
- [Schema Spec](./docs/reference/schema-spec.md)
- [Prompt Playbook](./docs/guides/prompt-playbook.md)
- [Prompt Family Catalog](./docs/reference/prompt-family-catalog.md)
