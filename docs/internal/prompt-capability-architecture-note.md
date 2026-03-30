![SAIDA Banner](../../assets/github-banner.png)

# Prompt Capability Architecture Note

[![Version](https://img.shields.io/badge/version-0.3.0-1f6feb)](../../pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-2ea043)](../../LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)](../../pyproject.toml)

This note explains where prompt and capability handling now fits in the live SAIDA architecture.

The short version is:

- prompt handling still exists
- capability contracts still matter
- but they are no longer the center of SAIDA

The center is now:

- `Dataset`
- `AnalysisPlan`
- validation
- execution
- `AnalysisResult`

## Current Role Of Prompt Handling

Prompt handling is now best understood as an optional frontend subsystem.

It is responsible for:

- turning natural language into a candidate `AnalysisPlan`
- building request-side artifacts such as `AnalysisRequest`
- building `PromptPlanContract`
- helping explain why SAIDA clarified or refused a prompt

It is not responsible for:

- executing compute
- bypassing validation
- redefining the execution contract

## Current Live Prompt Flow

The live prompt-driven flow is:

- `prompt -> AnalysisPlanGenerator -> AnalysisRequest + PromptPlanContract + candidate AnalysisPlan -> PlanValidator -> execution`

This means prompt interpretation now feeds the execution core instead of defining the core.

## Why The Capability Contract Still Matters

`PromptPlanContract` is still useful because it captures:

- what the frontend thinks the user is asking for
- what capabilities are being activated
- what parameters were resolved
- what is missing or ambiguous
- whether the dataset looks compatible

That makes it valuable for:

- explainability
- prompt debugging
- frontend regression testing
- safe clarification/refusal behavior

## What Changed Conceptually

Older SAIDA work treated prompt normalization and prompt-family routing as the main architectural center.

The new direction is different:

- prompts are one way to produce a plan
- authored plans are equally valid
- execution is defined by the canonical plan and validator

So the prompt capability system is still important, but it is now a supporting layer rather than the main identity of the framework.

## Live Components In This Area

The current prompt/capability side of the codebase mainly lives in:

- `src/saida/plan_generation/canonicalization.py`
- `src/saida/plan_generation/prompt_family_catalog.py`
- `src/saida/plan_generation/planning.py`
- `src/saida/plan_generation/llm_contract.py`
- `src/saida/plan_generation/`
- `src/saida/llm/`

## Practical Rule Going Forward

When thinking about new prompt work, the right question is:

- does this help produce a valid canonical `AnalysisPlan`?

Not:

- does this make prompt routing more clever in isolation?

That keeps prompt work aligned with SAIDA's plan-first architecture.

## Future Direction

Prompt and capability work should continue to improve:

- candidate plan generation
- contract validation
- clarification behavior
- optional LLM plan generation

But the source of truth should remain:

- code contracts
- validators
- analytics registry
- compute adapters
- standardized result shaping
