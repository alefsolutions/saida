![SAIDA Banner](assets/github-banner.png)

# Changelog

All notable changes to this project are documented here.

Quick links:

- [README](./README.md)
- [Architecture](./docs/overview/architecture.md)
- [Schema Spec](./docs/reference/schema-spec.md)

## [Unreleased]

### Changed

- Re-centered SAIDA around `AnalysisPlan` as the executable contract and `AnalysisResult` as the standardized output.
- Added `PromptAnalysisFrontend.plan(...)` and `Saida.execute_plan(...)` as first-class plan APIs.
- Expanded `AnalysisPlan` to `saida.plan.v2` with:
  - `plan_id`
  - `dataset_refs`
  - `inputs`
  - `expected_result_name`
  - `expected_result_shape`
  - richer step metadata
- Expanded `PlanStep` with:
  - canonical analytics family
  - method id
  - dependencies
  - output refs
  - expected output
  - execution metadata
- Added a formal analytics family and method registry.
- Added formal source interfaces and aligned built-in source adapters to them.
- Added formal compute interfaces and routed execution through compute adapters instead of engine-only branching.
- Added formal output interfaces and adapter-based result rendering.
- Moved prompt and LLM handling into a formal plan-generation subsystem.
- Strengthened validation so the validator now acts as the execution gatekeeper with:
  - method checks
  - required input checks
  - field validation
  - backend compatibility validation
  - result expectation validation
- Rebuilt part of the test suite around the new core contract with:
  - plan-centric end-to-end tests
  - plan reproducibility tests
  - adapter-equivalence tests
  - optional plan-generation subsystem coverage

### Documentation

- Rewrote the main docs around the cleaned plan-first framework model.
- Shortened README to focus on adoption, core usage, and next docs to read.
- Updated architecture, API, schema, and file-structure docs to consistently position prompt and LLM features as optional frontend layers.
- Added DAG execution and plan-authoring guidance, including explicit step input/output contracts and `final_output_ref`.

### DAG Execution

- Added typed runtime artifacts and an execution-scoped artifact store for graph-aware plan execution.
- Upgraded validation to check graph references, output ref uniqueness, cycle safety, and `final_output_ref`.
- Added deterministic DAG scheduling so step dependencies can be resolved from both `depends_on` edges and step-output bindings.
- Extended prompt-generated plans so they emit DAG-ready `inputs`, `outputs`, `output_refs`, and `final_output_ref`.

### Compatibility And Release Hardening

- Preserved `saida.response.v2` as the public response schema while surfacing DAG execution details under `execution` and `meta`.
- Preserved compatibility for legacy authored single-step plans by binding missing dataset inputs, output refs, expected outputs, and `final_output_ref`.
- Added compatibility metadata to execution results so callers can see when legacy plan shims were applied.
- Kept execution deterministic and single-threaded for the current release scope.

### Still Present But Optional

- Prompt-driven analysis through `analyze(...)`
- LLM-assisted plan generation
- prompt family and prompt contract artifacts

These remain supported, but they are now documented as optional frontend functionality.

### Reserved Surface

These APIs still exist but are not the main stable feature area:

- `train`
- `predict`
- `forecast`

## [0.1.0] - 2026-03-02

### Added

- Initial SAIDA package foundation and deterministic analytics implementation.
