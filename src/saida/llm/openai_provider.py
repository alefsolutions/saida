"""OpenAI-backed provider implementation."""

from __future__ import annotations

import json
import os
from urllib import error, request

from saida.config import LlmConfig
from saida.core.capability_contract import build_intent_prompt_contract_text, build_response_contract_text
from saida.exceptions import ReasoningError
from saida.llm.base import BaseLlmProvider
from saida.llm.models import IntentProposal, ResponseContext, ResponseProposal


class OpenAiLlmProvider(BaseLlmProvider):
    """Use the OpenAI Responses API for optional prompt and response handling."""

    provider_name = "openai"

    def __init__(self, config: LlmConfig) -> None:
        self.config = config
        self.model = config.model or "gpt-4.1-mini"
        self.base_url = (config.base_url or "https://api.openai.com/v1").rstrip("/")
        self.api_key = (
            config.options.get("api_key")
            if isinstance(config.options, dict) and "api_key" in config.options
            else os.getenv("OPENAI_API_KEY")
        )

    def interpret_prompt(
        self,
        question: str,
        dataset_name: str,
        profile_summary: str,
        context_summary: str | None,
    ) -> IntentProposal | None:
        payload = self._responses_json(
            self._build_intent_prompt(question, dataset_name, profile_summary, context_summary),
            max_output_tokens=500,
        )
        if payload is None:
            return None

        return IntentProposal(
            status=str(payload.get("status", "ready")),
            candidate_capabilities=self._maybe_string_list(payload.get("candidate_capabilities")),
            task_type_hint=self._maybe_string(payload.get("task_type_hint")),
            target=self._maybe_string(payload.get("target")),
            aggregation=self._maybe_string(payload.get("aggregation")),
            horizon=self._maybe_int(payload.get("horizon")),
            filters=self._maybe_string_dict(payload.get("filters")),
            group_by=self._maybe_string_list(payload.get("group_by")),
            time_reference=self._maybe_string_dict(payload.get("time_reference")),
            message=self._maybe_string(payload.get("message")),
            warnings=self._maybe_string_list(payload.get("warnings")) or [],
            raw_response=json.dumps(payload),
        )

    def generate_response(self, response_context: ResponseContext) -> ResponseProposal | None:
        payload = self._responses_json(self._build_response_prompt(response_context), max_output_tokens=500)
        if payload is None:
            return None

        return ResponseProposal(
            status=str(payload.get("status", "ready")),
            summary=self._maybe_string(payload.get("summary")),
            message=self._maybe_string(payload.get("message")),
            warnings=self._maybe_string_list(payload.get("warnings")) or [],
            raw_response=json.dumps(payload),
        )

    def _responses_json(self, prompt: str, max_output_tokens: int) -> dict[str, object] | None:
        if not self.api_key:
            raise ReasoningError("OpenAI API key is not configured for optional LLM handling.")

        body = {
            "model": self.model,
            "input": prompt,
            "text": {"format": {"type": "json_object"}},
            "max_output_tokens": max_output_tokens,
        }

        http_request = request.Request(
            f"{self.base_url}/responses",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.config.timeout_seconds) as response:
                raw_payload = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ReasoningError("OpenAI request failed during optional LLM handling.") from exc

        response_text = self._extract_output_text(raw_payload)
        if not response_text:
            return None

        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise ReasoningError("OpenAI returned invalid JSON for optional LLM handling.") from exc

        if not isinstance(parsed, dict):
            raise ReasoningError("OpenAI returned a non-object JSON payload.")
        return parsed

    def _extract_output_text(self, raw_payload: dict[str, object]) -> str | None:
        output = raw_payload.get("output")
        if not isinstance(output, list):
            return None
        for item in output:
            if not isinstance(item, dict):
                continue
            contents = item.get("content")
            if not isinstance(contents, list):
                continue
            for content in contents:
                if not isinstance(content, dict):
                    continue
                text_value = content.get("text")
                if isinstance(text_value, str) and text_value.strip():
                    return text_value.strip()
        return None

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

    def _build_response_prompt(self, response_context: ResponseContext) -> str:
        return (
            "You are a response writer for SAIDA.\n"
            "Return JSON only.\n"
            f"{build_response_contract_text()}"
            f"Question: {response_context.question}\n"
            f"Dataset: {response_context.dataset_name}\n"
            f"Task type: {response_context.task_type}\n"
            f"Deterministic summary: {response_context.deterministic_summary}\n"
            f"Context summary: {response_context.context_summary or 'none'}\n"
            f"Metric lookup: {json.dumps(response_context.metric_lookup, ensure_ascii=True)}\n"
            f"Table index: {json.dumps(response_context.table_index, ensure_ascii=True)}\n"
            f"Warnings: {json.dumps(response_context.warnings, ensure_ascii=True)}\n"
        )

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

    def _maybe_string_list(self, value: object) -> list[str] | None:
        if not isinstance(value, list):
            return None
        return [item for item in value if isinstance(item, str)]
