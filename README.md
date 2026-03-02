<p align="center">
  <img src="assets/banner.png" alt="SAIDA Banner" />
</p>

# SAIDA (Core)
## Specification Document
### A Deterministic, Measurable Intelligence Framework for Cluttered Data

---

# 1. Purpose

SAIDA is a Python intelligence framework that provides a structured intelligence layer over heterogeneous, cluttered data sources.

SAIDA must:

- Ingest structured and unstructured data
- Normalize tabular data into a canonical format
- Provide deterministic analytics
- Provide semantic retrieval
- Provide controlled LLM reasoning
- Provide measurable intelligence metrics
- Remain fully configurable and extensible
- Remain transport-agnostic (not tied to APIs)

SAIDA is a library, not a service.

---

# 2. Delivery Model

SAIDA must be delivered as:

- A Python package (`saida`)
- Installable via pip
- Importable into any Python script or application
- Usable via direct Python code
- Independent of web frameworks
- Independent of background daemons

SAIDA must not assume:

- FastAPI
- HTTP servers
- Background workers
- Multiprocessing runtimes
- Thread pools
- Continuous file watchers

All execution must be explicitly triggered by the caller.

---

# 3. Core Architectural Principles

SAIDA must strictly separate:

1. Deterministic computation (Analytics)
2. Semantic retrieval (Vector layer)
3. LLM reasoning (Language layer)
4. Metadata management (Control plane)
5. Orchestration (Workflow layer)
6. Evaluation (Benchmarking subsystem)

These responsibilities must not be mixed.

---

# 4. High-Level System Architecture

User Script
    ->
SaidaAgent
    ->
Orchestration Layer (LangChain)
    ->
Query Router
    ->
[Semantic Retrieval Layer]
    ->
[Analytics Layer (DuckDB)]
    ->
[LLM Reasoning Layer]
    ->
Structured Response Object

---

# 5. Subsystems Overview

SAIDA must include the following subsystems:

1. Agent Subsystem  
2. Connector Subsystem  
3. Ingestion Subsystem  
4. Storage Subsystem  
5. Analytics Subsystem  
6. Semantic Subsystem  
7. LLM Subsystem  
8. Embedding Subsystem  
9. Orchestration Subsystem  
10. Benchmarking & Evaluation Subsystem  

Each subsystem must:

- Be modular
- Be independently testable
- Expose clear interfaces
- Avoid hidden runtime behavior

---

# 6. Agent Subsystem

## SaidaAgent

SaidaAgent is the primary entry point to the SAIDA framework.

Responsibilities:

- Register connectors
- Register LLM provider
- Register embedding provider
- Register compute engine
- Manage configuration
- Trigger ingestion
- Execute queries
- Trigger benchmarking

Required public methods:

- agent.add_connector(connector)
- agent.ingest_all()
- agent.sync()
- agent.query(prompt)
- agent.run_benchmarks()

SaidaAgent must not:

- Spawn background loops
- Automatically monitor file systems
- Assume concurrency models
- Run schedulers internally

All ingestion and execution must be explicit.

---

# 7. Connector Subsystem

Connectors abstract data sources.

All connectors must implement a common interface.

class BaseConnector:
    def discover(self) -> list:
        """Return list of resource identifiers available for ingestion."""

    def load(self, resource_id):
        """Return raw content or structured content for a resource."""

    def get_metadata(self):
        """Return metadata about the source system."""

Supported connector types must include:

- FileSystemConnector
- GoogleDriveConnector
- PostgresConnector
- MySQLConnector

Connector design constraints:

- Must be stateless
- Must not manage background threads
- Must not persist data directly
- Must delegate storage to ingestion subsystem

---

# 8. Ingestion Subsystem

The Ingestion Subsystem transforms raw data into canonical internal representations.

Responsibilities:

- Parse documents (PDF, DOCX, TXT)
- Parse spreadsheets (XLSX, CSV, JSON)
- Convert tabular data to Parquet
- Profile schemas
- Generate semantic summaries
- Compute dataset hashes
- Detect changes via version/hash comparison
- Store metadata in PostgreSQL
- Generate embeddings

