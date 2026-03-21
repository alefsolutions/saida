from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from _env import load_project_env
from saida import Saida
from saida.config import LlmConfig, SaidaConfig
from saida.sources import CSVSource

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise RuntimeError(
        "FastAPI playground requires 'fastapi' and 'uvicorn'. "
        "Install them with: pip install fastapi uvicorn"
    ) from exc


DEFAULT_DATASET_PATH = PROJECT_ROOT / "examples" / "datasets" / "support_tickets_500.csv"
DEFAULT_CONTEXT_PATH = PROJECT_ROOT / "examples" / "contexts" / "support_tickets_500.md"

load_project_env(PROJECT_ROOT)


class AnalyzeRequest(BaseModel):
    question: str = Field(..., description="Natural-language question for SAIDA.")
    dataset_path: str | None = Field(
        default=None,
        description="Optional CSV path. Defaults to the bundled support_tickets_500 dataset.",
    )
    context_path: str | None = Field(
        default=None,
        description="Optional markdown context path. Defaults to the bundled support_tickets_500 context.",
    )
    use_llm: bool = Field(
        default=False,
        description="Enable OpenAI prompt and response assistance.",
    )
    llm_provider: str = Field(default="openai", description="LLM provider name when use_llm=true.")
    llm_model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))


class ErrorResponse(BaseModel):
    detail: str


app = FastAPI(
    title="SAIDA Playground API",
    version="0.2.0",
    description="Small Postman-friendly API wrapper around the SAIDA analytics engine.",
)


def _resolve_path(path_value: str | None, default_path: Path) -> Path:
    if not path_value:
        return default_path
    candidate = Path(path_value)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate


def _build_engine(use_llm: bool, llm_provider: str, llm_model: str) -> Saida:
    if not use_llm:
        return Saida()
    if llm_provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY is not set, so LLM mode is unavailable.")
    return Saida(
        config=SaidaConfig(
            llm=LlmConfig(
                enabled=True,
                provider=llm_provider,
                model=llm_model,
                use_for_prompting=True,
                use_for_reasoning=True,
            )
        )
    )


def _load_dataset(dataset_path: Path, context_path: Path | None) -> Any:
    if not dataset_path.exists():
        raise HTTPException(status_code=404, detail=f"Dataset file not found: {dataset_path}")
    if context_path is not None and not context_path.exists():
        raise HTTPException(status_code=404, detail=f"Context file not found: {context_path}")
    return CSVSource(dataset_path, context_path=context_path).load()


@app.get("/")
def root() -> dict[str, object]:
    return {
        "name": "SAIDA Playground API",
        "status": "ok",
        "default_dataset": str(DEFAULT_DATASET_PATH),
        "default_context": str(DEFAULT_CONTEXT_PATH),
        "routes": {
            "health": "GET /health",
            "analyze": "POST /analyze",
        },
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
def analyze(payload: AnalyzeRequest) -> dict[str, object]:
    dataset_path = _resolve_path(payload.dataset_path, DEFAULT_DATASET_PATH)
    context_path = _resolve_path(payload.context_path, DEFAULT_CONTEXT_PATH) if payload.context_path else DEFAULT_CONTEXT_PATH
    dataset = _load_dataset(dataset_path, context_path)
    engine = _build_engine(payload.use_llm, payload.llm_provider, payload.llm_model)

    try:
        result = engine.analyze(dataset, payload.question)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result.to_response_dict()


if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - runtime dependency guard
        raise RuntimeError(
            "Running the playground API requires 'uvicorn'. Install it with: pip install uvicorn"
        ) from exc

    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
