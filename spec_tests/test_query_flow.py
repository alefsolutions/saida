from pathlib import Path

from saida import SaidaAgent
from saida.connectors.filesystem import FileSystemConnector
from saida.utils.config import SaidaConfig


def test_query_returns_structured_response(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    text = data / "notes.txt"
    text.write_text("Revenue dropped in Q3 due to pricing changes.", encoding="utf-8")

    db_path = tmp_path / "control.db"
    agent = SaidaAgent(SaidaConfig(control_plane_dsn=f"sqlite+pysqlite:///{db_path.as_posix()}"))
    agent.add_connector(FileSystemConnector(str(data)))
    agent.ingest_all()

    result = agent.query("Why did revenue change?")

    assert result.query
    assert result.route in {"analytics", "semantic_reasoning"}
    assert isinstance(result.retrieved_context, list)
    assert isinstance(result.explanation, str)
