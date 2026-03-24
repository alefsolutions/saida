![SAIDA Banner](assets/github-banner.png)

# Changelog

All notable changes to this project will be documented in this file.

Quick links: [Main README](./README.md) | [Architecture](./ARCHITECTURE.md) | [License](./LICENSE)

## [Unreleased]

### Changed

- Reworked prompt interpretation around explicit prompt families, capability validation, and deterministic plan compilation.
- Added a live prompt family catalog with governed and partial family invariants.
- Added `PromptCapabilityContract` wiring to the engine and response payloads.
- Added metadata count families including:
  - `column_count`
  - `numeric_column_count`
  - `categorical_column_count`
  - `measure_count`
  - `dimension_count`
  - `time_column_count`
  - `identifier_count`
  - `high_cardinality_count`
- Added `distinct_value_count` as a first-class scalar family.
- Added singular schema/property routing for:
  - column type lookup
  - column presence checks
  - dimension/measure/high-cardinality property checks
  - representation ranking results
- Replaced the old broad “legacy metric fallback” naming with `exploratory_metric_overview` and tightened clarification/refusal boundaries for unsupported prompts.
- Added optional LLM canonical-question condensation for prompt interpretation.
- Added structured LLM semantic proposal fields for:
  - `operation`
  - `object_kind`
  - `object_ref`
  - `expected_result_shape`
- Added deterministic semantic operation/object routing so prompts like `Count total rows in dataset for Q1` normalize to scalar count workflows instead of row retrieval.
- Added richer time-filter support including:
  - month-year filtering
  - quarter filters
  - recurring day-of-month filters
  - weekday filters
  - month-start and month-end filters
  - recent-window filters
  - nth-weekday-of-month filters
- Allowed quarter-based time references in row-count planning.
- Improved clarification UX in playground scripts and added full-response output mode for the JSON playground.
- Strengthened prompt reproducibility, prompt acceptance, and capability-matrix testing across the current prompt family surface.
- Updated root docs so README, architecture, API, and schema materials describe the live `0.2.x` codebase more accurately.

### Planned

- Predictive and forecasting APIs beyond the current reserved surface
- Deeper semantic intent modeling beyond prompt-family routing
- Continued migration of manual family logic into stricter executable family specs

## [0.1.0] - 2026-03-02

### Added

- Initial SAIDA package foundation and deterministic analytics implementation.
