from __future__ import annotations

from abc import ABC, abstractmethod


class VectorStore(ABC):
    @abstractmethod
    def upsert(self, item_id: str, vector: list[float], metadata: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    def query(self, vector: list[float], top_k: int = 5) -> list[dict]:
        raise NotImplementedError