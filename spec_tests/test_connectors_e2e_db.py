from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from saida.connectors.mysql import MySQLConnector
from saida.connectors.postgres import PostgresConnector


def _get_env(name: str) -> str | None:
    value = os.getenv(name)
    return value if value else None


def test_postgres_connector_e2e():
    dsn = _get_env("TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("TEST_POSTGRES_DSN is not set; skipping Postgres connector e2e.")

    table = f"saida_connector_{uuid.uuid4().hex[:8]}"
    engine = create_engine(dsn, future=True)
    with engine.begin() as conn:
        conn.execute(text(f'CREATE TABLE "public"."{table}" (id INT PRIMARY KEY, name TEXT)'))
        conn.execute(text(f'INSERT INTO "public"."{table}" (id, name) VALUES (1, ''alpha''), (2, ''beta'')'))

    try:
        connector = PostgresConnector(dsn=dsn, schema="public", row_limit=10)
        resources = connector.discover()
        assert f"public.{table}" in resources

        rows = connector.load(f"public.{table}")
        assert len(rows) == 2
        assert {r["name"] for r in rows} == {"alpha", "beta"}
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP TABLE IF EXISTS "public"."{table}"'))


def test_mysql_connector_e2e():
    dsn = _get_env("TEST_MYSQL_DSN")
    if not dsn:
        pytest.skip("TEST_MYSQL_DSN is not set; skipping MySQL connector e2e.")

    table = f"saida_connector_{uuid.uuid4().hex[:8]}"
    engine = create_engine(dsn, future=True)
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE `{table}` (id INT PRIMARY KEY, name VARCHAR(64))"))
        conn.execute(text(f"INSERT INTO `{table}` (id, name) VALUES (1, 'alpha'), (2, 'beta')"))

    try:
        connector = MySQLConnector(dsn=dsn, row_limit=10)
        resources = connector.discover()
        assert any(resource.endswith(f".{table}") for resource in resources)

        rows = connector.load(table)
        assert len(rows) == 2
        assert {r["name"] for r in rows} == {"alpha", "beta"}
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
