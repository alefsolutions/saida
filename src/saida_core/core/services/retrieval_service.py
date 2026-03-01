from __future__ import annotations

from saida_core.core.domain.context import ContextBundle
from saida_core.core.contracts.data_source import DataSource
from saida_core.core.contracts.retriever import Retriever


class RetrievalService:
    def __init__(self, data_source: DataSource, retriever: Retriever):
        self.data_source = data_source
        self.retriever = retriever

    def collect(self, query: str) -> ContextBundle:
        records = self.data_source.fetch(query)
        docs = self.retriever.retrieve(query)
        return ContextBundle(records=records, documents=docs)