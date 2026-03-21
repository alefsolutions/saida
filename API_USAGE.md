![SAIDA Banner](assets/github-banner.png)

# SAIDA Planned API Usage

This document describes the planned API usage direction for SAIDA 0.2.0.

`ARCHITECTURE.md` is the source of truth.

Important:

- this file describes the intended public API direction
- it does not guarantee that every example shown here is implemented yet
- treat it as a planning document, not the current implementation contract

## Input Modes

SAIDA should accept three primary input styles:

- prompt input
- API input
- direct JSON plan input

Examples:

```python
# Prompt style
saida.analyze(prompt="Why did revenue drop in March?")

# API payload style
saida.execute(payload)

# Direct plan style
saida.execute_plan(plan)
```

## Canonical Flow

All supported input styles should normalize into the same internal contract:

- `AnalysisPlan`

All outputs should normalize into:

- `AnalyticalResult`

That means the public surface should converge on:

- one plan model
- one result model
- many adapters and execution backends behind them

## Example API Payload

Example human-readable payload:

```json
{
  "input_type": "prompt",
  "prompt": "Show revenue by region"
}
```

Example direct-plan payload:

```json
{
  "input_type": "plan",
  "plan": {
    "task_type": "descriptive",
    "steps": [
      {
        "tool_family": "duckdb",
        "action": "group_aggregate"
      }
    ]
  }
}
```

## Example Result Shape

All results should return a canonical analytical result that includes enough structure to be interpreted without external context.

The current 0.2.0 prototype returns `saida.response.v2` with:

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

The current primary `result` object includes:

- `physical_shape`
- `logical_shape`
- `dtype`
- `schema`
- `dimensions`
- `row_count`
- `labels`
- `value`

## Output Formats

The output layer should support formatting canonical results into:

- JSON
- CSV
- Excel
- XML
- SQL

The output formatter should not redefine meaning.
It should only transform the canonical result into a delivery format.

## LLM Usage

LLMs are optional.

Allowed:

- input assistance
- plan drafting
- output wording

Not allowed:

- direct execution
- silent fact generation
- bypassing validation

## Current Prototype Note

The current 0.2.0 prototype already supports prompt-driven schema metadata requests before the planned public API surface is finalized.

Examples that work today include:

- `What are the data types of each field or column?`
- `Which columns are numeric?`
- `Which columns are categorical?`
- `Which columns have missing values?`
- `Which columns are likely identifiers?`
- `Which columns have many unique values?`

The current prototype also already supports richer time-derived prompts such as:

- `How many tickets were created by quarter?`
- `Show revenue by month`
- `Show revenue by quarter`
- `Compare revenue this quarter to last quarter`
- `Compare revenue this year to last year`

The current prototype also already supports boolean verification prompts such as:

- `Does csat_score have missing values?`
- `Is csat_score complete?`
- `Are any resolution hours above 20?`
- `Does csat_score fall between 3 and 5?`
- `Is revenue numeric?`
- `Is created_at a datetime field?`
- `Is ticket_id likely an identifier?`

The current prototype also already supports stronger filter-oriented prompts such as:

- `Show revenue for West SMB`
- `Only reopened tickets`
- `Exclude reopened tickets`
- `What is the total revenue for West in 2026?`
- `What is the total revenue for West in March?`

The current prototype also already applies stronger typed routing guards so prompts like:

- `What is the average region?`
- `What is the highest posted_at?`

do not silently fall back to a numeric measure when the requested target type is incompatible with the requested computation.

## Design Rule

The API surface should stay thin.

The important boundary is not the transport layer.
The important boundary is:

- input -> canonical plan
- execution -> backend adapters
- output -> canonical result
