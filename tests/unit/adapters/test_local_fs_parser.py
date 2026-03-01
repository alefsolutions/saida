from pathlib import Path

from saida_core.adapters.data_sources.local_fs.parser import chunk_text, parse_file


def test_parse_file_reads_text_file(tmp_path: Path):
    path = tmp_path / "report.txt"
    path.write_text("hello world", encoding="utf-8")
    parsed = parse_file(path)
    assert parsed["text"] == "hello world"
    assert parsed["extension"] == ".txt"


def test_chunk_text_splits_with_overlap():
    text = "a" * 3000
    chunks = chunk_text(text, chunk_size=1000, overlap=100)
    assert len(chunks) >= 3
