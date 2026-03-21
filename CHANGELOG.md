![SAIDA Banner](assets/github-banner.png)

# Changelog

All notable changes to this project will be documented in this file.

Quick links: [Main README](./README.md) | [Architecture](./ARCHITECTURE.md) | [License](./LICENSE)

## [Unreleased]

### Changed

- The active root documentation set now explicitly identifies the SAIDA 0.2.0 direction.
- SAIDA documentation has been realigned around the 0.2.0 architecture reset.
- `ARCHITECTURE.md` is now treated as the primary source of truth for the framework direction.
- Repo docs now describe SAIDA as a canonical analytics framework built around `AnalysisPlan` and `AnalyticalResult`.
- Added first-class schema metadata question support for column types, numeric columns, categorical columns, missing values, identifiers, and high-cardinality columns.
- Added metadata result tables and summaries for typed schema questions in the 0.2.0 prototype.
- Added richer time-derived grouping and comparison support across year, month, and quarter buckets.
- Added deterministic adjacent-period comparison support for month, quarter, and year prompts in the 0.2.0 prototype.
- Added broader boolean verification support for null checks, completeness checks, threshold checks, range checks, and column-property checks.
- Added canonical verification result tables and summaries for the expanded Phase 3 prompt family in the 0.2.0 prototype.

### Planned

- Source-agnostic source adapters
- Backend routing and adapter translation layers
- Result canonicalization around stable analytical result contracts
- Multi-source and multi-backend execution

## [0.1.0] - 2026-03-02

### Added

- Initial SAIDA package foundation and deterministic analytics implementation.
