from __future__ import annotations

from abc import ABC, abstractmethod


class DataSource(ABC):
    @abstractmethod
    def fetch(self, query: str) -> list[dict]:
        raise NotImplementedError