Ingestion must be:

- Idempotent
- Deterministic
- Explicitly invoked

Ingestion must not:

- Run continuously
- Poll connectors automatically
- Spawn threads or workers internally

---

# 9. Storage Subsystem

## PostgreSQL (Control Plane + Semantic Layer)

PostgreSQL must be used for:

- Dataset registry
- Schema definitions
- Column metadata
- Data profiling statistics
- Execution logs
- Benchmark results
- Vector embeddings (via pgvector)

Schema management must use ORM (e.g., SQLAlchemy + Alembic).

---

## Parquet (Tabular Storage Layer)

All tabular data must be converted to Parquet.

Parquet serves as:

- Canonical tabular representation
- Immutable dataset version storage
- Input to DuckDB analytics engine

SAIDA must not create uncontrolled PostgreSQL tables per spreadsheet.

---

# 10. Analytics Subsystem

## DuckDB

DuckDB must be the deterministic compute engine.

Responsibilities:

- Execute SQL queries
- Perform aggregations (SUM, AVG, COUNT, etc.)
- Perform joins
- Perform group-by operations
- Perform window functions
- Query Parquet files
- Attach external SQL databases for federated analytics

Critical Rule:

LLM must never compute numeric results.

All numeric results must originate from DuckDB execution.

---

# 11. Semantic Subsystem

Implemented using PostgreSQL + pgvector.

Responsibilities:

- Store document embeddings
- Store dataset summaries
- Store schema descriptions
- Support retrieval
- Support column grounding
- Support dataset discovery

Embeddings must be provider-agnostic.

---

# 12. LLM Subsystem

LLM must be pluggable.

Responsibilities:

- Interpret natural language queries
- Generate SQL plans (optional)
- Produce explanations
- Perform semantic enrichment

LLM must not:

- Execute SQL
- Compute numeric results
- Access databases directly

---

# 13. Orchestration Subsystem

Must use LangChain.

Responsibilities:

- Query classification
- Tool routing
- Retrieval chaining
- SQL planning
- Explanation generation

LLM must never bypass analytics or semantic layers.

---

# 14. No Background Runtime in Core

SAIDA Core must not implement:

- Multiprocessing ingestion
- Background file watchers
- Continuous polling
- Task schedulers

Background ingestion is considered deployment-level functionality.

---

# 15. Benchmarking & Evaluation Subsystem

The Benchmarking Subsystem measures SAIDA's intelligence.

It must:

- Use the same execution pipeline as production
- Run predefined benchmark datasets
- Compare outputs to expected results
- Compute intelligence scores
- Persist results in PostgreSQL
- Produce CLI and JSON reports

---

## Intelligence Dimensions

Analytical Intelligence Score (AIS):
(Correct Analytical Results / Total Analytical Tests) x 100

Semantic Intelligence Score (SES):
(Correct Semantic Matches / Total Semantic Tests) x 100

Reasoning Intelligence Score (RIS):
(Faithful Explanations / Total Explanations) x 100

System Stability Score (SSS):
(Successful Executions / Total Executions) x 100

Composite SAIDA Intelligence Score:
0.40 x AIS
+ 0.30 x SES
+ 0.20 x RIS
+ 0.10 x SSS

Weights must be configurable.

---

# 16. Project Structure

saida/
  agent/
  connectors/
  ingestion/
  storage/
  analytics/
  semantic/
  llm/
  embeddings/
  orchestration/
  benchmarking/
  models/
  utils/

Each folder must correspond to a subsystem defined above.

---

# 17. Production Readiness Criteria

Minimum thresholds:

- AIS >= 95%
- SES >= 90%
- RIS >= 90%
- SSS >= 95%

---

# 18. Definition of SAIDA

SAIDA is:

A deterministic, measurable, modular intelligence framework.

It is defined by:

- Correctness
- Reproducibility
- Measurability
- Configurability
- Extensibility
