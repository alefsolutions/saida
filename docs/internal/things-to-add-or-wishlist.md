![SAIDA Banner](assets/github-banner.png)

# SAIDA 0.3.0 Things To Add / Wishlist

This file captures important improvements that should be considered for **SAIDA 0.3.0** and beyond.

[`architecture.md`](../overview/architecture.md) remains the source of truth.

## Intent Organization And Canonical Routing

One important improvement area is the way SAIDA organizes intent families, canonicalization, and routing.

The current codebase already has the beginnings of this structure:

- explicit `intent_name` values in canonical requests
- family-like routing for metadata, ranking, verification, time analysis, and tabular querying
- planner-side validation
- result-family normalization

However, this is still not formalized strongly enough.

The risk is that SAIDA can drift into a reactive pattern:

- a prompt fails
- a phrase rule gets added
- a branch gets added
- a test gets added

That approach can improve coverage in the short term, but it does not scale cleanly.

### Desired Improvement

SAIDA should move toward a more formal and capability-driven intent system.

The desired direction is:

- define canonical intent families explicitly
- define a canonical request grammar explicitly
- define routing precedence explicitly
- reduce overlapping keyword heuristics
- separate language parsing from analytical semantics more cleanly
- make planning more capability-driven and less phrase-driven

### Intent Families To Formalize

Examples of first-class intent families that should be defined more explicitly:

- metadata inquiry
- scalar aggregation
- grouped aggregation
- ranking
- verification
- time-bucket analysis
- statistical testing
- tabular retrieval
- grouped tabular retrieval

Each family should clearly define:

- supported operations
- valid target types
- valid grouping behavior
- valid filters
- valid time references
- expected result shapes

### Canonical Request Grammar

SAIDA should normalize prompts into a clearer canonical operation model, for example:

- operation
- target
- grouping
- filters
- ordering
- limit
- pagination
- time bucket
- comparison reference

This would help avoid situations where a prompt about ranking falls into a plain aggregation path just because a keyword overlaps.

### Routing Precedence

SAIDA should define an explicit routing precedence model so overlapping language is resolved consistently.

Examples of competing signals today:

- `top`
- `highest`
- `list`
- `rows`
- `by month`
- `compare`
- `show`

These should not compete informally.

The system should explicitly decide which families take priority when multiple signals are present.

### Capability Matrix

SAIDA should also evolve toward a capability matrix for testing and validation.

Instead of mainly adding prompt-by-prompt tests, the system should define test coverage by capability family:

- ranking
- verification
- time analysis
- tabular retrieval
- grouped tabular querying
- metadata inquiry
- statistical workflows

Each family should have:

- normal cases
- paraphrase cases
- safe failure cases
- invalid request cases
- edge and boundary cases

### Why This Matters

This work would move SAIDA away from:

- prompt-specific bandage fixes

and toward:

- capability-driven canonical analysis routing

That is more consistent with the SAIDA 0.3.0 architecture direction:

- contract-first
- source-agnostic
- backend-agnostic
- deterministic
- structured

### Summary

Wishlist item:

- formalize intent families, canonical request grammar, and routing precedence as a first-class architectural improvement

This should be treated as a real product and architecture enhancement, not just a small prompt-fix task.

## Capability Contract Source Of Truth

Another important improvement is to maintain a formal capability contract in code.

The desired direction is:

- define a prompt or LLM contract module only where frontend guidance still needs it
- make it describe the current live framework surface
- use it as a reusable source of truth for:
  - intent families
  - accepted request fields
  - valid operations
  - valid target and grouping rules
  - valid filters and time references
  - result shapes and result dtypes
  - response envelope fields

This matters because today the optional LLM layer only knows what SAIDA supports through provider prompt text.

That means:

- the LLM sees a prose description
- but it does not directly know the real canonical router contract

The improvement direction is:

- move capability knowledge into code
- let the LLM/provider prompt be derived from that contract
- keep deterministic canonicalization and planning as the final authority

Wishlist item:

- maintain a machine-readable capability contract in core and use it to align routing, provider prompting, and result-contract understanding
