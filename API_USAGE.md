![SAIDA Banner](assets/github-banner.png)

# SAIDA API Usage

This document describes how SAIDA 0.2.0 should be used at the contract level.

`ARCHITECTURE.md` is the source of truth.

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

Minimum result expectations:

- `result_type`
- `schema`
- `data`
- `metadata`

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

## Design Rule

The API surface should stay thin.

The important boundary is not the transport layer.
The important boundary is:

- input -> canonical plan
- execution -> backend adapters
- output -> canonical result
