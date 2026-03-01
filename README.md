# SAIDA.ai (Core)

<p align="left">
  <img src="assets/logo.png" alt="SAIDA.ai logo" width="300" />
</p>

**Strategic Artificial Intelligence for Data & Analytics**

SAIDA.ai Core is an open-core intelligence engine designed to turn structured and unstructured business data into actionable executive insights.

It combines:

- Heavy data analytics pipelines
- LLM-based reasoning
- Retrieval-augmented generation (RAG)
- Tool orchestration
- Model routing
- Connector abstraction

SAIDA Core is built for developers, data teams, and organizations that want to build intelligent systems over business data while maintaining full architectural control.

## Vision

SAIDA.ai Core exists to bridge the gap between raw business data and strategic decision-making intelligence.

Instead of dashboards alone, SAIDA enables natural language analysis over:

- Financial data
- Sales and operational databases
- PDFs and reports
- Spreadsheets
- Knowledge repositories

The result is an AI engine capable of acting as a strategic analyst grounded in real data.

## Architecture Overview

SAIDA.ai Core is modular and model-agnostic.

```text
User Query
  -> Intent Routing
  -> Tool Selection
  -> Data Retrieval (Database / Local Drive / Cloud Drive / Vector Search)
  -> Analytics + LLM Reasoning Layer
  -> Structured Executive Output
```

Core components:

- Agent Orchestration
- Model Router (multi-LLM support)
- Tool Interface Layer
- Connector Abstraction
- Retrieval Engine
- Analytics Engine
- Embedding Layer
- Vector Store Integration

## Core Capabilities

### 1. Heavy Data Analytics

SAIDA Core is not only a reasoning layer. It is built to execute data-heavy analytical workflows before synthesis.

It supports:

- Structured query execution
- Metric computation and aggregation
- Cross-source data joins
- Time-series and comparative analysis
- Explainable analytics outputs for executive decisions

### 2. Model-Agnostic Reasoning

Supports multiple model providers:

- OpenAI
- Self-hosted open-weight models
- Future provider integrations

Route lightweight tasks to smaller models and complex tasks to larger models.

### 3. Connector Framework

A standardized connector interface enables integration with:

- Local drive data sources
- Google Drive files and folders
- SQL and warehouse databases
- API-based services

Connectors are modular, extensible, and tool-ready.

### 4. Retrieval-Augmented Generation (RAG)

- Document chunking
- Embedding abstraction
- Vector store support
- Hybrid retrieval
- Metadata filtering

### 5. Tool-Oriented Agent Design

SAIDA agents do not hallucinate raw numbers.

They:

- Call tools
- Execute structured queries
- Retrieve verified context
- Generate explainable answers

### 6. Multi-Model Routing

Lightweight models handle:

- Classification
- Summarization
- Parsing
- Formatting

Heavy models handle:

- Strategic synthesis
- Deep financial reasoning
- Multi-document inference

## Data Connectivity

SAIDA Core is designed to connect directly to your data.

Current focus:

- Local drive integration for file-based analysis
- Google Drive integration for document retrieval and processing
- Database integration for structured analytics (SQL-first)

To support these integrations, the core includes:

- Connector abstraction interfaces
- Authentication and connection hooks at the connector level
- Tool contracts for consistent query/retrieval execution
- Retrieval pipelines that unify documents and structured data

## What SAIDA Core Includes

Open-source core provides:

- Agent orchestration engine
- Data analytics execution layer
- Model routing layer
- Tool abstraction framework
- Base connector interfaces
- Retrieval logic
- Embedding wrappers
- CLI execution mode
- Local development setup

## What SAIDA Core Does NOT Include

The open-source core does not include:

- Multi-tenancy
- Enterprise authentication
- RBAC
- Audit logging
- Billing systems
- SaaS dashboard
- Managed cloud deployment scripts
- Enterprise connectors
- SLA-backed hosting

These features are part of the commercial SAIDA Enterprise platform.

## Installation

```bash
git clone https://github.com/your-org/saida-core.git
cd saida-core
pip install -e .
```

Set environment variables:

```bash
export OPENAI_API_KEY=your_key
```

Run locally:

```bash
python -m saida_core.cli
```

## Example Usage

```python
from saida import SaidaAgent

agent = SaidaAgent()

response = agent.ask(
    "Why did revenue decline in Q3 compared to Q2?"
)

print(response)
```

## Design Philosophy

SAIDA.ai Core is built on simplicity and transparency.

Its core principles are:

- Simplicity in architecture, workflows, and developer experience
- Transparency in data flow, tool usage, and reasoning outputs
- Tool-first reasoning over hallucination
- Heavy analytics before narrative synthesis
- Modular architecture
- Provider independence
- Production extensibility

## Use Cases

- Financial intelligence systems
- Executive AI assistants
- AI-powered BI platforms
- Internal analytics copilots
- Compliance-aware AI agents
- Document + database hybrid reasoning systems

## License

SAIDA.ai Core is licensed under the Apache License 2.0.

You are free to:

- Use
- Modify
- Distribute
- Commercialize derivatives

Subject to the terms of the license.

## Enterprise Version

SAIDA Enterprise includes:

- Multi-tenant SaaS architecture
- Enterprise authentication (OAuth, SSO)
- Role-based access control
- Audit logs
- Usage analytics
- Data export tools
- Managed hosting
- Premium connectors
- SLA-backed support

For enterprise licensing or hosted deployments:

`hello@alefpng.com`

## Roadmap

- Enhanced model routing
- Pluggable policy engine
- Fine-tuning support
- Connector marketplace
- Governance and compliance layer
- Enterprise on-prem deployment support

## Contribution

We welcome community contributions.

To contribute:

- Fork the repository
- Create a feature branch
- Submit a pull request

All contributions must align with project architecture principles.

## About

SAIDA stands for Strategic Artificial Intelligence for Data & Analytics.

It is designed to move beyond dashboards into real AI-assisted executive reasoning grounded in analytics.
