from __future__ import annotations

import json
from urllib import error

import pytest

from saida.config import LlmConfig
from saida.exceptions import LlmIntegrationError
from saida.llm.openai_provider import OpenAiLlmProvider
from saida.llm.ollama import OllamaLlmProvider


def test_openai_provider_classifies_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAiLlmProvider(LlmConfig(enabled=True, provider="openai", model="gpt-4.1-mini"))

    with pytest.raises(LlmIntegrationError) as exc_info:
        provider.interpret_prompt("How many rows?", "sales", "rows=10", None)

    assert exc_info.value.code == "auth_missing"
    assert exc_info.value.provider == "openai"


def test_openai_provider_classifies_http_auth_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenAiLlmProvider(
        LlmConfig(enabled=True, provider="openai", model="gpt-4.1-mini", options={"api_key": "test-key"})
    )

    def _raise_http_error(*args, **kwargs):
        raise error.HTTPError("https://api.openai.com/v1/responses", 401, "Unauthorized", hdrs=None, fp=None)

    monkeypatch.setattr("urllib.request.urlopen", _raise_http_error)

    with pytest.raises(LlmIntegrationError) as exc_info:
        provider.interpret_prompt("How many rows?", "sales", "rows=10", None)

    assert exc_info.value.code == "bad_auth"
    assert exc_info.value.provider == "openai"


def test_ollama_provider_classifies_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OllamaLlmProvider(LlmConfig(enabled=True, provider="ollama", model="missing-model"))

    def _raise_http_error(*args, **kwargs):
        raise error.HTTPError("http://127.0.0.1:11434/api/generate", 404, "Not Found", hdrs=None, fp=None)

    monkeypatch.setattr("urllib.request.urlopen", _raise_http_error)

    with pytest.raises(LlmIntegrationError) as exc_info:
        provider.interpret_prompt("How many rows?", "sales", "rows=10", None)

    assert exc_info.value.code == "model_missing"
    assert exc_info.value.provider == "ollama"


def test_ollama_provider_classifies_invalid_contract_json(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OllamaLlmProvider(LlmConfig(enabled=True, provider="ollama", model="gemma3:1b"))

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            payload = {"response": "not-json"}
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: _FakeResponse())

    with pytest.raises(LlmIntegrationError) as exc_info:
        provider.generate_summary(
            summary_context=type(
                "SummaryContextLike",
                (),
                {
                    "question": "How many rows?",
                    "dataset_name": "sales",
                    "task_type": "descriptive",
                    "deterministic_summary": "The dataset contains 10 rows.",
                    "context_summary": None,
                    "metric_lookup": {"row_count": 10},
                    "table_index": {},
                    "warnings": [],
                },
            )()
        )

    assert exc_info.value.code == "invalid_contract_json"
    assert exc_info.value.provider == "ollama"
