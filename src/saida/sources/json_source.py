"""JSON source implementation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from saida.sources._helpers import build_dataset, load_context
from saida.exceptions import AdapterError
from saida.core.contracts import Dataset


class JSONSource:
    """Load JSON data into the SAIDA dataset schema."""

    def __init__(self, path: str | Path, *, name: str | None = None, context_path: str | Path | None = None) -> None:
        self.path = Path(path)
        self.name = name or self.path.stem
        self.context_path = Path(context_path) if context_path else None

    def load(self) -> Dataset:
        """Load a JSON file and attach optional semantic context."""
        if not self.path.exists():
            raise AdapterError(f"JSON file not found: {self.path}")

        try:
            dataframe = pd.read_json(self.path)
        except ValueError:
            try:
                dataframe = pd.read_json(self.path, lines=True)
            except Exception as exc:  # pragma: no cover
                raise AdapterError(f"Failed to load JSON file: {self.path}") from exc
        except Exception as exc:  # pragma: no cover
            raise AdapterError(f"Failed to load JSON file: {self.path}") from exc

        context = load_context(self.context_path)
        return build_dataset(
            dataframe,
            name=self.name,
            source_type="json",
            metadata={"path": str(self.path)},
            context=context,
        )


JSONAdapter = JSONSource
