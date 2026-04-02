from __future__ import annotations

from pathlib import Path


def example1_dataset_paths(project_root: Path) -> tuple[Path, Path]:
    data_root = project_root / "playground" / "example1" / "data"
    return data_root / "sales_data_800_rows.csv", data_root / "sales_data_800_rows.md"
