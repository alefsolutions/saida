# Saida Capability Graph Codex Analysis Plan

## Purpose

This document is an instruction and analysis brief for Codex to inspect the current **Saida** codebase, specifically the **prompt → LLM → analysis plan** section, identify failure points, and evaluate whether a **capability graph / compatibility graph** architecture would improve reliability compared to the current implementation.

The immediate problem to investigate is that the current prompt-to-plan pipeline is producing:

- prompt mismatches
- capability mismatches
- data mismatches
- invalid analysis-plan outputs
- unsupported command combinations
- schema/contract violations
- unstable or brittle prompt behavior

This document is written as an engineering analysis task for Codex to execute step by step.

---

## Core Problem Statement

Saida appears to have a strong compute/result layer, but the weak point is the translation layer between:

1. user natural-language prompt
2. LLM interpretation
3. canonical analysis plan generation
4. compute/workflow execution

The likely issue is that the current system is relying too heavily on direct prompt-to-plan generation, where the LLM is expected to infer the correct canonical structure in one pass.

This leads to errors when:

- prompts overlap across multiple analysis intents
- the LLM selects unsupported capabilities
- required parameters are missing
- terms used by the user do not align with canonical metric/dimension names
- the plan shape does not match the actual compute capabilities
- data shape expectations differ from produced plan outputs

The proposed new direction is to move toward a **capability graph** architecture.

---

## Proposed Concept: Capability Graph

The new idea is that Saida should not treat prompt understanding as a flat classification problem or a direct freeform generation problem.

Instead, Saida should treat prompt understanding as **activation of a valid capability subgraph**.

### Meaning

A user prompt may activate multiple analytical regions at once, for example:

- ranking
- comparison
- trend
- segmentation
- diagnostic

These should not be forced into one exclusive label.

Instead, the system should:

1. detect candidate capabilities
2. map them into a graph of supported analytical capabilities
3. validate whether those capabilities form a legal and supported subgraph
4. compile that subgraph into a canonical analysis plan

So the design becomes:

**Prompt → Candidate capability nodes → Validated capability subgraph → Canonical analysis plan → Compute/workflows → Analysis result**

---

## Why a Graph Approach

A graph is preferred over a strict tree or pyramid because analytical requests often overlap.

Examples:

- `growth ranking` belongs to both ranking and comparison
- `grouped trend` belongs to both trend and segmentation
- `forecast by region` belongs to predictive and grouped analysis
- `anomaly over time` belongs to diagnostic and trend analysis

A graph allows:

- multi-parent relationships
- compositional capability matching
- dependency modeling
- compatibility checks
- invalid combination detection
- deterministic expansion into primitives

This is more realistic than forcing every request into one template family too early.

---

## High-Level Architectural Target

Codex should evaluate whether the current Saida codebase can be evolved toward this target architecture:

1. **Prompt intake**
2. **Intent and entity extraction**
3. **Capability graph node activation**
4. **Capability/compatibility contract validation**
5. **Subgraph selection**
6. **Canonical analysis plan compilation**
7. **Compute/workflow execution**
8. **Analysis result production**

The main focus is on steps 2 through 6.

---

## Critical Additional Principle: Data Feasibility Must Be Checked Separately

A request may match a supported analytical capability, but still fail because the **actual dataset does not support the requested analysis**.

This is a separate concern from prompt interpretation and capability matching.

Examples:

- the user asks for a trend analysis, but the dataset has no valid time field
- the user asks for growth comparison, but there is not enough historical depth
- the user asks for segmentation by region, but no region field exists
- the user asks for forecasting, but the dataset is too short, too sparse, or too irregular
- the user asks for correlation or driver analysis, but the relevant variables are missing
- the user asks for ranked contribution, but the required metric fields are absent or unusable

This means Saida needs not just a capability graph, but also a **data-feasibility check** before plan compilation or execution.

The system should distinguish between:

1. **Capability support** — whether Saida knows how to perform this type of analysis in principle
2. **Data support** — whether the current dataset contains the fields, quality, granularity, and history needed to perform it

A request should only proceed when both are satisfied.

So the deeper design becomes:

**Prompt → Candidate capability nodes → Capability contract validation → Data-feasibility validation → Canonical analysis plan → Compute/workflows → Analysis result**

This should be treated as a first-class architectural rule.

## Key New Concept: Prompt-to-Capability Contract

The current system likely has some implicit contract between prompt and plan, but it should be made explicit.

The new contract should answer:

1. What is the user asking for?
2. Which supported analytical capabilities does this request invoke?
3. Which parameters were resolved?
4. Which required parameters are missing?
5. Which parts are unsupported or ambiguous?
6. Is there a valid supported path from this request to a canonical plan?

