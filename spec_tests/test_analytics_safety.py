from pathlib import Path

import pytest

from saida import SaidaAgent
from saida.analytics.sql_planner import SQLPlanner
from saida.analytics.sql_validator import SQLValidationError, SQLValidator
from saida.llm.base import BaseLLMProvider
from saida.orchestration.llm_guard import LLMNumericPolicyError
from saida.connectors.filesystem import FileSystemConnector
from saida.utils.config import SaidaConfig


class _BadNumericLLM(BaseLLMProvider):
    name = "bad"

    def explain(self, prompt: str) -> str:
        return "Computed result is 9999 based on analysis."


class _GroundedLLM(BaseLLMProvider):
    name = "good"

    def explain(self, prompt: str) -> str:
        return "The verified row_count is 2."


def test_sql_validator_blocks_dangerous_statements():
    validator = SQLValidator()
    with pytest.raises(SQLValidationError):
        validator.validate("DROP TABLE users")
    with pytest.raises(SQLValidationError):
        validator.validate("SELECT * FROM read_parquet('x'); SELECT 1")


def test_sql_planner_produces_read_only_templates():
    planner = SQLPlanner()
    plan = planner.plan(
        query="count records",
        route="analytics",
        retrieved_context=[{"parquet_path": "C:/tmp/a.parquet"}],
    )
    assert plan.sql is not None
    assert plan.sql.lower().startswith("select")
    assert "read_parquet" in plan.sql.lower()


def test_llm_numeric_policy_rejects_unverified_numbers(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    csv = data / "sales.csv"
    csv.write_text("quarter,revenue\nQ1,10\nQ2,20\n", encoding="utf-8")

    db_path = tmp_path / "control.db"
    agent = SaidaAgent(SaidaConfig(control_plane_dsn=f"sqlite+pysqlite:///{db_path.as_posix()}"))
    agent.add_connector(FileSystemConnector(str(data)))
    agent.ingest_all()

    agent.orchestrator.llm_provider = _BadNumericLLM()
    with pytest.raises(LLMNumericPolicyError):
        agent.query("count rows for q1")


def test_llm_numeric_policy_allows_grounded_numbers(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    csv = data / "sales.csv"
    csv.write_text("quarter,revenue\nQ1,10\nQ2,20\n", encoding="utf-8")

    db_path = tmp_path / "control.db"
    agent = SaidaAgent(SaidaConfig(control_plane_dsn=f"sqlite+pysqlite:///{db_path.as_posix()}"))
    agent.add_connector(FileSystemConnector(str(data)))
    agent.ingest_all()

    agent.orchestrator.llm_provider = _GroundedLLM()
    result = agent.query("count rows")
    assert "2" in result.explanation
