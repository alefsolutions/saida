from saida import PromptAnalysisFrontend
from saida.sources import CSVSource


dataset = CSVSource("examples/sales.csv", context_path="examples/sales_context.md").load()
result = PromptAnalysisFrontend().analyze(dataset, "Why did revenue drop in March by region?")

print(result.summary)
print("Tables:", ", ".join(table.name for table in result.tables))
