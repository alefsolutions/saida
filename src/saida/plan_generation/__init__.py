"""Plan generation subsystem for optional prompt-based frontends."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "AnalysisPlanGeneratorInterface",
    "AnalysisPlanner",
    "build_default_prompt_family_catalog",
    "build_intent_prompt_contract_text",
    "build_prompt_capability_contract",
    "build_response_contract_text",
    "CapabilityActivation",
    "DataFeasibilityCheck",
    "derive_contract_status",
    "derive_prompt_family",
    "get_capability_contract",
    "get_prompt_family_catalog",
    "InputCanonicalizer",
    "LlmAssistedPlanGenerator",
    "OpenAIPlanGenerator",
    "PlanBuilder",
    "PlanGenerationResult",
    "PromptCapabilityContract",
    "PromptFamilyCatalog",
    "PromptFamilyPlanStepSpec",
    "PromptFamilyResultSpec",
    "PromptFamilySpec",
    "PromptFamilyValueSpec",
    "PromptAnalysisFrontend",
    "RequestNormalizer",
    "ResolvedParameter",
    "RuleBasedPlanGenerator",
    "ValidationIssue",
]

_EXPORT_TO_MODULE = {
    "build_intent_prompt_contract_text": "saida.plan_generation.capability_contract",
    "build_response_contract_text": "saida.plan_generation.capability_contract",
    "get_capability_contract": "saida.plan_generation.capability_contract",
    "InputCanonicalizer": "saida.plan_generation.canonicalization",
    "RequestNormalizer": "saida.plan_generation.canonicalization",
    "PromptAnalysisFrontend": "saida.plan_generation.frontend",
    "LlmAssistedPlanGenerator": "saida.plan_generation.generators",
    "OpenAIPlanGenerator": "saida.plan_generation.generators",
    "RuleBasedPlanGenerator": "saida.plan_generation.generators",
    "AnalysisPlanGeneratorInterface": "saida.plan_generation.interfaces",
    "PlanGenerationResult": "saida.plan_generation.interfaces",
    "AnalysisPlanner": "saida.plan_generation.planning",
    "PlanBuilder": "saida.plan_generation.planning",
    "CapabilityActivation": "saida.plan_generation.prompt_capability_contract",
    "DataFeasibilityCheck": "saida.plan_generation.prompt_capability_contract",
    "PromptCapabilityContract": "saida.plan_generation.prompt_capability_contract",
    "ResolvedParameter": "saida.plan_generation.prompt_capability_contract",
    "ValidationIssue": "saida.plan_generation.prompt_capability_contract",
    "build_prompt_capability_contract": "saida.plan_generation.prompt_capability_contract",
    "derive_contract_status": "saida.plan_generation.prompt_capability_contract",
    "PromptFamilyCatalog": "saida.plan_generation.prompt_family_catalog",
    "PromptFamilyPlanStepSpec": "saida.plan_generation.prompt_family_catalog",
    "PromptFamilyResultSpec": "saida.plan_generation.prompt_family_catalog",
    "PromptFamilySpec": "saida.plan_generation.prompt_family_catalog",
    "PromptFamilyValueSpec": "saida.plan_generation.prompt_family_catalog",
    "build_default_prompt_family_catalog": "saida.plan_generation.prompt_family_catalog",
    "derive_prompt_family": "saida.plan_generation.prompt_family_catalog",
    "get_prompt_family_catalog": "saida.plan_generation.prompt_family_catalog",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_TO_MODULE.get(name)
    if module_name is None:
        raise AttributeError(f"module 'saida.plan_generation' has no attribute {name!r}")
    module = import_module(module_name)
    return getattr(module, name)
