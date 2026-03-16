![SAIDA Banner](assets/github-banner.png)

# SAIDA Compute Capabilities

This document lists the computation types the current SAIDA engine supports.

The current repo build is centered on the deterministic non-ML analytics core.

---

## Support Strength

### Strongest Support

These are the current areas where SAIDA is most reliable and most mature:

- deterministic descriptive aggregation
- grouped aggregation and ranked grouped breakdowns
- distinct value listing for dimension columns
- row counts and grouped row-count ranking
- metadata inventory queries
- month-based time trends and adjacent period comparison
- contribution analysis and top movers
- time coverage inspection
- statistical summaries
- core formal statistical testing
- standardized analytical response packaging

### Moderate Support

These are useful and working, but still benefit from clearer prompting or some maturity work:

- LLM-assisted prompt interpretation
- LLM-assisted response wording
- confidence interval workflows
- regression significance workflows
- p-value-driven significance workflows
- observed power analysis
- sample-size estimation
- context-aware semantic resolution for analysis planning

### Weakest Support

These are the current areas with the most visible limits:

- broader natural-language time phrasing
- open-ended ranking phrasing
- open-ended comparison phrasing
- open-ended factor-selection prompts
- arbitrary natural-language SQL-style requests
- ML training, prediction, and forecasting

---

## DuckDB Compute

The DuckDB layer currently supports:

- dataset summary
- scalar aggregation:
  - sum
  - mean
  - max
  - min
  - count
- grouped aggregation
- ranked grouped breakdowns
- row counts
- row counts by group
- distinct value listing for dimension columns
- time trends by month
- adjacent period comparison for month-based requests
- grouped period comparison
- top movers between adjacent periods
- contribution breakdowns
- time coverage inspection:
  - years present
  - months present
  - date range

### Typical prompt shapes

- `What is the average revenue?`
- `Give me total revenue by region`
- `Which segment is the least represented?`
- `What are the different priority categories in the data?`
- `Why did revenue drop in March?`
- `The data shows revenue for which years?`

---

## Stats Compute

The stats layer currently supports:

- missingness summary
- numeric summary
- distribution summary
- correlation analysis
- anomaly detection
- time-series diagnostics
- group mean comparison

### Statistical testing

The current repo build also supports:

- Welch t-tests
- chi-square tests
- one-way ANOVA
- Mann-Whitney tests
- confidence intervals for a mean
- regression coefficient significance testing
- p-value-driven group significance workflows
- observed power analysis for two-group comparisons
- sample-size estimation for two-group comparisons

### Typical prompt shapes

- `Run a t-test for revenue by region`
- `Run chi-square test for segment and region`
- `Run ANOVA for revenue by team`
- `Run Mann-Whitney test for csat_score by reopened_flag`
- `What is the 95% confidence interval for revenue?`
- `Is revenue by region statistically significant?`
- `Run regression significance test for shipping_cost using parcel_count`
- `Run power analysis for resolution_hours by reopened_flag`
- `Estimate sample size for revenue by channel`

---

## Metadata Compute

The engine also supports metadata-style outputs through deterministic planning:

- column inventory
- measure inventory
- dimension inventory
- time column inventory

### Typical prompt shapes

- `What are the columns in the sales data?`
- `What measure columns are available?`
- `What time columns are available?`

---

## Response Contract

All successful computations are packaged into a standardized analytical response contract that includes:

- resolved intent
- plan and operations
- metric lookup
- output tables
- warnings
- trace events
- deterministic summary
- optional LLM summary

---

## Current Limits

The current repo build still has important boundaries:

- ML training, prediction, and forecasting are not implemented yet
- time execution is still strongest for month-based requests
- broader relative-period expressions are still limited
- some natural-language ranking and comparison phrasing still needs expansion
- open-ended automatic factor selection is still limited for some statistical prompts
- SAIDA does not support arbitrary natural-language SQL generation

---

## V1 Practical Summary

Current SAIDA V1 is strongest as:

- a deterministic descriptive analytics engine
- a deterministic diagnostic analytics engine
- a deterministic statistics and inference engine
- an optional LLM-assisted analytical interface

It is not yet a complete ML-enabled analytics library because:

- `train(...)`
- `predict(...)`
- `forecast(...)`

remain intentionally deferred.
