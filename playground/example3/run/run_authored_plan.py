from pathlib import Path
import json
import sys


EXAMPLE_ROOT = Path(__file__).resolve().parents[1]
PLAYGROUND_ROOT = EXAMPLE_ROOT.parents[0]
PROJECT_ROOT = EXAMPLE_ROOT.parents[1]
SRC_PATH = PROJECT_ROOT / "src"
for path in (SRC_PATH, PLAYGROUND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from _env import load_project_env
from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec
from saida.sources import SQLiteSource


DEFAULT_DATABASE_PATH = EXAMPLE_ROOT / "data" / "sales_sqlite_40.db"
DEFAULT_CONTEXT_PATH = EXAMPLE_ROOT / "data" / "sales_sqlite_40.md"
DEFAULT_QUERY = "SELECT * FROM sales_orders"


def build_first_five_rows_plan(dataset_name: str = "sales_sqlite_40") -> AnalysisPlan:
    return AnalysisPlan(
        task_type="descriptive",
        rationale="Return the first five dataset rows using an explicit authored AnalysisPlan.",
        plan_id=f"{dataset_name}:authored:first-five-rows",
        dataset_refs=[dataset_name],
        inputs=[PlanInput(input_id="primary_dataset", kind="dataset", ref=dataset_name)],
        expected_result_name="first_five_rows",
        expected_result_shape="recordset",
        final_output_ref="first_five_rows",
        steps=[
            PlanStep(
                step_id="first_five_rows",
                tool_family="duckdb",
                action="tabular_query",
                method_id="tabular_query",
                family="projection_field_selection",
                parameters={
                    "sort_by": "order_date",
                    "sort_direction": "asc",
                    "page": 1,
                    "page_size": 5,
                },
                description="Return the first five rows ordered by order_date ascending.",
                inputs=[
                    StepInputRef(
                        input_id="dataset_input",
                        source_type="plan_input",
                        ref="primary_dataset",
                        expected_kind="dataset",
                    )
                ],
                output_refs=["first_five_rows"],
                outputs=[
                    StepOutputSpec(
                        output_id="first_five_rows",
                        kind="frame",
                        logical_shape="recordset",
                        physical_shape="recordset",
                    )
                ],
                expected_output={
                    "output_id": "first_five_rows",
                    "logical_shape": "recordset",
                    "physical_shape": "recordset",
                },
            )
        ],
    )


def main() -> None:
    load_project_env(PROJECT_ROOT)

    dataset = SQLiteSource(
        DEFAULT_DATABASE_PATH,
        DEFAULT_QUERY,
        name="sales_sqlite_40",
        context_path=DEFAULT_CONTEXT_PATH,
    ).load()

    result = Saida().execute_plan(dataset, build_first_five_rows_plan(dataset.name))
    print(json.dumps(result.to_response_dict(), indent=2))


if __name__ == "__main__":
    main()