The contract should be capability-aware, not just prompt-aware.

This means the system should not ask only:

> What does the prompt mean?

It should also ask:

> Which supported capability nodes and dependencies are actually satisfiable?

---

## Capability Graph Model

Codex should inspect the codebase and see how close or far it already is from a graph-capable model.

### Recommended node categories

#### 1. Domain nodes
Broad analytical intent zones.

Examples:

- descriptive
- comparative
- ranking
- trend
- diagnostic
- predictive
- segmentation
- distribution

#### 2. Pattern nodes
Reusable supported analysis patterns.

Examples:

- top_n_by_metric
- bottom_n_by_metric
- grouped_breakdown
- period_over_period_comparison
- grouped_trend
- growth_ranking
- contribution_breakdown
- variance_analysis
- anomaly_scan
- forecast_series

#### 3. Primitive nodes
Canonical low-level plan operations.

Examples:

- select_dataset
- resolve_metric
- resolve_dimension
- filter
- filter_period
- time_bucket
- group_by
- aggregate
- derive_metric
- derive_growth
- compare_periods
- compare_groups
- sort
- limit
- window
- segment
- forecast

#### 4. Constraint/contract metadata
These are validation rules and requirements.

Examples:

- requires_metric
- requires_dimension
- requires_time_field
- requires_reference_period
- output_shape_ranked_table
- output_shape_time_series
- compatible_with_segment_filter
- incompatible_with_distribution_histogram

---

## Recommended Edge Types in the Graph

Codex should evaluate whether current code patterns can be refactored toward explicit typed edges.

### `specializes`
A pattern refines a broader domain.

Example:

- growth_ranking specializes ranking
- growth_ranking specializes comparative

### `requires`
A node depends on another node or parameter.

Example:

- growth_ranking requires metric
- growth_ranking requires dimension
- growth_ranking requires reference_period

### `uses`
A pattern expands into primitives.

Example:

- top_n_by_metric uses aggregate
- top_n_by_metric uses sort
- top_n_by_metric uses limit

### `compatible_with`
Nodes can coexist in one valid analysis shape.

### `incompatible_with`
Nodes should not coexist in the same plan or output shape.

### `implies`
A signal or term strongly suggests another capability.

Example:

- growth implies comparison
- monthly implies time_bucket
- top 10 implies ranking + limit

---

## Core Engineering Hypothesis

The current Saida pipeline may be too direct:

**Prompt → LLM → Analysis Plan**

The proposed graph-based design becomes:

**Prompt → LLM/rules extract candidate nodes + parameters → contract validates subgraph → deterministic compiler produces analysis plan**

The hypothesis is that this would reduce:

- invalid command combinations
- mismatched data expectations
- unsupported analysis-plan generation
- hidden assumptions made by the LLM
- brittle prompt behavior
- plan-output inconsistencies

Codex should test this hypothesis against the current architecture.

---

## What Codex Should Analyze in the Current Codebase

Codex should inspect the codebase and produce findings under the following categories.

### 1. Prompt Processing Layer
Identify where natural-language prompts are currently:

- accepted
- normalized
- routed
- classified
- transformed into plan instructions

Questions:

- Where is the main prompt-to-plan logic located?
- Is plan generation single-step or multi-step?
- Is it heavily prompt-template driven?
- Are there hidden assumptions embedded in prompt instructions?
- Is there any existing intermediate representation?

### 2. Canonical Analysis Plan Layer
Identify:

- the current analysis plan schema
- the canonical commands available
- required and optional fields
- command dependency order
- command compatibility rules
- how plan validation is currently performed

Questions:

- Is there a strict canonical grammar already?
- Are commands typed and validated?
- Are there plan schemas or only implicit structures?
- Are there known recurring mismatch classes?

### 3. Capability/Support Surface
Determine what Saida actually supports today.

Questions:

- What high-level analysis types are already supported?
- What low-level primitives exist?
- Which patterns are already indirectly implemented?
- Which capabilities are assumed by prompts but not actually backed by compute logic?

### 4. Failure Surface
Locate actual mismatch/error points.

Questions:

- Where do prompt mismatches occur?
- Where do capability mismatches occur?
- Where do data mismatches occur?
- Which modules throw validation or schema errors?
- Are errors happening before plan generation, during plan generation, or at execution time?

### 5. Data Shape / Result Shape Contracts
Inspect how the codebase defines:

- expected input data shapes
- transformation expectations
- output result shapes
- compatibility between plan nodes and result nodes

Questions:

