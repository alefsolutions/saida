![SAIDA Banner](../assets/github-banner.png)

# SAIDA Docs

[![Version](https://img.shields.io/badge/version-0.3.0-1f6feb)](../pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-2ea043)](../LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)](../pyproject.toml)

Start here if you want the bigger picture behind the framework.

Core idea:

- input: `AnalysisPlan`
- output: `AnalysisResult`

Prompt and LLM features are documented too, but they are optional frontend layers.

## Recommended Reading Order

1. [Architecture](./overview/architecture.md)
2. [AnalysisPlan API Reference](./reference/analysis-plan-api.md)
3. [API Usage](./reference/api-usage.md)
4. [Schema Spec](./reference/schema-spec.md)
5. [DAG Plan Authoring](./guides/dag-plan-authoring.md)
6. [File Structure](./overview/file-structure.md)

## Reference

- [AnalysisPlan API Reference](./reference/analysis-plan-api.md)
- [Prompt Family Catalog](./reference/prompt-family-catalog.md)

## Guides

- [Prompt Playbook](./guides/prompt-playbook.md)
- [DAG Plan Authoring](./guides/dag-plan-authoring.md)

## Internal Notes

- [Prompt Capability Architecture Note](./internal/prompt-capability-architecture-note.md)
- [Things To Add / Wishlist](./internal/things-to-add-or-wishlist.md)
- [Capability Graph Analysis Plan](./internal/saida-capability-graph-codex-analysis-plan.md)
