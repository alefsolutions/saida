# SAIDA.ai (Core)

<p align="left">
  <img src="assets/logo.png" alt="SAIDA.ai logo" width="180" />
</p>


**Strategic Artificial Intelligence for Data & Analytics**

SAIDA.ai is an open-core AI intelligence engine designed to transform structured and unstructured business data into actionable executive insights.

It combines:

- LLM-based reasoning
- Retrieval-augmented generation (RAG)
- Structured data analytics
- Tool orchestration
- Model routing
- Connector abstraction

SAIDA.ai is built for developers, data teams, and organizations who want to build intelligent AI systems over business data, while maintaining full architectural control.

## Vision

SAIDA.ai exists to bridge the gap between raw business data and strategic decision-making intelligence.

Instead of dashboards alone, SAIDA enables natural language reasoning over:

- Financial data
- Sales databases
- PDFs
- Reports
- Spreadsheets
- Knowledge repositories

The result is an AI engine capable of acting as a strategic analyst.

## Architecture Overview

SAIDA.ai is modular and model-agnostic.

```text
User Query
    ?
Intent Routing
    ?
Tool Selection
    ?
Data Retrieval (SQL / Drive / Vector Search)
    ?
LLM Reasoning Layer
    ?
Structured Executive Output
```

Core components:

- Agent Orchestration
- Model Router (multi-LLM support)
- Tool Interface Layer
- Connector Abstraction
- Retrieval Engine
- Embedding Layer
- Vector Store Integration

## Core Capabilities

### 1. Model-Agnostic Reasoning

Supports multiple LLM providers:

- OpenAI
- Self-hosted open-weight models
- Future provider integrations

Route light tasks to smaller models and heavy reasoning to larger models.

### 2. Connector Framework

Standardized connector interface enables integration with:

- SQL databases
- File storage systems
- Cloud drives
- API-based services

Connectors are modular and extensible.

### 3. Retrieval-Augmented Generation (RAG)

- Document chunking
- Embedding abstraction
- Vector store support
- Hybrid retrieval
- Metadata filtering

### 4. Tool-Oriented Agent Design

SAIDA agents do not hallucinate raw numbers.

They:

- Call tools
- Execute structured queries
- Retrieve verified context
- Generate explainable answers

### 5. Multi-Model Routing

Lightweight models handle:

- Classification
- Summarization
- Parsing
- Formatting

Heavy models handle:

- Strategic synthesis
- Deep financial reasoning
- Multi-document inference

## What SAIDA Core Includes

Open-source core provides:

- Agent orchestration engine
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

SAIDA.ai is built on five principles:

- Tool-first reasoning over hallucination
- Modular architecture
- Provider independence
- Cost-aware model routing
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

`contact@saida.ai`

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

It is designed to move beyond dashboards into real AI-assisted executive reasoning.
