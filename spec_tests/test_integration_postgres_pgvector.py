from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from saida import SaidaAgent
from saida.connectors.filesystem import FileSystemConnector
from saida.utils.config import SaidaConfig


def _pg_dsn() -> str | None:
    return os.getenv("TEST_POSTGRES_DSN")


def _require_postgres() -> str:
    dsn = _pg_dsn()
    if not dsn:
        pytest.skip("TEST_POSTGRES_DSN is not set; skipping Postgres+pgvector integration test.")
    return dsn


def _reset_tables(dsn: str) -> None:
    engine = create_engine(dsn, future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("DROP TABLE IF EXISTS semantic_embeddings CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS benchmark_reports CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS resource_hashes CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS datasets CASCADE"))


def test_postgres_pgvector_storage_and_retrieval(tmp_path: Path):
    dsn = _require_postgres()
    _reset_tables(dsn)

    data = tmp_path / "data"
    data.mkdir()
    csv = data / "sales.csv"
    csv.write_text("quarter,revenue\nQ1,10\nQ2,20\n", encoding="utf-8")

    cfg = SaidaConfig(
        control_plane_dsn=dsn,
        llm_provider="mock",
        embedding_provider="mock",
        parquet_root=str(tmp_path / "parquet"),
    )
    agent = SaidaAgent(cfg)
    agent.add_connector(FileSystemConnector(str(data)))
    assets = agent.ingest_all()
    assert assets

    result = agent.query("count rows")
    assert result.retrieved_context

    engine = create_engine(dsn, future=True)
    with engine.connect() as conn:
        ext = conn.execute(text("SELECT extname FROM pg_extension WHERE extname='vector'"))
        assert ext.scalar_one() == "vector"

        col = conn.execute(
            text(
                """
                SELECT udt_name
                FROM information_schema.columns
                WHERE table_name='semantic_embeddings'
                  AND column_name='embedding_vector'
                """
            )
        )
        assert col.scalar_one() == "vector"
