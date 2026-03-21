![SAIDA Banner](assets/github-banner.png)

# SAIDA *(0.2.0 Architecture Shift)*

[![Version](https://img.shields.io/badge/version-0.2.0--preview-1f6feb)](ARCHITECTURE.md)
[![License](https://img.shields.io/badge/license-MIT-2ea043)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)](pyproject.toml)
![Status](https://img.shields.io/badge/status-architecture%20reset-f59e0b)

SAIDA is a **canonical analytics framework** for turning prompts, API payloads, or direct plans into standardized analysis plans and standardized analytical results.

`ARCHITECTURE.md` is the current source of truth for SAIDA 0.2.0.

## What Changed In 0.2.0

SAIDA is no longer being framed primarily as a single deterministic analytics engine with built-in workflows.

The new direction is:

- input -> canonical `AnalysisPlan`
- execution -> routed to external compute backends
- output -> canonical `AnalyticalResult`

Core principle:

- SAIDA defines meaning
- backends perform computation

## Architecture At A Glance

SAIDA 0.2.0 is organized into these layers:

1. Input Layer
2. Canonicalization Layer
3. Validation Layer
4. Routing Layer
5. Adapter Layer
6. Execution Layer
7. Result Canonicalization Layer
8. Output Layer

This means SAIDA is being designed to be:

- source-agnostic
- backend-agnostic
- contract-first
- reproducible
- plugin-friendly

## Core Contracts

The two most important contracts are:

- `AnalysisPlan`
- `AnalyticalResult`

SAIDA should accept:

- prompt input
- API input
- direct JSON plans

SAIDA should return:

- canonical structured results with stable shape, schema, and metadata

## Sources And Backends

The architecture defines SAIDA as multi-source and multi-backend.

Planned source support includes:

- CSV
- Excel
- PostgreSQL
- MySQL
- Microsoft Access
- GIS sources such as GeoJSON and shapefiles

Planned execution backends include:

- DuckDB
- pandas / Polars
- statsmodels
- GeoPandas
- scikit-learn / TensorFlow

## LLM Position

LLMs remain optional.

Rules:

- LLM never executes
- LLM only helps produce structured plans

The compute truth stays outside the LLM layer.

## Documentation Map

Core project docs:

- [Architecture](ARCHITECTURE.md)
- [Schema Spec](SCHEMA_SPEC.md)
- [API Usage](API_USAGE.md)
- [File Structure](FILE_STRUCTURE.md)
- [Coding Guidelines](CODING_GUIDELINES.md)
- [Changelog](CHANGELOG.md)

Example context docs:

- [Sales Context](examples/sales_context.md)
- [Retail Sales Context](examples/contexts/retail_sales_100.md)
- [Support Tickets Context](examples/contexts/support_tickets_500.md)
- [Shipping Operations Context](examples/contexts/shipping_operations_1000.md)

## Current Documentation Rule

For SAIDA 0.2.0, treat [ARCHITECTURE.md](ARCHITECTURE.md) as authoritative.

The remaining root docs are intentionally limited to usage, structure, schemas, coding rules, and change history so the new direction stays clear.
