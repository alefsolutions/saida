from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from saida.exceptions import AdapterError
from saida.sources import (
    CSVSource,
    JSONSource,
    MySQLSource,
    PandasSource,
    PostgreSQLSource,
    RelationalAccessPlan,
    RelationalSchemaModel,
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


def test_sqlite_source_can_discover_relational_schema_with_foreign_keys(tmp_path) -> None:
    database_path = tmp_path / "warehouse.sqlite"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("pragma foreign_keys = on")
        connection.execute("create table customers (customer_id text primary key, country text)")
        connection.execute(
            "create table orders ("
            "order_id text primary key, "
            "customer_id text not null, "
            "total_sales real, "
            "foreign key(customer_id) references customers(customer_id)"
            ")"
        )
        connection.commit()
    finally:
        connection.close()

    source = SQLiteSource(database_path, "select * from orders", name="warehouse_sales")

    schema = source.discover_schema()

    assert isinstance(schema, RelationalSchemaModel)
    assert schema.source_type == "sqlite"
    assert schema.source_name == "warehouse_sales"
    assert schema.metadata["table_count"] == 2
    assert schema.metadata["relationship_count"] == 1

    tables_by_name = {table.name: table for table in schema.tables}
    assert sorted(tables_by_name) == ["customers", "orders"]
    assert tables_by_name["customers"].primary_key == ["customer_id"]
    assert tables_by_name["orders"].primary_key == ["order_id"]

    order_columns = {column.name: column for column in tables_by_name["orders"].columns}
    assert order_columns["order_id"].is_primary_key is True
    assert order_columns["customer_id"].nullable is False
    assert "real" in order_columns["total_sales"].data_type

    relationship = schema.relationships[0]
    assert relationship.left_table == "orders"
    assert relationship.left_columns == ["customer_id"]
    assert relationship.right_table == "customers"
    assert relationship.right_columns == ["customer_id"]
    assert relationship.relationship_type == "many_to_one"


def test_sqlite_source_schema_discovery_is_cached(tmp_path) -> None:
    database_path = tmp_path / "warehouse.sqlite"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("create table sales (order_id text primary key, total_sales real)")
        connection.commit()
    finally:
        connection.close()

    source = SQLiteSource(database_path, "select * from sales")

    schema_first = source.discover_schema()
    schema_second = source.discover_schema()

    assert schema_first is schema_second


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


def test_sql_query_sources_can_discover_schema_from_sqlalchemy_uri(tmp_path) -> None:
    database_path = tmp_path / "warehouse.sqlite"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("create table sales (order_id text primary key, total_sales real)")
        connection.commit()
    finally:
        connection.close()

    postgres_like_source = PostgreSQLSource(
        f"sqlite:///{database_path}",
        "select * from sales",
        name="warehouse_sales",
    )

    schema = postgres_like_source.discover_schema()

    assert schema.source_type == "postgresql"
    assert [table.name for table in schema.tables] == ["sales"]
    assert schema.metadata["introspection_backend"] == "sqlalchemy"


def test_sqlite_source_can_plan_access_for_joined_fields(tmp_path) -> None:
    database_path = tmp_path / "warehouse.sqlite"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("pragma foreign_keys = on")
        connection.execute("create table customers (customer_id text primary key, country text, region text)")
        connection.execute(
            "create table orders ("
            "order_id text primary key, "
            "customer_id text not null, "
            "order_date text, "
            "total_sales real, "
            "foreign key(customer_id) references customers(customer_id)"
            ")"
        )
        connection.commit()
    finally:
        connection.close()

    source = SQLiteSource(database_path, "select * from orders", name="warehouse_sales")

    plan = source.plan_access(required_columns=["order_id", "country", "total_sales"])

    assert isinstance(plan, RelationalAccessPlan)
    assert plan.base_table == "orders"
    assert plan.required_tables == ["customers", "orders"]
    assert [(projection.source_table, projection.source_column) for projection in plan.projections] == [
        ("orders", "order_id"),
        ("customers", "country"),
        ("orders", "total_sales"),
    ]
    assert len(plan.joins) == 1
    assert plan.joins[0].left_table == "orders"
    assert plan.joins[0].right_table == "customers"
    assert plan.joins[0].left_columns == ["customer_id"]
    assert plan.joins[0].right_columns == ["customer_id"]


def test_sqlite_source_can_plan_access_with_single_table_projection(tmp_path) -> None:
    database_path = tmp_path / "warehouse.sqlite"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("create table sales (order_id text primary key, order_date text, total_sales real)")
        connection.commit()
    finally:
        connection.close()

    source = SQLiteSource(database_path, "select * from sales", name="warehouse_sales")

    plan = source.plan_access(required_columns=["order_id", "total_sales"])

    assert plan.base_table == "sales"
    assert plan.required_tables == ["sales"]
    assert plan.joins == []
    assert [projection.source_table for projection in plan.projections] == ["sales", "sales"]


def test_sqlite_source_access_planning_rejects_ambiguous_columns(tmp_path) -> None:
    database_path = tmp_path / "warehouse.sqlite"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("create table customers (customer_id text primary key, country text)")
        connection.execute("create table shipments (shipment_id text primary key, country text)")
        connection.commit()
    finally:
        connection.close()

    source = SQLiteSource(database_path, "select * from customers", name="warehouse_sales")

    with pytest.raises(AdapterError, match="ambiguous across tables"):
        source.plan_access(required_columns=["country"])


def test_sqlite_source_access_planning_can_use_qualified_column_names(tmp_path) -> None:
    database_path = tmp_path / "warehouse.sqlite"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("create table customers (customer_id text primary key, country text)")
        connection.execute("create table shipments (shipment_id text primary key, country text)")
        connection.commit()
    finally:
        connection.close()

    source = SQLiteSource(database_path, "select * from customers", name="warehouse_sales")

    plan = source.plan_access(required_columns=["customers.country"], preferred_base_table="customers")

    assert plan.base_table == "customers"
    assert plan.required_tables == ["customers"]
    assert plan.projections[0].source_table == "customers"
    assert plan.projections[0].source_column == "country"