- Are result schemas formalized?
- Do plan steps assume data columns that are not guaranteed?
- Are metric/dimension references validated against dataset metadata?
- Are there shape mismatches between plan output and compute modules?

### 6. Prompt/Capability Vocabulary Alignment
Check whether user language is mapped to canonical system language.

Questions:

- Are aliases handled?
- Are synonyms normalized?
- Are metric and dimension names canonicalized?
- Are ambiguous terms handled safely?

Examples:

- revenue vs sales vs turnover
- branch vs office vs location
- monthly growth vs change over time

### 7. Existing Architecture Fit for Graph Refactor
Assess how easily the codebase can support:

- domain nodes
- pattern nodes
- primitive nodes
- typed edges
- validation contract layer
- deterministic graph-to-plan compilation

---

## Specific Refactor Goal for Codex to Evaluate

Codex should analyze whether the current system can be refactored toward this architecture:

### Stage A: Signal extraction
From prompt, detect:

- candidate domains
- candidate patterns
- candidate primitives
- parameter hints
- ambiguity flags

### Stage B: Capability graph activation
Map extracted signals into graph nodes with confidence scores.

### Stage C: Contract validation
Validate:

- required parameters
- supported capabilities
- data availability
- field availability
- minimum data sufficiency
- output-shape compatibility
- inter-node compatibility
- dependency satisfaction

### Stage C2: Data-feasibility validation
Separately validate whether the current dataset can support the requested analysis in practice.

This should include checks such as:

- does the dataset contain the required fields?
- are the resolved metric and dimension fields actually present?
- does the dataset contain a valid time field when time-based analysis is requested?
- is there enough historical depth for comparison, trend, or forecasting?
- is the granularity appropriate for the requested analysis?
- are null rates, sparsity, or cardinality issues too severe?
- do joins or derived metrics require fields that are absent?
- does the requested result shape make sense for the available data?

The system should return a structured failure or downgrade path when capability is supported but data is insufficient.

Possible statuses:

- supported_and_data_feasible
- supported_but_data_infeasible
- supported_but_data_insufficient
- supported_with_partial_fallback
- unsupported_capability


- required parameters
- supported capabilities
- data availability
- output-shape compatibility
- inter-node compatibility
- dependency satisfaction

### Stage D: Subgraph selection
Choose the smallest valid connected subgraph that satisfies the request.

### Stage E: Deterministic compilation
Compile the selected subgraph into an ordered canonical analysis plan.

### Stage F: Execution and result validation
Run compute/workflows only after the compiled plan passes contract validation.

---

## Recommended Deliverables from Codex

Ask Codex to produce the following outputs.

### Deliverable 1: Current-State Architecture Analysis
A concise but technically detailed map of the current prompt-to-plan pipeline.

Include:

- file/module map
- key functions/classes
- plan generation flow
- validation flow
- failure points

### Deliverable 2: Error Taxonomy
List all observed or likely error classes in the current system.

Suggested taxonomy:

- prompt intent mismatch
- unsupported capability selection
- unresolved parameter mismatch
- canonical schema violation
- invalid command ordering
- invalid command combination
- metric/dimension resolution mismatch
- dataset metadata mismatch
- output shape mismatch
- runtime compute mismatch

For each class, identify likely root cause and location.

### Deliverable 3: Capability Inventory
Inventory current supported capabilities in two layers:

- user-facing high-level analysis capabilities
- underlying primitive compute operations

This should become the foundation for a first version of the capability graph.

### Deliverable 4: Proposed Capability Graph Design Fit
Evaluate whether the graph approach fits the current system.

Codex should answer:

- which parts of the current code already resemble graph nodes or contracts
- which parts would need redesign
- what can be wrapped versus rewritten
- where the graph can be introduced incrementally

### Deliverable 5: Acceptability Analysis
Compare the proposed capability graph approach against the current Saida approach.

Codex should evaluate:

- reliability improvement potential
- complexity cost
- migration risk
- maintainability impact
- explainability impact
- testing benefits
- likely reduction in plan mismatch errors

The result should include a recommendation such as:

- high-fit, recommended now
- medium-fit, recommended incrementally
- low-fit, not worth current disruption

### Deliverable 6: Incremental Refactor Plan
Produce a staged migration plan.

Suggested phases:

1. document current canonical plan grammar
2. inventory capabilities and primitives
3. introduce explicit prompt-to-capability contract object
4. add alias/synonym normalization layer
5. define first graph nodes and edges
6. implement graph validation and subgraph selection
7. replace direct prompt-to-plan generation with graph-to-plan compilation
8. expand test coverage with real prompts and expected contracts

---

## Recommended Questions Codex Should Explicitly Answer

