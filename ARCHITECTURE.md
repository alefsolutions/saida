
# SAIDA Architecture (Canonical Analytics Framework)

## 1. Overview
SAIDA standardizes analysis:
- Input → Canonical `AnalysisPlan`
- Output → Canonical `AnalyticalResult`
- Compute → External libraries (DuckDB, pandas, statsmodels, etc.)

Core principle:
- SAIDA defines meaning
- Backends perform computation

---

## 2. Layered Architecture

### Layer 1: Input Layer
- Accepts:
  - prompt
  - API input
  - direct JSON plan

### Layer 2: Canonicalization Layer
- Converts input → `AnalysisPlan`
- Resolves:
  - synonyms
  - fields
  - intent

### Layer 3: Validation Layer
- Validates:
  - schema
  - required fields
  - task types

### Layer 4: Routing Layer
- Chooses backend:
  - DuckDB → SQL analytics
  - pandas → dataframe ops
  - statsmodels → statistical models
  - GeoPandas → spatial

### Layer 5: Adapter Layer
- Translates plan → backend logic

### Layer 6: Execution Layer
- Backend performs computation

### Layer 7: Result Canonicalization
- Converts output → `AnalyticalResult`
- Enforces:
  - shape
  - schema
  - types

### Layer 8: Output Layer
- Formats:
  - JSON
  - CSV
  - Excel
  - XML
  - SQL

---

## 3. Data Sources (Multi-Source)

Supported:
- CSV
- Excel
- PostgreSQL
- MySQL
- Microsoft Access
- GIS (GeoJSON, shapefiles)

Features:
- multiple sources
- optional relationships
- canonical schema per source

---

## 4. Compute Adapters

Default:
- DuckDB
- pandas / Polars
- statsmodels
- GeoPandas
- scikit-learn / TensorFlow (ML)

---

## 5. LLM Layer (Optional)

Modes:
- no LLM
- one LLM (input + output)
- two LLMs (separate)

Rules:
- LLM never executes
- LLM only produces structured plans

---

## 6. Canonical Contracts

### AnalysisPlan
- structured
- deterministic
- multi-step support

### AnalyticalResult
Must include:
- result_type
- schema
- data
- metadata

---

## 7. Data Shapes

Supported:
- scalar
- vector
- table
- matrix
- time_series
- distribution
- spatial

---

## 8. Codex Instructions

### Goal
Generate clean, simple, modular code.

### Rules (Zen of Python)
- simple > complex
- explicit > implicit
- readability counts
- no over-engineering

### Structure
- saida/
  - core/
  - adapters/
  - sources/
  - outputs/
  - llm/
  - tests/

---

## 9. Testing Strategy

### Per Layer
- Input tests
- Plan validation tests
- Adapter execution tests
- Result normalization tests

### Types
- unit tests
- integration tests
- snapshot tests (for outputs)

---

## 10. Summary

SAIDA:
- standardizes analysis
- separates meaning from computation
- enables reproducibility
- supports multi-source + multi-backend
