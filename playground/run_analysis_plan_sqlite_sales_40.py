from pathlib import Path
import json
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from _env import load_project_env
from saida import Saida
from saida.core.contracts import AnalysisPlan, PlanInput, PlanStep, StepInputRef, StepOutputSpec
from saida.sources import SQLiteSource


DEFAULT_DATABASE_PATH = PROJECT_ROOT / "examples" / "sqlite_sales_40" / "sales_sqlite_40.db"
DEFAULT_CONTEXT_PATH = PROJECT_ROOT / "examples" / "sqlite_sales_40" / "sales_sqlite_40.md"
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


def _print_result_rows(result: object) -> None:
    payload = result.to_response_dict()
    rows = payload.get("result", {}).get("value", [])
    if not isinstance(rows, list):
        print("Result:", rows)
        return
    for index, row in enumerate(rows, start=1):
        if isinstance(row, dict):
            parts = [f"{key}={value}" for key, value in row.items()]
            print(f"{index}. " + " | ".join(parts))
        else:
            print(f"{index}. {row}")


def main() -> None:
    load_project_env(PROJECT_ROOT)

    dataset = SQLiteSource(
        DEFAULT_DATABASE_PATH,
        DEFAULT_QUERY,
        name="sales_sqlite_40",
        context_path=DEFAULT_CONTEXT_PATH,
    ).load()

    plan = build_first_five_rows_plan(dataset.name)
    engine = Saida()
    result = engine.execute_plan(dataset, plan)

    print("SAIDA SQLite authored AnalysisPlan playground")
    print(f"Dataset: {dataset.name}")
    print()
    print("AnalysisPlan JSON:")
    print(json.dumps(plan.to_dict(), indent=2))
    print()
    print("Result summary:")
    print(result.summary)
    print()
    print("Rows:")
    _print_result_rows(result)


if __name__ == "__main__":
    main()
