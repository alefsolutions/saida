"""Ollama-backed provider implementation."""

from __future__ import annotations

import json
from urllib import error, request

from saida.config import LlmConfig
from saida.plan_generation.llm_contract import build_intent_prompt_contract_text, build_summary_contract_text
from saida.exceptions import LlmIntegrationError
from saida.llm.base import BaseLlmProvider
from saida.llm.models import IntentProposal, SummaryContext, SummaryProposal


class OllamaLlmProvider(BaseLlmProvider):
    """Use a local Ollama model for prompt interpretation and optional summary wording."""

    provider_name = "ollama"

    def __init__(self, config: LlmConfig) -> None:
        self.config = config
        self.model = config.model or "llama3.1"
        self.base_url = (config.base_url or "http://127.0.0.1:11434").rstrip("/")

    def interpret_prompt(
        self,
        question: str,
        dataset_name: str,
        profile_summary: str,
        context_summary: str | None,
    ) -> IntentProposal | None:
        prompt = self._build_intent_prompt(question, dataset_name, profile_summary, context_summary)
        payload = self._generate_json(prompt)
        if payload is None:
            return None

        return IntentProposal(
            status=str(payload.get("status", "ready")),
            canonical_question=self._maybe_string(payload.get("canonical_question")),
            prompt_family_hint=self._maybe_string(payload.get("prompt_family_hint")),
            confidence=self._maybe_float(payload.get("confidence")),
            operation=self._maybe_string(payload.get("operation")),
            object_kind=self._maybe_string(payload.get("object_kind")),
            object_ref=self._maybe_string(payload.get("object_ref")),
            expected_result_shape=self._maybe_string(payload.get("expected_result_shape")),
            candidate_capabilities=self._maybe_string_list(payload.get("candidate_capabilities")),
            task_type_hint=self._maybe_string(payload.get("task_type_hint")),
            target=self._maybe_string(payload.get("target")),
            aggregation=self._maybe_string(payload.get("aggregation")),
            horizon=self._maybe_int(payload.get("horizon")),
            filters=self._maybe_object_dict(payload.get("filters")),
            group_by=self._maybe_string_list(payload.get("group_by")),
            time_reference=self._maybe_string_dict(payload.get("time_reference")),
            message=self._maybe_string(payload.get("message")),
            warnings=self._maybe_string_list(payload.get("warnings")) or [],
            raw_response=json.dumps(payload),
        )

    def generate_summary(self, summary_context: SummaryContext) -> SummaryProposal | None:
        prompt = self._build_summary_prompt(summary_context)
        payload = self._generate_json(prompt)
        if payload is None:
            return None

        return SummaryProposal(
            status=str(payload.get("status", "ready")),
            summary=self._maybe_string(payload.get("summary")),
            message=self._maybe_string(payload.get("message")),
            warnings=self._maybe_string_list(payload.get("warnings")) or [],
            raw_response=json.dumps(payload),
        )

    def _generate_json(self, prompt: str) -> dict[str, object] | None:
        body = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }
        if self.config.options:
            body["options"] = self.config.options

        http_request = request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.config.timeout_seconds) as response:
                raw_payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            code = "model_missing" if exc.code == 404 else "http_error"
            raise LlmIntegrationError(
                "Ollama request failed during optional LLM handling.",
                code=code,
                provider=self.provider_name,
            ) from exc
        except error.URLError as exc:
            raise LlmIntegrationError(
                "Ollama request failed during optional LLM handling.",
                code="provider_unreachable",
                provider=self.provider_name,
            ) from exc
        except TimeoutError as exc:
            raise LlmIntegrationError(
                "Ollama request timed out during optional LLM handling.",
                code="timeout",
                provider=self.provider_name,
            ) from exc
        except json.JSONDecodeError as exc:
            raise LlmIntegrationError(
                "Ollama returned invalid transport JSON for optional LLM handling.",
                code="invalid_provider_json",
                provider=self.provider_name,
            ) from exc

        response_text = raw_payload.get("response")
        if not isinstance(response_text, str) or not response_text.strip():
            raise LlmIntegrationError(
                "Ollama returned no usable content for optional LLM handling.",
                code="empty_response",
                provider=self.provider_name,
            )

        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise LlmIntegrationError(
                "Ollama returned invalid JSON for optional LLM handling.",
                code="invalid_contract_json",
                provider=self.provider_name,
            ) from exc

        if not isinstance(parsed, dict):
            raise LlmIntegrationError(
                "Ollama returned a non-object JSON payload.",
                code="invalid_payload",
                provider=self.provider_name,
            )
        return parsed

    def _build_intent_prompt(
        self,
        question: str,
        dataset_name: str,
        profile_summary: str,
        context_summary: str | None,
    ) -> str:
        return (
            "You are a prompt interpreter for SAIDA.\n"
            "Return JSON only.\n"
            f"{build_intent_prompt_contract_text()}"
            f"Dataset: {dataset_name}\n"
            f"Profile summary: {profile_summary}\n"
            f"Context summary: {context_summary or 'none'}\n"
            f"Question: {question}\n"
        )

    def _build_summary_prompt(self, summary_context: SummaryContext) -> str:
        return (
            "You are a summary writer for SAIDA.\n"
            "Return JSON only.\n"
            f"{build_summary_contract_text()}"
            f"Question: {summary_context.question}\n"
            f"Dataset: {summary_context.dataset_name}\n"
            f"Task type: {summary_context.task_type}\n"
            f"Deterministic summary: {summary_context.deterministic_summary}\n"
            f"Context summary: {summary_context.context_summary or 'none'}\n"
            f"Metric lookup: {json.dumps(summary_context.metric_lookup, ensure_ascii=True)}\n"
            f"Table index: {json.dumps(summary_context.table_index, ensure_ascii=True)}\n"
            f"Warnings: {json.dumps(summary_context.warnings, ensure_ascii=True)}\n"
        )

    def _maybe_float(self, value: object) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _maybe_int(self, value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _maybe_string(self, value: object) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _maybe_string_dict(self, value: object) -> dict[str, str] | None:
        if not isinstance(value, dict):
            return None
        converted: dict[str, str] = {}
        for key, item in value.items():
            if isinstance(key, str) and isinstance(item, str):
                converted[key] = item
        return converted or None

    def _maybe_object_dict(self, value: object) -> dict[str, object] | None:
        if not isinstance(value, dict):
            return None
        converted: dict[str, object] = {}
        for key, item in value.items():
            if isinstance(key, str):
                converted[key] = item
        return converted or None

    def _maybe_string_list(self, value: object) -> list[str] | None:
        if not isinstance(value, list):
            return None
        return [item for item in value if isinstance(item, str)]
