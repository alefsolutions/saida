from __future__ import annotations

from abc import ABC, abstractmethod


class ModelRouter(ABC):
    @abstractmethod
    def select_llm(self, task_type: str):
        raise NotImplementedError