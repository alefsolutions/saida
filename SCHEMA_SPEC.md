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

- `result_type`
- `schema`
- `data`
- `metadata`

The result must be self-describing enough to travel across:

- APIs
- UIs
- plugins
- output formatters

## Shape Requirements

The architecture names these output shapes as first-class:

- scalar
- vector
- table
- matrix
- time_series
- distribution
- spatial

## Result Normalization

Backend-specific output should never leak directly as the public contract.

Instead, SAIDA should normalize backend output into canonical result form with:

- stable shape
- stable schema
- stable type information

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

The current prototype also accepts richer canonical filter payloads for:

- equality filters
- exclusion filters
- implied yes/no flag filters
- simple year filters on datetime columns
- simple month filters on datetime columns

These filters are normalized before execution and reused across the same analytical response contract.

## Guiding Principle

Schemas in SAIDA 0.2.0 are not just internal containers.

They are the formal contract that separates:

- meaning
- execution
- presentation
