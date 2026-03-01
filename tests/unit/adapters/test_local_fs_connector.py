from saida_core.adapters.data_sources.local_fs.connector import LocalFileSystemDataSource


def test_local_fs_fetch_handles_missing_root(tmp_path):
    source = LocalFileSystemDataSource(root=str(tmp_path / "missing"))
    assert source.fetch("test") == []