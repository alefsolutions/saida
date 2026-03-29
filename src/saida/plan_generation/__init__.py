"""Plan generation subsystem for optional prompt-based frontends."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "AnalysisPlanGeneratorInterface",
    "AnalysisPlanner",
    "build_default_prompt_family_catalog",
    "build_intent_prompt_contract_text",
    "build_prompt_plan_contract",
    "build_summary_contract_text",
    "derive_prompt_contract_status",
    "derive_prompt_family",
    "EntityExtractionResult",
    "FrontendIntent",
    "get_llm_contract",
    "InputCanonicalizer",
    "LlmAssistedPlanGenerator",
    "OpenAIPlanGenerator",
    "PlanBuilder",
    "PlanGenerationResult",
    "PromptEntityExtractor",
    "PromptIntentResolver",
    "PromptPlanContract",
    "PromptAnalysisFrontend",
    "RequestNormalizer",
    "RuleBasedPlanGenerator",
]

_EXPORT_TO_MODULE = {
    "build_intent_prompt_contract_text": "saida.plan_generation.llm_contract",
    "build_summary_contract_text": "saida.plan_generation.llm_contract",
    "get_llm_contract": "saida.plan_generation.llm_contract",
    "EntityExtractionResult": "saida.plan_generation.entities",
    "PromptEntityExtractor": "saida.plan_generation.entities",
    "InputCanonicalizer": "saida.plan_generation.canonicalization",
    "FrontendIntent": "saida.plan_generation.intent",
    "PromptIntentResolver": "saida.plan_generation.intent",
    "RequestNormalizer": "saida.plan_generation.canonicalization",
    "PromptAnalysisFrontend": "saida.plan_generation.frontend",
    "LlmAssistedPlanGenerator": "saida.plan_generation.generators",
    "OpenAIPlanGenerator": "saida.plan_generation.generators",
    "RuleBasedPlanGenerator": "saida.plan_generation.generators",
    "AnalysisPlanGeneratorInterface": "saida.plan_generation.interfaces",
    "PlanGenerationResult": "saida.plan_generation.interfaces",
    "AnalysisPlanner": "saida.plan_generation.planning",
    "PlanBuilder": "saida.plan_generation.planning",
    "PromptPlanContract": "saida.plan_generation.planning",
    "build_prompt_plan_contract": "saida.plan_generation.planning",
    "derive_prompt_contract_status": "saida.plan_generation.planning",
    "build_default_prompt_family_catalog": "saida.plan_generation.prompt_family_catalog",
    "derive_prompt_family": "saida.plan_generation.prompt_family_catalog",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_TO_MODULE.get(name)
    if module_name is None:
        raise AttributeError(f"module 'saida.plan_generation' has no attribute {name!r}")
    module = import_module(module_name)
    return getattr(module, name)
