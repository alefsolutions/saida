![SAIDA Banner](assets/github-banner.png)

# SAIDA 0.2.0 Schema Spec

This document summarizes the canonical contracts defined for **SAIDA 0.2.0**.

`ARCHITECTURE.md` is the source of truth.

## Primary Contracts

The architecture centers on two primary contracts:

- `AnalysisPlan`
- `AnalyticalResult`

## AnalysisPlan

`AnalysisPlan` is the canonical input to execution.

It should be:

- structured
- deterministic
- multi-step

Typical responsibilities of the plan:

- describe task type
- describe steps
- describe intended meaning independent of backend

## AnalyticalResult

`AnalyticalResult` is the canonical output of the framework.

It must include:

- a standardized response envelope
- a self-describing primary `result`
- optional secondary `tables`
- metadata and execution trace information

The result must be self-describing enough to travel across:

- APIs
- UIs
- plugins
- output formatters

## Current Prototype Envelope

The current 0.2.0 prototype returns `saida.response.v2` with these top-level fields:

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

## Shape Requirements

The architecture names these output shapes as first-class:

- scalar
- vector
- table
- matrix
- timeseries
- distribution
- spatial

The current prototype also uses:

- recordset
- object
- verification
- statistical_test

## Result Normalization

Backend-specific output should never leak directly as the public contract.

Instead, SAIDA should normalize backend output into canonical result form with:

- stable shape
- stable schema
- stable type information

The current primary `result` object is normalized with:

- `physical_shape`
- `logical_shape`
- `dtype`
- `schema`
- `dimensions`
- `row_count`
- `labels`
- `pagination`
- `metadata`
- `value`

## Current Prototype Result Families

The current 0.2.0 prototype already returns canonical table results for schema metadata questions, including:

- full column type inventory
- numeric column inventory
- categorical column inventory
- time column inventory
- missing value inventory
- identifier inventory
- high-cardinality inventory

These results are exposed through the same standardized response envelope as analytical tables.

The current prototype also returns canonical time-series result families for:

- time bucket counts by year, month, and quarter
- time bucket breakdowns for numeric targets by year, month, and quarter
- adjacent period comparisons across month, quarter, and year buckets

These results are normalized as canonical timeseries-style tables in the same response contract.

The current prototype also returns canonical verification result families for:

- time-value existence checks
- filtered row existence checks
- null and completeness checks
- numeric threshold and range checks
- column-property checks such as numeric, datetime, categorical, and identifier validation

These results are normalized as verification-style outputs in the same response contract.

The current prototype also returns canonical tabular result families for:

- filtered row retrieval
- selected-column row retrieval
- grouped tabular outputs
- paginated recordset responses

These results are normalized as `recordset` or `table` outputs and carry structured pagination metadata:

- `page`
- `page_size`
- `total_rows`
- `returned_rows`
- `has_next_page`
- `has_previous_page`
- `offset`
- optional `next_page_token`

The current prototype also accepts richer canonical filter payloads for:

- equality filters
- exclusion filters
- implied yes/no flag filters
- simple year filters on datetime columns
- simple month filters on datetime columns

These filters are normalized before execution and reused across the same analytical response contract.

The current prototype also applies stronger typed routing rules before execution so that:

- numeric aggregations require numeric targets
- unsupported time and categorical aggregations fail at the contract boundary
- grouped descriptive requests do not silently reuse measure-only workflows when the target type is incompatible

## Guiding Principle

Schemas in SAIDA 0.2.0 are not just internal containers.

They are the formal contract that separates:

- meaning
- execution
- presentation
