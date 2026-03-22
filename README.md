![SAIDA Banner](assets/github-banner.png)

# SAIDA

[![Version](https://img.shields.io/badge/version-0.2.0-1f6feb)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-2ea043)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)](pyproject.toml)

SAIDA is a developer-facing analytics framework that turns natural-language requests into:

- deterministic analysis workflows
- canonical result objects
- stable JSON response payloads

In plain terms:

- you give SAIDA a dataset and a question
- SAIDA figures out what analysis is being requested
- SAIDA runs the right deterministic workflow
- SAIDA gives you a structured result you can use in apps, APIs, UIs, and playgrounds

## What SAIDA Is

SAIDA is not just a prompt wrapper around an LLM.

It is a contract-first analytics engine that sits between:

- natural language
- dataset understanding
- deterministic planning
- compute backends
- standardized outputs

That means SAIDA is designed to help developers build systems where prompts can be useful without letting prompt interpretation become uncontrolled or opaque.

## What The Goal Is

The goal of SAIDA is to make prompt-driven analytics reliable enough to build on.

More specifically, SAIDA aims to give developers:

- a stable way to convert prompts into analysis workflows
- a predictable JSON result contract
- safer clarification and refusal behavior when a prompt is ambiguous
- reproducible routing so paraphrases converge to the same plan
- portability across datasets, APIs, playgrounds, and future backends

The core idea is:

- prompts are user input
- SAIDA defines the meaning
- deterministic compute produces the truth

## How SAIDA Works

At a high level, SAIDA works like this:

1. **Load and profile the dataset**
   SAIDA inspects rows, columns, measures, dimensions, time fields, identifiers, nulls, and cardinality.

2. **Normalize the prompt**
   SAIDA converts the raw prompt into a structured `AnalysisRequest`.

3. **Derive a prompt family**
   SAIDA maps the request into a supported prompt family such as:
   - `metric_aggregate`
   - `column_inventory`
   - `column_type_lookup`
   - `tabular_record_retrieval`
   - `grouped_entity_count`
   - `distinct_value_count`
   - `time_bucket_counts`
   - `row_existence_check`

4. **Build a prompt capability contract**
   SAIDA validates whether the request is supported, feasible, ambiguous, or should clarify/refuse.

5. **Compile a deterministic `AnalysisPlan`**
   SAIDA creates executable plan steps for the chosen workflow.

6. **Run the plan on compute backends**
   Today that mainly means deterministic pandas/DuckDB/stats-style execution.

7. **Canonicalize the output**
   SAIDA returns a stable `AnalysisResult` plus a portable JSON envelope: `saida.response.v2`.

In one line:

- `prompt -> request -> prompt family -> capability contract -> analysis plan -> execution -> canonical result`

## What You Get Back

The main top-level Python object is `AnalysisResult`.

That result includes:

- `summary`
- `metrics`
- `tables`
- `warnings`
- `plan`
- `trace`
- `artifacts`
- `response`

The portable JSON response includes:

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

This makes SAIDA useful for:

- backend services
- internal analytics tools
- web UIs
- chat or copilot experiences
- testing and regression suites

## What SAIDA Supports Today

The current `0.2.0` surface already supports a broad deterministic set of prompt families, including:

- schema and metadata inventory
  - list columns
  - list numeric/categorical/time/identifier/high-cardinality columns
  - show column types

- metadata counts
  - count columns
  - count measure columns
  - count dimension columns
  - count time columns
  - count identifier columns
  - count high-cardinality columns

- scalar metric analysis
  - sum, mean, min, max, count

- grouped analysis
  - counts by group
  - metric totals by group
  - grouped tables

- tabular retrieval
  - rows
  - selected columns
  - sorting
  - pagination
  - filtered record retrieval

- distinct value workflows
  - list distinct values
  - count distinct values

- verification workflows
  - column presence
  - column properties
  - null checks
  - threshold checks
  - filtered row existence
  - time-value existence

- ranking workflows
  - most/least represented group
  - top rows
  - top groups

- time-oriented analysis
  - date coverage
  - counts by month/quarter/year
  - time-bucket metric breakdowns
  - adjacent period comparison

- statistical workflows
  - t-test
  - ANOVA
  - Mann-Whitney
  - chi-square
  - confidence interval
  - power analysis
  - sample size estimate
  - regression significance

It also supports:

- safe clarification when the prompt is ambiguous
- safe refusal when the request references missing or invalid dataset concepts
- optional LLM-assisted prompting and response reasoning

## What Is Not Implemented Yet

These public APIs exist, but are not implemented yet:

- `train`
- `predict`
- `forecast`

So SAIDA is currently strongest as a prompt-to-analysis framework, not yet as a full predictive or forecasting platform.

## Quick Start

### Install

```bash
pip install -e .
```

### Analyze A CSV Dataset

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
print(result.response["interpretation"]["prompt_family"])
```

### Analyze A Pandas DataFrame

```python
import pandas as pd

from saida import Saida
from saida.sources import PandasSource

df = pd.DataFrame(
    {
        "posted_at": ["2026-01-01", "2026-02-01", "2026-03-01"],
        "revenue": [100.0, 120.0, 80.0],
        "region": ["West", "West", "East"],
    }
)

dataset = PandasSource(df, name="sales").load()
engine = Saida()

result = engine.analyze(dataset, "Show revenue by month")

print(result.summary)
print([table.name for table in result.tables])
print(result.to_response_dict()["status"])
```

### Use Optional LLM Prompting And Reasoning

```python
from saida import Saida
from saida.config import LlmConfig, SaidaConfig

engine = Saida(
    config=SaidaConfig(
        llm=LlmConfig(
            enabled=True,
            provider="openai",
            model="gpt-4.1-mini",
            use_for_prompting=True,
            use_for_reasoning=True,
        )
    )
)
```

Important:

- LLMs in SAIDA are optional
- LLMs do not perform the compute
- deterministic execution still owns the analysis truth

## Real-World Developer Use Cases

### 1. Build An Analytics API

You want users to ask questions like:

- `What are the columns in this dataset?`
- `How many unique channels are there?`
- `Show total revenue by region`

SAIDA gives you:

- normalized prompt handling
- deterministic execution
- a stable JSON envelope for your API response

### 2. Build A Support-Ops Copilot

You have support data and want prompts like:

- `Which channel has the most tickets?`
- `How many tickets were created by quarter?`
- `Does csat_score have missing values?`
- `Show resolution_hours by priority and product_area`

SAIDA gives you:

- prompt routing
- safe clarification for ambiguous requests
- structured tables and scalar results

### 3. Build A Dataset QA Or Metadata Assistant

You want prompts like:

- `What are the data types of each field?`
- `How many columns are in the dataset?`
- `Which columns are numeric?`
- `Is created_at a datetime field?`

SAIDA gives you:

- schema-aware interpretation
- canonical metadata results
- consistent verification outputs

### 4. Standardize Analytics Across Different Interfaces

You want the same engine to power:

- a CLI
- a web API
- an internal admin UI
- a playground

SAIDA gives you:

- the same deterministic engine
- the same response contract
- the same prompt-family routing

## Example Prompts

Here are a few examples that map cleanly to current workflows:

- `What are the columns in the dataset?`
- `How many columns are in the dataset?`
- `What is the data type of created_at?`
- `How many unique team values are there?`
- `Give me the total tickets per channel.`
- `Which channel has the most tickets?`
- `Show all rows.`
- `Show ticket_id and priority rows sorted by created_at.`
- `How many tickets were created by quarter?`
- `Compare revenue this quarter to last quarter.`
- `Does csat_score have missing values?`
- `Are any resolution_hours above 20?`

## CLI

SAIDA includes a simple CLI:

```bash
saida profile --csv examples/datasets/support_tickets_500.csv --json
saida analyze --csv examples/datasets/support_tickets_500.csv --question "How many columns are in the dataset?" --json
```

## Documentation Map

If you want the deeper design details, use:

- [Architecture](ARCHITECTURE.md)
- [Prompt Family Catalog](PROMPT_FAMILY_CATALOG.md)
- [Prompt Capability Architecture Note](PROMPT_CAPABILITY_ARCHITECTURE_NOTE.md)
- [Schema Spec](SCHEMA_SPEC.md)
- [Planned API Usage](API_USAGE.md)
- [File Structure](FILE_STRUCTURE.md)
- [Coding Guidelines](CODING_GUIDELINES.md)
- [Changelog](CHANGELOG.md)

## Bottom Line

SAIDA exists to help developers build prompt-driven analytics systems that are:

- more deterministic than a pure chat wrapper
- more structured than ad hoc data-question code
- easier to test
- easier to extend
- safer to integrate into real products

If you want prompts to result in real analytical workflows and real structured results, that is the point of SAIDA.