1. Where exactly does the current prompt-to-plan mismatch begin?
2. Is the current design fundamentally direct-generation based?
3. Does the current code already contain hidden graph-like structures or templates?
4. Which existing abstractions can be reused for graph nodes?
5. Which current errors would most likely disappear under a graph contract architecture?
6. Which new complexities would a graph introduce?
7. Would a graph approach improve determinism and validation enough to justify migration?
8. What is the best incremental adoption path?

---

## Suggested Evaluation Criteria for the Graph Approach

Codex should judge the graph approach on these dimensions.

### Reliability
Would it reduce invalid plans and mismatches?

### Determinism
Would it reduce freeform LLM behavior and increase control?

### Explainability
Would it make it easier to inspect why a prompt mapped to a given plan?

### Compatibility Checking
Would it catch unsupported or conflicting requests earlier?

### Refactor Cost
How disruptive would this be to current code?

### Extensibility
Would it make it easier to add new analysis patterns later?

### Testing
Would it improve unit/integration testability of the prompt-to-plan layer?

---

## Proposed First-Pass Capability Graph for Evaluation

Codex can use this as an initial conceptual model.

### Domain nodes
- descriptive
- comparative
- ranking
- trend
- diagnostic
- predictive
- segmentation
- distribution

### Pattern nodes
- grouped_breakdown
- contribution_breakdown
- top_n_by_metric
- bottom_n_by_metric
- period_over_period_comparison
- peer_group_comparison
- grouped_trend
- cumulative_trend
- growth_ranking
- variance_analysis
- anomaly_scan
- forecast_series
- segmented_forecast

### Primitive nodes
- select_dataset
- resolve_metric
- resolve_dimension
- filter
- filter_period
- time_bucket
- group_by
- aggregate
- derive_metric
- derive_growth
- compare_periods
- compare_groups
- sort
- limit
- window
- segment
- forecast

### Constraint examples
- requires_metric
- requires_dimension
- requires_time_field
- requires_reference_period
- output_shape_ranked_table
- output_shape_time_series

---

## Example Interpretation Model

A prompt should activate a candidate subgraph, not just a single label.

Example prompt:

> Show top 5 provinces by revenue growth this quarter.

Possible activated nodes:

- ranking
- comparative
- growth_ranking
- filter_period
- aggregate
- derive_growth
- sort
- limit

Required parameters:

- metric = revenue
- dimension = province
- period = this_quarter
- reference period = previous_quarter or explicit comparison basis
- limit = 5

The contract layer should validate whether this set forms a legal supported subgraph before compiling into a canonical plan.

---

## Example Codex Task Instructions

Use the following as a direct task instruction for Codex:

### Task
Analyze the current Saida codebase with a focus on the prompt-to-LLM-to-analysis-plan section. Identify why prompt mismatches, capability mismatches, and data mismatches are occurring. Then evaluate whether a capability-graph architecture would improve the system.

### Objectives
1. Trace the current prompt-to-plan pipeline end to end.
2. Identify all major mismatch/error sources.
3. Inventory current high-level capabilities and low-level primitives.
4. Determine whether the current code can support a capability graph refactor.
5. Compare the graph approach against the existing direct prompt-to-plan approach.
6. Produce an acceptability analysis and an incremental migration plan.

### Constraints
- Do not assume the graph already exists.
- Base findings on actual code structure.
- Distinguish between what exists, what is implied, and what is missing.
- Separate reusable abstractions from rewrite-required areas.
- Focus on deterministic plan generation and validation.

### Output format
Return the analysis in this structure:

1. Executive summary
2. Current architecture map
3. Error taxonomy
4. Capability inventory
5. Current design weaknesses
6. Capability graph fit assessment
7. Acceptability analysis
8. Recommended migration path
9. Immediate high-priority fixes

---

## Immediate High-Priority Fixes Codex Should Look For

Before a full graph refactor, Codex should also identify quick wins such as:

- missing schema validation in the plan layer
- absent alias/normalization dictionaries
- prompt instructions that overreach system capability
- lack of required-parameter checks
- no distinction between unsupported and ambiguous requests
- direct plan generation without intermediate validation
- brittle coupling between prompt wording and plan shape

---

## Final Framing

The key proposal is this:

Saida should move away from treating prompt interpretation as a direct text-to-plan generation problem, and instead treat it as a **capability graph activation and validation problem**.

The LLM should help activate candidate nodes and extract parameters, but it should not be the sole authority on final executable plan structure.

The final analysis plan should come from a validated capability contract and deterministic compilation path.

This is the core idea Codex should evaluate against the current codebase.

