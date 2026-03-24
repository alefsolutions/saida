"""Pandas source implementation."""

from __future__ import annotations

import pandas as pd

from saida.sources._helpers import build_dataset
from saida.sources.interfaces import SourceInterface
from saida.core.context import SourceContextParser
from saida.exceptions import AdapterError
from saida.core.contracts import Dataset


class PandasSource(SourceInterface):
    """Wrap an existing pandas DataFrame in the SAIDA dataset schema."""

    def __init__(self, dataframe: pd.DataFrame, *, name: str = "dataframe", context_markdown: str | None = None) -> None:
        if not isinstance(dataframe, pd.DataFrame):
            raise AdapterError("PandasAdapter requires a pandas DataFrame.")
        self.dataframe = dataframe.copy()
        self.name = name
        self.context_markdown = context_markdown

    @property
    def source_type(self) -> str:
        return "pandas"

    @property
    def source_name(self) -> str:
        return self.name

    def describe_source(self) -> dict[str, object]:
        return {"rows": len(self.dataframe), "columns": list(self.dataframe.columns)}

    def load_context(self) -> object:
        if self.context_markdown:
            return SourceContextParser().parse(self.context_markdown)
        return None

    def load(self) -> Dataset:
        """Return the DataFrame as a SAIDA dataset."""
        return build_dataset(
            self.dataframe,
            name=self.name,
            source_type=self.source_type,
            metadata=self.describe_source(),
            context=self.load_context(),
        )


PandasAdapter = PandasSource
