"""Excel source implementation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from saida.sources._helpers import build_dataset, load_context
from saida.exceptions import AdapterError
from saida.core.contracts import Dataset


class ExcelSource:
    """Load Excel data into the SAIDA dataset schema."""

    def __init__(
        self,
        path: str | Path,
        *,
        sheet_name: str | int = 0,
        name: str | None = None,
        context_path: str | Path | None = None,
    ) -> None:
        self.path = Path(path)
        self.sheet_name = sheet_name
        self.name = name or self.path.stem
        self.context_path = Path(context_path) if context_path else None

    def load(self) -> Dataset:
        """Load the Excel file and attach optional semantic context."""
        if not self.path.exists():
            raise AdapterError(f"Excel file not found: {self.path}")

        try:
            dataframe = pd.read_excel(self.path, sheet_name=self.sheet_name)
        except Exception as exc:  # pragma: no cover
            raise AdapterError(f"Failed to load Excel file: {self.path}") from exc

        context = load_context(self.context_path)
        return build_dataset(
            dataframe,
            name=self.name,
            source_type="excel",
            metadata={"path": str(self.path), "sheet_name": self.sheet_name},
            context=context,
        )


ExcelAdapter = ExcelSource
