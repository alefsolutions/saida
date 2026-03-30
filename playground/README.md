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
  - `run/run_prompt_analysis.py`: OpenAI prompt-driven analysis over the 40-row SQLite dataset
- `example3/`
  - `data/`: SQLite database and markdown context
  - `run/run_authored_plan.py`: pure `AnalysisPlan -> execute_plan -> AnalysisResult` example that prints JSON

## Run

Example 1:

```powershell
python playground/example1/run/run_prompt_analysis.py
```

Example 2:

```powershell
python playground/example2/run/run_prompt_analysis.py
```

Example 3:

```powershell
python playground/example3/run/run_authored_plan.py
```
