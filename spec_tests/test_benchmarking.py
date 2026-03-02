from pathlib import Path

from saida import SaidaAgent
from saida.connectors.filesystem import FileSystemConnector
from saida.utils.config import SaidaConfig


def test_benchmark_report_has_scores(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    text = data / "doc.txt"
    text.write_text("This is a benchmark fixture.", encoding="utf-8")

    db_path = tmp_path / "control.db"
    agent = SaidaAgent(SaidaConfig(control_plane_dsn=f"sqlite+pysqlite:///{db_path.as_posix()}"))
    agent.add_connector(FileSystemConnector(str(data)))
    agent.ingest_all()

    report = agent.run_benchmarks()

    assert report.total >= 1
    assert report.scores.composite >= 0.0
