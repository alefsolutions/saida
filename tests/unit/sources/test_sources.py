from __future__ import annotations

import sqlite3

import pandas as pd

from saida.sources import (
    CSVSource,
    JSONSource,
    MySQLSource,
    PandasSource,
    PostgreSQLSource,
    SQLSourceInterface,
    SourceInterface,
    SQLiteSource,
)


def test_csv_source_implements_interface_and_loads_dataset(tmp_path) -> None:
    csv_path = tmp_path / "tickets.csv"
    context_path = tmp_path / "tickets.md"
    csv_path.write_text("ticket_id,resolution_hours\nT1,4.2\nT2,5.1\n", encoding="utf-8")
    context_path.write_text("# Dataset: Tickets\n\n## Metric Definitions\nresolution_hours: resolution time\n", encoding="utf-8")

    source = CSVSource(csv_path, context_path=context_path)
    dataset = source.load()

    assert isinstance(source, SourceInterface)
    assert source.source_type == "csv"
    assert source.describe_source()["path"].endswith("tickets.csv")
    assert dataset.source_type == "csv"
    assert dataset.metadata["path"].endswith("tickets.csv")
    assert dataset.context is not None
    assert dataset.context.metric_definitions["resolution_hours"] == "resolution time"


def test_json_source_implements_interface_and_loads_dataset(tmp_path) -> None:
    json_path = tmp_path / "events.json"
    json_path.write_text('[{"event_id":"E1","amount":10},{"event_id":"E2","amount":20}]', encoding="utf-8")

    source = JSONSource(json_path)
    dataset = source.load()

    assert isinstance(source, SourceInterface)
    assert source.source_type == "json"
    assert dataset.source_type == "json"
    assert list(dataset.data.columns) == ["event_id", "amount"]
    assert dataset.data["amount"].tolist() == [10, 20]


def test_pandas_source_implements_interface_and_attaches_context() -> None:
    dataframe = pd.DataFrame({"revenue": [100.0, 120.0], "region": ["West", "East"]})
    source = PandasSource(
        dataframe,
        name="sales",
        context_markdown="# Dataset: Sales\n\n## Metric Definitions\nrevenue: total revenue\n",
    )
    dataset = source.load()

    assert isinstance(source, SourceInterface)
    assert source.source_type == "pandas"
    assert source.describe_source()["rows"] == 2
    assert dataset.name == "sales"
    assert dataset.context is not None
    assert dataset.context.metric_definitions["revenue"] == "total revenue"


def test_sqlite_source_implements_sql_interface_and_loads_dataset(tmp_path) -> None:
    database_path = tmp_path / "warehouse.sqlite"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("create table sales (order_id text, total_sales real)")
        connection.execute("insert into sales values ('O1', 100.5)")
        connection.execute("insert into sales values ('O2', 80.0)")
        connection.commit()
    finally:
        connection.close()

    source = SQLiteSource(database_path, "select * from sales order by order_id")
    dataset = source.load()

    assert isinstance(source, SQLSourceInterface)
    assert source.source_type == "sqlite"
    assert dataset.source_type == "sqlite"
    assert dataset.data["order_id"].tolist() == ["O1", "O2"]
    assert dataset.data["total_sales"].tolist() == [100.5, 80.0]


def test_remote_sql_sources_expose_masked_metadata_without_loading() -> None:
    postgres_source = PostgreSQLSource(
        "postgresql://reporter:secret@db.example.com:5432/warehouse",
        "select * from sales",
        name="warehouse_sales",
    )
    mysql_source = MySQLSource(
        "mysql://reporter:secret@db.example.com:3306/warehouse",
        "select * from sales",
        name="warehouse_sales",
    )

    assert isinstance(postgres_source, SQLSourceInterface)
    assert isinstance(mysql_source, SQLSourceInterface)
    assert postgres_source.describe_source()["connection_uri"] == "postgresql://reporter:***@db.example.com:5432/warehouse"
    assert mysql_source.describe_source()["connection_uri"] == "mysql://reporter:***@db.example.com:3306/warehouse"

