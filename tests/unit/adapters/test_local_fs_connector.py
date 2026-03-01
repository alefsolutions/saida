from saida_core.adapters.data_sources.local_fs.connector import LocalFileSystemDataSource


def test_local_fs_fetch_handles_missing_root(tmp_path):
    source = LocalFileSystemDataSource(root=str(tmp_path / "missing"))
    assert source.fetch("test") == []


def test_local_fs_fetch_matches_content(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    file_path = root / "notes.txt"
    file_path.write_text("Q3 revenue declined by 12 percent", encoding="utf-8")

    source = LocalFileSystemDataSource(root=str(root))
    results = source.fetch("revenue")

    assert len(results) == 1
    assert results[0]["match"] == "content"
