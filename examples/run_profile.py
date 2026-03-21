from saida import Saida
from saida.sources import CSVSource


dataset = CSVSource("examples/sales.csv", context_path="examples/sales_context.md").load()
profile = Saida().profile(dataset)

print("Dataset:", profile.dataset_name)
print("Measures:", ", ".join(profile.measure_columns) or "none")
print("Dimensions:", ", ".join(profile.dimension_columns) or "none")
print("Time columns:", ", ".join(profile.time_columns) or "none")
