from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Type

from saida.sources import MySQLSource, PostgreSQLSource, SQLiteSource


def create_commerce_relational_database(database_path: str | Path) -> Path:
    path = Path(database_path)
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    try:
        connection.execute("pragma foreign_keys = on")
        connection.execute(
            "create table customers ("
            "customer_id text primary key, "
            "customer_name text not null, "
            "country text not null, "
            "region text not null"
            ")"
        )
        connection.execute(
            "create table products ("
            "product_id text primary key, "
            "product_name text not null, "
            "product_category text not null, "
            "unit_price real not null"
            ")"
        )
        connection.execute(
            "create table orders ("
            "order_id text primary key, "
            "customer_id text not null, "
            "order_date text not null, "
            "sales_channel text not null, "
            "total_sales real not null, "
            "foreign key(customer_id) references customers(customer_id)"
            ")"
        )
        connection.execute(
            "create table order_items ("
            "order_item_id text primary key, "
            "order_id text not null, "
            "product_id text not null, "
            "quantity integer not null, "
            "line_total real not null, "
            "foreign key(order_id) references orders(order_id), "
            "foreign key(product_id) references products(product_id)"
            ")"
        )

        connection.executemany(
            "insert into customers values (?, ?, ?, ?)",
            [
                ("C1", "Acacia Retail", "Australia", "Oceania"),
                ("C2", "Sakura Labs", "Japan", "Asia"),
                ("C3", "Rhein Works", "Germany", "Europe"),
            ],
        )
        connection.executemany(
            "insert into products values (?, ?, ?, ?)",
            [
                ("P1", "Insight Suite", "Software", 45.0),
                ("P2", "Field Kit", "Hardware", 80.0),
                ("P3", "Advisory Hours", "Services", 120.0),
            ],
        )
        connection.executemany(
            "insert into orders values (?, ?, ?, ?, ?)",
            [
                ("O1", "C1", "2026-01-01", "Online", 100.0),
                ("O2", "C1", "2026-01-02", "Retail", 120.0),
                ("O3", "C2", "2026-01-03", "Online", 80.0),
                ("O4", "C3", "2026-01-04", "Partner", 150.0),
            ],
        )
        connection.executemany(
            "insert into order_items values (?, ?, ?, ?, ?)",
            [
                ("OI1", "O1", "P1", 1, 45.0),
                ("OI2", "O1", "P2", 1, 55.0),
                ("OI3", "O2", "P3", 1, 120.0),
                ("OI4", "O3", "P1", 1, 45.0),
                ("OI5", "O3", "P2", 1, 35.0),
                ("OI6", "O4", "P2", 1, 80.0),
                ("OI7", "O4", "P3", 1, 70.0),
            ],
        )
        connection.commit()
    finally:
        connection.close()

    return path


def build_commerce_sqlite_source(database_path: str | Path) -> SQLiteSource:
    path = create_commerce_relational_database(database_path)
    return SQLiteSource(path, 'SELECT * FROM "orders"', name="warehouse_sales")


def build_commerce_sql_query_source(
    source_cls: Type[PostgreSQLSource] | Type[MySQLSource],
    database_path: str | Path,
):
    path = create_commerce_relational_database(database_path)
    query = 'SELECT * FROM "orders"' if source_cls is PostgreSQLSource else "SELECT * FROM orders"
    return source_cls(f"sqlite:///{path}", query, name="warehouse_sales")


def create_support_relational_database(database_path: str | Path) -> Path:
    path = Path(database_path)
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    try:
        connection.execute("pragma foreign_keys = on")
        connection.execute("create table teams (team_id text primary key, team_name text not null)")
        connection.execute(
            "create table agents ("
            "agent_id text primary key, "
            "team_id text not null, "
            "agent_name text not null, "
            "foreign key(team_id) references teams(team_id)"
            ")"
        )
        connection.execute("create table channels (channel_id text primary key, channel_name text not null)")
        connection.execute(
            "create table tickets ("
            "ticket_id text primary key, "
            "agent_id text not null, "
            "channel_id text not null, "
            "created_at text not null, "
            "resolution_hours real not null, "
            "csat_score real, "
            "status text not null, "
            "foreign key(agent_id) references agents(agent_id), "
            "foreign key(channel_id) references channels(channel_id)"
            ")"
        )
        connection.executemany(
            "insert into teams values (?, ?)",
            [("T1", "Support"), ("T2", "Platform")],
        )
        connection.executemany(
            "insert into agents values (?, ?, ?)",
            [("A1", "T1", "Mia"), ("A2", "T2", "Noah")],
        )
        connection.executemany(
            "insert into channels values (?, ?)",
            [("CH1", "Email"), ("CH2", "Chat")],
        )
        connection.executemany(
            "insert into tickets values (?, ?, ?, ?, ?, ?, ?)",
            [
                ("TK1", "A1", "CH1", "2026-02-01", 2.5, 4.8, "closed"),
                ("TK2", "A1", "CH2", "2026-02-02", 3.0, 4.4, "closed"),
                ("TK3", "A2", "CH2", "2026-02-03", 5.5, 3.9, "closed"),
            ],
        )
        connection.commit()
    finally:
        connection.close()

    return path


def build_support_sqlite_source(database_path: str | Path) -> SQLiteSource:
    path = create_support_relational_database(database_path)
    return SQLiteSource(path, 'SELECT * FROM "tickets"', name="support_relational")


def build_simple_sales_sqlite_source(database_path: str | Path) -> SQLiteSource:
    path = Path(database_path)
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("pragma foreign_keys = on")
        connection.execute("create table customers (customer_id text primary key, country text, region text)")
        connection.execute(
            "create table orders ("
            "order_id text primary key, "
            "customer_id text not null, "
            "order_date text not null, "
            "total_sales real not null, "
            "foreign key(customer_id) references customers(customer_id)"
            ")"
        )
        connection.execute("insert into customers values ('C1', 'Australia', 'Oceania')")
        connection.execute("insert into customers values ('C2', 'Japan', 'Asia')")
        connection.execute("insert into orders values ('O1', 'C1', '2026-01-01', 100.0)")
        connection.execute("insert into orders values ('O2', 'C1', '2026-01-02', 120.0)")
        connection.execute("insert into orders values ('O3', 'C2', '2026-01-03', 80.0)")
        connection.commit()
    finally:
        connection.close()
    return SQLiteSource(path, 'SELECT * FROM "orders"', name="warehouse_sales")


def build_ambiguous_country_sqlite_source(database_path: str | Path) -> SQLiteSource:
    path = Path(database_path)
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("pragma foreign_keys = on")
        connection.execute("create table customers (customer_id text primary key, country text)")
        connection.execute("create table shipments (shipment_id text primary key, country text)")
        connection.execute("insert into customers values ('C1', 'Australia')")
        connection.execute("insert into shipments values ('S1', 'Japan')")
        connection.commit()
    finally:
        connection.close()
    return SQLiteSource(path, 'SELECT * FROM "customers"', name="warehouse_sales")


def build_missing_join_path_sqlite_source(database_path: str | Path) -> SQLiteSource:
    path = Path(database_path)
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
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
        connection.execute("create table suppliers (supplier_id text primary key, supplier_name text)")
        connection.execute("insert into customers values ('C1', 'Australia')")
        connection.execute("insert into orders values ('O1', 'C1', 100.0)")
        connection.execute("insert into suppliers values ('S1', 'Contoso')")
        connection.commit()
    finally:
        connection.close()
    return SQLiteSource(path, 'SELECT * FROM "orders"', name="warehouse_sales")
