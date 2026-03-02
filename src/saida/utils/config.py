from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(slots=True)
class SaidaConfig:
    llm_provider: str = field(default_factory=lambda: os.getenv("SAIDA_LLM_PROVIDER", "mock"))
    embedding_provider: str = field(default_factory=lambda: os.getenv("SAIDA_EMBEDDING_PROVIDER", "mock"))
    control_plane_dsn: str = field(
        default_factory=lambda: os.getenv(
            "SAIDA_CONTROL_PLANE_DSN", "postgresql+psycopg://postgres:postgres@localhost:5432/saida"
        )
    )
    parquet_root: str = field(default_factory=lambda: os.getenv("SAIDA_PARQUET_ROOT", "./.saida/parquet"))
