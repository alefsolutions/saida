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

## Guiding Principle

Schemas in SAIDA 0.2.0 are not just internal containers.

They are the formal contract that separates:

- meaning
- execution
- presentation
