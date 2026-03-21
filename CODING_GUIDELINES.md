![SAIDA Banner](assets/github-banner.png)

# SAIDA Coding Guidelines

These guidelines should be read together with `ARCHITECTURE.md`.

## Core Rule

Write code that preserves the architecture boundary:

- SAIDA defines meaning
- backends perform computation

## Principles

- simple > complex
- explicit > implicit
- readability counts
- no over-engineering

## What Good SAIDA 0.2.0 Code Should Do

- keep canonical contracts clear
- keep source access separate from computation
- keep backend routing separate from meaning
- keep result normalization explicit
- keep LLM behavior optional and bounded

## Contract-First Design

Prefer code that makes these boundaries obvious:

- input -> canonical `AnalysisPlan`
- backend execution -> adapter layer
- output -> canonical `AnalyticalResult`

Do not let backend-specific shapes become the public meaning layer.

## Modularity

Prefer small, focused modules with narrow responsibilities.

Typical module categories should map to architecture concerns:

- core
- adapters
- sources
- outputs
- llm
- tests

## LLM Rules

LLMs may help with:

- structured plan creation
- output wording

LLMs must not:

- execute
- bypass validation
- replace canonical contracts

## Testing Rules

Tests should reflect the architecture layers.

Minimum categories:

- input tests
- plan validation tests
- adapter execution tests
- result normalization tests

## Final Guideline

When in doubt, choose the design that makes canonical meaning, backend execution, and output normalization easier to see and easier to test.
