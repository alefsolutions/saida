from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class RuntimeConfig:
    llm_provider: str = os.getenv("SAIDA_LLM_PROVIDER", "openai")
    embedding_provider: str = os.getenv("SAIDA_EMBEDDING_PROVIDER", "openai")
    vector_store_provider: str = os.getenv("SAIDA_VECTOR_STORE_PROVIDER", "chroma")
    data_source_provider: str = os.getenv("SAIDA_DATA_SOURCE_PROVIDER", "local_fs")