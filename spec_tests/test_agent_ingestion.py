from pathlib import Path

from saida import SaidaAgent
from saida.connectors.filesystem import FileSystemConnector
from saida.utils.config import SaidaConfig


def test_agent_required_methods_exist():
    agent = SaidaAgent(SaidaConfig(control_plane_dsn="sqlite+pysqlite:///:memory:"))
    for name in ["add_connector", "ingest_all", "sync", "query", "run_benchmarks"]:
        assert hasattr(agent, name)


def test_ingestion_is_explicit_and_idempotent(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    csv = data / "sales.csv"
    csv.write_text("quarter,revenue\nQ1,10\nQ2,20\n", encoding="utf-8")

    db_path = tmp_path / "control.db"
    agent = SaidaAgent(SaidaConfig(control_plane_dsn=f"sqlite+pysqlite:///{db_path.as_posix()}"))
    agent.add_connector(FileSystemConnector(str(data)))

    first = agent.ingest_all()
    second = agent.ingest_all()

    assert len(first) >= 1
    assert second == []
