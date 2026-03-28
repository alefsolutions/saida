# SAIDA Spec Tests

This test suite is organized around SAIDA's plan-first framework identity.

## Core Framework Focus

The primary contract under test is:

- `Dataset + AnalysisPlan -> AnalysisResult`

The main core execution tests are:

- `test_plan_execution_e2e.py`
- `test_plan_execution_family_contracts.py`
- `test_plan_execution_method_matrix.py`
- `test_plan_execution_reproducibility.py`
- `test_plan_contract.py`
- `test_validation_gatekeeper.py`
- `test_results_builder.py`
- `test_output_interfaces.py`

These files treat authored `AnalysisPlan` objects as the source of truth and assert canonical `AnalysisResult` behavior.

## Optional Frontend Coverage

Prompt and LLM-related tests still exist, but they verify optional frontend behavior only.

The main optional/frontend test files are:

- `test_normalizer.py`
- `test_planner.py`
- `test_plan_generators.py`
- `test_plan_reproducibility.py`
- `test_prompt_acceptance_matrix.py`
- `test_prompt_capability_contract.py`
- `test_prompt_capability_matrix.py`
- `test_prompt_family_catalog.py`
- prompt-oriented sections inside `test_engine.py`, `test_smoke.py`, and `test_playground.py`

These tests are valuable, but they do not define SAIDA's core framework contract.

## Supporting Coverage

Additional files cover:

- adapters
- sources
- CLI
- summaries
- analytics registry

Together, the suite is intended to prove that SAIDA behaves first as a deterministic analysis framework, with prompt generation as an optional layer on top.
