![SAIDA Banner](assets/github-banner.png)

# SAIDA Library Usage

SAIDA is used as a Python library.

Example:

```python
from saida import Saida
from saida.adapters import CSVAdapter

engine = Saida()

dataset = CSVAdapter("data.csv").load()

result = engine.analyze(
    dataset=dataset,
    question="Why did revenue drop in March?"
)

print(result.summary)
print(result.to_response_dict())
```

The current non-ML build supports month-based time references reliably. Quarter-style prompts are documented as future work.
For the exact current compute surface, see [Compute Capabilities](COMPUTE_CAPABILITIES.md).

When an optional LLM provider is configured, SAIDA lets the model interpret the prompt first and then validates that proposal against the dataset profile and context before creating an `AnalysisRequest`.
The normalized request can now carry supported aggregation intents such as `sum`, `mean`, `max`, `min`, and `count`.

Aggregation-style prompts are supported by the deterministic core as well:

```python
result = engine.analyze(
    dataset=dataset,
    question="What is the average revenue?"
)

print(result.summary)
```

Distinct-value prompts are supported for dimension columns as well:

```python
result = engine.analyze(
    dataset=dataset,
    question="Give me a list of all segments"
)

print(result.summary)
# Available segment values: Enterprise, SMB.
```

Other deterministic intent examples:

```python
engine.analyze(dataset=dataset, question="How many data rows do we have?")
engine.analyze(dataset=dataset, question="Which segment is the least represented?")
engine.analyze(dataset=dataset, question="What are the columns in the sales data?")
```

Statistical workflows are also supported:

```python
engine.analyze(dataset=dataset, question="Run a t-test for revenue by region")
engine.analyze(dataset=dataset, question="Do regions differ in revenue?")
engine.analyze(dataset=dataset, question="Run chi-square test for segment and region")
engine.analyze(dataset=dataset, question="Run ANOVA for revenue by team")
engine.analyze(dataset=dataset, question="What is the 95% confidence interval for revenue?")
engine.analyze(dataset=dataset, question="What range are we 95% confident revenue falls in?")
engine.analyze(dataset=dataset, question="Is revenue by region statistically significant?")
engine.analyze(dataset=dataset, question="Do we have enough data to detect a difference in revenue by region?")
engine.analyze(dataset=dataset, question="Does parcel_count significantly affect shipping_cost?")
```

Current practical limits:

- month-based time execution is the strongest supported time workflow
- broader time phrasing and rolling-window execution are still limited
- some natural-language ranking phrasing still needs expansion
- open-ended prompts like `Which factors significantly affect customer satisfaction?` still work best when predictor columns are named explicitly

Grouped aggregation prompts are summarized directly from grouped results, for example:

```python
result = engine.analyze(
    dataset=dataset,
    question="Give me the total revenue by region"
)

print(result.summary)
# Total revenue by region: region=West = 397.00; region=East = 350.00.
```

`result.to_response_dict()` returns the standardized analytical response contract. It includes:
- original question
- resolved intent
- plan and operations
- computed metric lookup
- output table metadata
- deterministic summary
- optional LLM summary
- summary source
- warnings and trace events

---

# Profile Example

```python
profile = engine.profile(dataset)

print(profile.measure_columns)
print(profile.time_columns)
```

---

# Capabilities Example

```python
engine.capabilities()
```

Current output in this repo build:

```python
{
    "analyze": True,
    "profile": True,
    "load_context": True,
    "train": False,
    "predict": False,
    "forecast": False,
    "llm_prompting": False,
    "llm_reasoning": False,
}
```

---

# Local CLI Example

```bash
$env:PYTHONPATH="src"
python -m saida.cli.main analyze --csv examples/sales.csv --context examples/sales_context.md --question "Why did revenue drop in March?"
```

Optional LLM-enhanced CLI example:

```bash
$env:PYTHONPATH="src"
python -m saida.cli.main analyze --csv examples/sales.csv --question "Why did revenue drop in March?" --llm-provider ollama --llm-model llama3.1
```

---

# ML Methods

```python
engine.train(...)
engine.predict(...)
engine.forecast(...)
```

These methods are intentionally not implemented yet in the current repo build.

