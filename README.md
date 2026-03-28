![SAIDA Banner](assets/github-banner.png)

# SAIDA

[![Version](https://img.shields.io/badge/version-0.2.0-1f6feb)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-2ea043)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)](pyproject.toml)

SAIDA is a developer-facing analytics framework for:

- canonical `AnalysisPlan` execution
- deterministic data analysis jobs
- standardized `AnalysisResult` output

I built SAIDA to make BI dashboarding and day-to-day data analysis easier, faster, and less repetitive.

The core idea is simple:

- you define or generate an `AnalysisPlan`
- SAIDA validates it
- SAIDA executes it through built-in adapters
- SAIDA returns a stable result contract you can use in apps, APIs, dashboards, and output pipelines

Natural language and LLMs can still help, but they are now optional frontend utilities. They are not the compute layer, and they are not the core identity of SAIDA.

## What SAIDA Is

SAIDA is a contract-first analytics framework with a deterministic execution engine inside it.

Its main job is to standardize:

- how data comes in
- how analysis work is described
- how that work is validated and executed
- how results come out

The center of the framework is:

- `Dataset`
- `AnalysisPlan`
- `PlanValidator`
- compute adapters
- `AnalysisResult`

If you strip everything else away, the framework's core runtime is:

- `Dataset`
- `AnalysisPlan`
- validation
- execution
- `AnalysisResult`

## What The Goal Is

The goal of SAIDA is to make analytics execution reproducible and portable.

That means:

- the same `AnalysisPlan` and the same dataset should produce the same `AnalysisResult`
- compute should stay deterministic
- results should have a stable shape for downstream systems
- backends should be replaceable without changing SAIDA's core contracts

This makes SAIDA a good fit for:

- BI dashboards
- internal analytics tools
- reporting APIs
- app features that need structured analytics output
- testing and regression workflows around analytics jobs

## How SAIDA Works

The core runtime flow is:

- `Source -> Dataset -> AnalysisPlan -> Validate -> Execute -> AnalysisResult -> OutputAdapter`

Optional frontend flow:

- `Natural language -> AnalysisPlanGenerator -> candidate AnalysisPlan -> Validate -> Execute -> AnalysisResult`

In plain English:

1. Load data through a source adapter.
2. Profile the dataset.
3. Provide a canonical `AnalysisPlan` directly, or generate one through an optional frontend layer.
4. Validate the plan against the dataset and analytics registry.
5. Execute plan steps through compute adapters.
6. Return a standardized `AnalysisResult`.
7. Render the result through JSON, summary, or future output adapters.

## Core Concepts

### `Dataset`

The canonical input after loading from a source adapter.

Examples:

- CSV
- Excel
- JSON
- pandas
- SQL-backed sources

### `AnalysisPlan`

The executable contract.

An `AnalysisPlan` describes:

- input references
- ordered steps
- method ids
- dependencies
- expected result shape

It represents what should be executed, not how to hand-code the analysis.

### `AnalysisResult`

The canonical output.

It contains:

- primary result
- supporting tables
- warnings
- execution metadata
- stable JSON payloads

### Analytics Families

SAIDA organizes supported analytics into canonical families and methods, such as:

- projection / field selection
- aggregation / grouping
- ranking
- validation / verification
- schema / metadata inspection
- distinct / cardinality analysis
- time-series / time bucketing
- period comparison
- statistical inference
- diagnostic workflows

## Built-In Interfaces

SAIDA already has formal interfaces and built-in defaults for the main framework layers.

### Source interfaces

Built-in source adapters include:

- `CSVSource`
- `ExcelSource`
- `JSONSource`
- `PandasSource`
- SQL sources such as:
  - `SQLiteSource`
  - `PostgreSQLSource`
  - `MySQLSource`

### Compute interfaces

Built-in compute adapters include:

- `DuckDBAdapter`
- `MetadataComputeAdapter`
- `StatsModelsAdapter`
- `MlAdapter` for reserved ML-facing surface

DuckDB, metadata-backed execution, and statsmodels-backed execution are the default built-ins. They are replaceable, but they are not the architecture itself.

### Output interfaces

Built-in output adapters include:

- `JsonOutputAdapter`
- `SummaryOutputAdapter`

The canonical result remains `AnalysisResult`. Output adapters transform that result into delivery formats.

## Quick Start

### 1. Load A Dataset

```python
from saida.sources import CSVSource

dataset = CSVSource(
    "examples/datasets/support_tickets_500.csv",
    context_path="examples/contexts/support_tickets_500.md",
).load()
```

### 2. Execute An Authored Plan

```python
from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanStep

engine = Saida()

plan = AnalysisPlan(
    task_type="descriptive",
    rationale="Count support tickets by team.",
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

### 3. Use Optional Prompt-to-Plan Generation

```python
from saida import PromptAnalysisFrontend

engine = PromptAnalysisFrontend()
result = engine.analyze(dataset, "How many tickets do we have by team?")

print(result.summary)
print(result.response["execution"]["plan_id"])
print(result.response["interpretation"]["prompt_family"])
```

### 4. Render Through Output Adapters

```python
json_payload = engine.render_output(result, output_format="json")
summary_text = engine.render_output(result, output_format="summary")

print(json_payload["result"])
print(summary_text)
```

## Real Developer Use Cases

### BI dashboard metric cards

Use a plan that returns:

- row counts
- totals
- averages
- distinct counts

Then feed the `AnalysisResult` JSON directly into your dashboard layer.

### Grouped tables for reporting

Use grouped count or grouped aggregate plans to return standardized tables for team, country, region, product, or priority breakdowns.

### Verification checks

Use verification plans for:

- threshold checks
- null checks
- time-value existence
- schema checks

This is useful for operational monitoring and data-quality workflows.

### Statistical analysis endpoints

Use inferential plans such as:

- `t_test`
- `anova`
- `chi_square`
- `confidence_interval`

and keep the response contract stable for application code.

## What Is Optional

Prompt interpretation and LLM support are optional.

If used, they should:

- generate candidate plans
- follow strict contracts
- pass validation before execution

They should never bypass the validator or become the compute layer.

## What Is Not Implemented Yet

These public APIs exist but are still reserved surfaces:

- `train`
- `predict`
- `forecast`

So today SAIDA is strongest as a deterministic analytics planning and execution framework, not yet a full predictive platform.

## More Docs

- [Docs Index](./docs/README.md)
- [Architecture](./docs/overview/architecture.md)
- [API Usage](./docs/reference/api-usage.md)
- [Schema Spec](./docs/reference/schema-spec.md)
- [Prompt Family Catalog](./docs/reference/prompt-family-catalog.md)
- [Prompt Playbook](./docs/guides/prompt-playbook.md)
