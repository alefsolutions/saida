"""Pandas source implementation."""

from __future__ import annotations

import pandas as pd

from saida.sources._helpers import build_dataset
from saida.core.context import SourceContextParser
from saida.exceptions import AdapterError
from saida.core.contracts import Dataset


class PandasSource:
    """Wrap an existing pandas DataFrame in the SAIDA dataset schema."""

    def __init__(self, dataframe: pd.DataFrame, *, name: str = "dataframe", context_markdown: str | None = None) -> None:
        if not isinstance(dataframe, pd.DataFrame):
            raise AdapterError("PandasAdapter requires a pandas DataFrame.")
        self.dataframe = dataframe.copy()
        self.name = name
        self.context_markdown = context_markdown

    def load(self) -> Dataset:
        """Return the DataFrame as a SAIDA dataset."""
        context = None
        if self.context_markdown:
            context = SourceContextParser().parse(self.context_markdown)

        return build_dataset(
            self.dataframe,
            name=self.name,
            source_type="pandas",
            metadata={"rows": len(self.dataframe), "columns": list(self.dataframe.columns)},
            context=context,
        )


PandasAdapter = PandasSource
