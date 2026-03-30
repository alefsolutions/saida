from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd
import pytest

from saida.sources import CSVAdapter, ExcelAdapter, JSONAdapter, PandasAdapter, SQLAdapter
from saida.exceptions import AdapterError, ContextError


def test_csv_adapter_loads_context_and_adds_metadata(tmp_path: Path) -> None:
    csv_path = tmp_path / "sales.csv"
    context_path = tmp_path / "sales.md"
    csv_path.write_text(" revenue ,region\n100,West\n", encoding="utf-8")
    context_path.write_text(
        """
# Dataset: Sales

## Metric Definitions
revenue: total revenue
""".strip(),
        encoding="utf-8",
    )

    dataset = CSVAdapter(csv_path, context_path=context_path).load()

    assert list(dataset.data.columns) == ["revenue", "region"]
    assert dataset.context is not None
    assert dataset.context.metric_definitions["revenue"] == "total revenue"
    assert dataset.metadata["row_count"] == 1
    assert dataset.metadata["column_count"] == 2


def test_csv_adapter_rejects_empty_dataset(tmp_path: Path) -> None:
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("revenue,region\n", encoding="utf-8")

    with pytest.raises(AdapterError, match="Loaded dataset is empty."):
        CSVAdapter(csv_path).load()


def test_json_adapter_rejects_duplicate_columns_after_normalization(tmp_path: Path) -> None:
    json_path = tmp_path / "duplicate.json"
    json_path.write_text('[{" revenue ": 100, "revenue": 90}]', encoding="utf-8")

    with pytest.raises(AdapterError, match="duplicate column names"):
        JSONAdapter(json_path).load()


def test_pandas_adapter_rejects_non_dataframe_input() -> None:
    with pytest.raises(AdapterError, match="requires a pandas DataFrame"):
        PandasAdapter([{"revenue": 100}]).load()  # type: ignore[arg-type]


def test_pandas_adapter_rejects_duplicate_columns_after_normalization() -> None:
    dataframe = pd.DataFrame([[100, 90]], columns=[" revenue ", "revenue"])

    with pytest.raises(AdapterError, match="duplicate column names"):
        PandasAdapter(dataframe).load()


def test_sql_adapter_raises_clean_error_for_bad_query(tmp_path: Path) -> None:
    database_path = tmp_path / "sales.db"
    connection = sqlite3.connect(database_path)
    connection.execute("create table sales (revenue integer)")
    connection.commit()
    connection.close()

    with pytest.raises(AdapterError, match="Failed to load SQL query results"):
        SQLAdapter(database_path, "select missing_column from sales").load()


def test_csv_adapter_uses_custom_name(tmp_path: Path) -> None:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("revenue,region\n100,West\n", encoding="utf-8")

    dataset = CSVAdapter(csv_path, name="custom_sales").load()

    assert dataset.name == "custom_sales"


def test_csv_adapter_raises_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(AdapterError, match="CSV file not found"):
        CSVAdapter(tmp_path / "missing.csv").load()


def test_csv_adapter_surfaces_missing_context_error(tmp_path: Path) -> None:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("revenue,region\n100,West\n", encoding="utf-8")

    with pytest.raises(ContextError, match="Context file not found"):
        CSVAdapter(csv_path, context_path=tmp_path / "missing.md").load()


def test_excel_adapter_loads_sheet_and_metadata(tmp_path: Path) -> None:
    excel_path = tmp_path / "sales.xlsx"
    dataframe = pd.DataFrame({"revenue": [100, 120], "region": ["West", "East"]})
    dataframe.to_excel(excel_path, index=False)

    dataset = ExcelAdapter(excel_path, sheet_name=0).load()

    assert dataset.source_type == "excel"
    assert dataset.metadata["sheet_name"] == 0
    assert list(dataset.data.columns) == ["revenue", "region"]


def test_json_adapter_loads_line_delimited_json(tmp_path: Path) -> None:
    json_path = tmp_path / "sales_lines.json"
    json_path.write_text('{"revenue": 100, "region": "West"}\n{"revenue": 90, "region": "East"}\n', encoding="utf-8")

    dataset = JSONAdapter(json_path).load()

    assert len(dataset.data) == 2
    assert dataset.data.iloc[1]["region"] == "East"


def test_pandas_adapter_sets_metadata_counts() -> None:
    dataframe = pd.DataFrame({"revenue": [100, 120], "region": ["West", "East"]})

    dataset = PandasAdapter(dataframe, name="sales").load()

    assert dataset.metadata["row_count"] == 2
    assert dataset.metadata["column_count"] == 2


def test_pandas_adapter_rejects_empty_column_name() -> None:
    dataframe = pd.DataFrame([[100, "West"]], columns=["", "region"])

    with pytest.raises(AdapterError, match="empty column name"):
        PandasAdapter(dataframe).load()


def test_sql_adapter_loads_metadata_for_valid_query(tmp_path: Path) -> None:
    database_path = tmp_path / "sales.db"
    connection = sqlite3.connect(database_path)
    connection.execute("create table sales (revenue integer, region text)")
    connection.execute("insert into sales (revenue, region) values (100, 'West')")
    connection.commit()
    connection.close()

    dataset = SQLAdapter(database_path, "select revenue, region from sales", name="sales_query").load()

    assert dataset.name == "sales_query"
    assert dataset.metadata["database_path"] == str(database_path)
    assert "select revenue, region from sales" in dataset.metadata["query"]


_PANDAS_ADAPTER_MANY_VALID_CASES = [
    (
        f"sales_{index}",
        pd.DataFrame(
            {
                " revenue ": [float(index), float(index + 1), float(index + 2)],
                "region": [f"Region{index % 5}", f"Region{(index + 1) % 5}", f"Region{(index + 2) % 5}"],
            }
        ),
    )
    for index in range(1, 91)
]


@pytest.mark.parametrize(("dataset_name", "dataframe"), _PANDAS_ADAPTER_MANY_VALID_CASES)
def test_pandas_adapter_handles_many_valid_shapes(dataset_name: str, dataframe: pd.DataFrame) -> None:
    dataset = PandasAdapter(dataframe, name=dataset_name).load()

    assert dataset.name == dataset_name
    assert list(dataset.data.columns) == ["revenue", "region"]
    assert dataset.metadata["row_count"] == 3
    assert dataset.metadata["column_count"] == 2

