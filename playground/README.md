![SAIDA Banner](../assets/github-banner.png)

# Playground Scenarios

[![Version](https://img.shields.io/badge/version-0.3.0-1f6feb)](../pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-2ea043)](../LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)](../pyproject.toml)

This folder contains runnable scenario-based playgrounds.

## Layout

- `example1/`
  - `data/`: CSV dataset and markdown context
  - `run/run_prompt_analysis.py`: OpenAI prompt-driven analysis over the 800-row sales CSV
- `example2/`
  - `data/`: SQLite database and markdown context
  - `run/run_prompt_analysis.py`: OpenAI prompt-driven analysis over the SQLite source-aware flow
- `example3/`
  - `data/`: SQLite database and markdown context
  - `run/run_authored_plan.py`: pure `AnalysisPlan -> execute_plan -> AnalysisResult` example that prints JSON
- `example4/`
  - `data/`: markdown context plus a runtime-built multi-table SQLite warehouse
  - `run/run_prompt_analysis.py`: OpenAI prompt-driven analysis over a richer relational schema

## Run

Example 1:

```powershell
python playground/example1/run/run_prompt_analysis.py
```

Example 2:

```powershell
python playground/example2/run/run_prompt_analysis.py
```

Example 2 now uses `PromptAnalysisFrontend.analyze_source(...)`, so the playground exercises schema discovery and source-side materialization before the core runtime executes the final plan.

Example 3:

```powershell
python playground/example3/run/run_authored_plan.py
```

Example 4:

```powershell
python playground/example4/run/run_prompt_analysis.py
```
