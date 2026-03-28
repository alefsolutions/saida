"""Built-in plan generator implementations."""

from __future__ import annotations

from saida.plan_generation.planning import PlanBuilder
from saida.core.contracts import AnalysisPlan, AnalysisRequest, Dataset, DatasetProfile, ExecutionTraceEvent, SourceContext
from saida.exceptions import LlmIntegrationError, PlanningError
from saida.llm import BaseLlmProvider
from saida.plan_generation.canonicalization import InputCanonicalizer
from saida.plan_generation.interfaces import AnalysisPlanGeneratorInterface, PlanGenerationResult
from saida.plan_generation.prompt_capability_contract import build_prompt_capability_contract


class RuleBasedPlanGenerator(AnalysisPlanGeneratorInterface):
    """Generate plans deterministically from the built-in canonicalizer."""

    def __init__(self, canonicalizer: InputCanonicalizer, plan_builder: PlanBuilder) -> None:
        self.canonicalizer = canonicalizer
        self.plan_builder = plan_builder

    @property
    def generator_name(self) -> str:
        return "rule_based"

    def generate(
        self,
        question: str,
        dataset: Dataset,
        profile: DatasetProfile,
        context: SourceContext | None,
    ) -> PlanGenerationResult:
        request, request_warnings = self.canonicalizer.normalize(question, dataset, profile, context)
        return _compile_plan_generation_result(
            question=question,
            request=request,
            request_warnings=request_warnings,
            plan_builder=self.plan_builder,
            profile=profile,
            context=context,
            trace_event=None,
            generator_name=self.generator_name,
        )


class LlmAssistedPlanGenerator(AnalysisPlanGeneratorInterface):
    """Generate candidate plans with optional LLM assistance before deterministic validation."""

    def __init__(
        self,
        canonicalizer: InputCanonicalizer,
        plan_builder: PlanBuilder,
        llm_provider: BaseLlmProvider,
    ) -> None:
        self.canonicalizer = canonicalizer
        self.plan_builder = plan_builder
        self.llm_provider = llm_provider

    @property
    def generator_name(self) -> str:
        return "llm_assisted"

    def generate(
        self,
        question: str,
        dataset: Dataset,
        profile: DatasetProfile,
        context: SourceContext | None,
    ) -> PlanGenerationResult:
        try:
            proposal = self.llm_provider.interpret_prompt(
                question=question,
                dataset_name=dataset.name,
                profile_summary=_profile_summary(profile),
                context_summary=_context_summary(context),
            )
        except LlmIntegrationError:
            request, warnings = self.canonicalizer.normalize(question, dataset, profile, context)
            warnings.append("Optional LLM prompting failed; falling back to deterministic request normalization.")
            return _compile_plan_generation_result(
                question=question,
                request=request,
                request_warnings=warnings,
                plan_builder=self.plan_builder,
                profile=profile,
                context=context,
                trace_event=ExecutionTraceEvent(stage="llm", message="prompt interpretation failed", payload={"fallback": "rules"}),
                generator_name=self.generator_name,
            )

        if proposal is None:
            request, warnings = self.canonicalizer.normalize(question, dataset, profile, context)
            warnings.append("Optional LLM prompting was unavailable; falling back to deterministic request normalization.")
            return _compile_plan_generation_result(
                question=question,
                request=request,
                request_warnings=warnings,
                plan_builder=self.plan_builder,
                profile=profile,
                context=context,
                trace_event=ExecutionTraceEvent(stage="llm", message="prompt interpretation skipped", payload={"fallback": "rules"}),
                generator_name=self.generator_name,
            )

        if proposal.status in {"clarify", "refuse"}:
            fallback_request, fallback_warnings = self.canonicalizer.normalize(question, dataset, profile, context)
            if _is_confident_deterministic_request(fallback_request, fallback_warnings):
                fallback_warnings.append(
                    "Optional LLM prompting requested clarification or refusal, but deterministic request normalization found a valid supported intent."
                )
                return _compile_plan_generation_result(
                    question=question,
                    request=fallback_request,
                    request_warnings=fallback_warnings,
                    plan_builder=self.plan_builder,
                    profile=profile,
                    context=context,
                    trace_event=ExecutionTraceEvent(
                        stage="llm",
                        message="early LLM outcome overridden by deterministic request normalization",
                        payload={"status": proposal.status},
                    ),
                    generator_name=self.generator_name,
                )

            request = AnalysisRequest(
                question=question,
                task_type_hint=None,
                target=None,
                options={
                    "dataset": dataset.name,
                    "nlp_backend": "llm+validation",
                    "analysis_outcome": proposal.status,
                    "llm_message": proposal.message,
                },
            )
            return _compile_plan_generation_result(
                question=question,
                request=request,
                request_warnings=list(proposal.warnings),
                plan_builder=self.plan_builder,
                profile=profile,
                context=context,
                trace_event=ExecutionTraceEvent(
                    stage="llm",
                    message="prompt interpretation returned early outcome",
                    payload={"status": proposal.status},
                ),
                generator_name=self.generator_name,
            )

        request, warnings = self.canonicalizer.normalize_with_proposal(question, dataset, profile, proposal, context)
        return _compile_plan_generation_result(
            question=question,
            request=request,
            request_warnings=warnings,
            plan_builder=self.plan_builder,
            profile=profile,
            context=context,
            trace_event=ExecutionTraceEvent(stage="llm", message="prompt interpreted by optional LLM", payload={"status": proposal.status}),
            generator_name=self.generator_name,
        )


class OpenAIPlanGenerator(LlmAssistedPlanGenerator):
    """Named OpenAI-backed plan generator for the public architecture surface."""

    @property
    def generator_name(self) -> str:
        return "openai_plan_generator"


def _compile_plan_generation_result(
    *,
    question: str,
    request: AnalysisRequest,
    request_warnings: list[str],
    plan_builder: PlanBuilder,
    profile: DatasetProfile,
    context: SourceContext | None,
    trace_event: ExecutionTraceEvent | None,
    generator_name: str,
) -> PlanGenerationResult:
    capability_contract = build_prompt_capability_contract(request, profile)
    contract_warning_messages = [
        issue.message for issue in capability_contract.validation_issues if issue.severity != "error"
    ]
    terminal_summary: str | None = None

    if request.options.get("analysis_outcome") == "clarify":
        plan = AnalysisPlan(
            task_type="clarification",
            rationale="Optional LLM interpretation requested clarification before planning.",
            steps=[],
            warnings=request_warnings,
        )
        terminal_summary = request.options.get("llm_message") or "We need clarification before running this analysis."
    elif request.options.get("analysis_outcome") == "refuse":
        plan = AnalysisPlan(
            task_type="unavailable",
            rationale="Optional LLM interpretation declined the request before planning.",
            steps=[],
            warnings=request_warnings,
        )
        terminal_summary = request.options.get("llm_message") or "We are not able to provide this information at this time."
    elif capability_contract.status == "unsupported_capability":
        plan = AnalysisPlan(
            task_type="unavailable",
            rationale="Prompt capability contract determined the request is unsupported before planning.",
            steps=[],
            warnings=_merge_warnings(request_warnings, capability_contract.warnings, contract_warning_messages),
        )
        terminal_summary = "The request mapped to capabilities that SAIDA does not currently support."
    elif (
        request.options.get("nlp_backend") == "llm+validation"
        and capability_contract.status in {"supported_but_data_infeasible", "supported_but_data_insufficient"}
    ):
        plan = AnalysisPlan(
            task_type="clarification",
            rationale="Prompt capability contract requires clarification or better data support before planning.",
            steps=[],
            warnings=_merge_warnings(request_warnings, capability_contract.warnings, contract_warning_messages),
        )
        terminal_summary = _contract_guidance_message(capability_contract)
    else:
        try:
            plan = plan_builder.build_plan_from_contract(capability_contract, request, profile, context)
        except PlanningError as exc:
            if request.options.get("nlp_backend") != "llm+validation" or not capability_contract.missing_parameters:
                raise
            plan = AnalysisPlan(
                task_type="clarification",
                rationale="Prompt capability contract could not be compiled into a safe deterministic plan.",
                steps=[],
                warnings=_merge_warnings(request_warnings, capability_contract.warnings, contract_warning_messages),
            )
            terminal_summary = _contract_guidance_message(capability_contract, fallback_message=str(exc))

    return PlanGenerationResult(
        question=question,
        request=request,
        request_warnings=request_warnings,
        capability_contract=capability_contract,
        contract_warning_messages=contract_warning_messages,
        plan=plan,
        terminal_summary=terminal_summary,
        trace_event=trace_event,
        generator_name=generator_name,
    )


def _merge_warnings(*warning_groups: list[str]) -> list[str]:
    merged: list[str] = []
    for warning_group in warning_groups:
        for warning in warning_group:
            if warning not in merged:
                merged.append(warning)
    return merged


def _profile_summary(profile: DatasetProfile) -> str:
    return (
        f"rows={profile.row_count}; columns={profile.column_count}; "
        f"measures={profile.measure_columns}; dimensions={profile.dimension_columns}; "
        f"time_columns={profile.time_columns}; identifiers={profile.identifier_columns}"
    )


def _context_summary(context: SourceContext | None) -> str | None:
    if context is None:
        return None
    parts: list[str] = []
    if context.metric_definitions:
        parts.append(f"metrics={list(context.metric_definitions.keys())}")
    if context.trusted_date_fields:
        parts.append(f"trusted_dates={context.trusted_date_fields}")
    if context.preferred_identifiers:
        parts.append(f"identifiers={context.preferred_identifiers}")
    if context.caveats:
        parts.append(f"caveats={context.caveats}")
    if context.freshness_notes:
        parts.append(f"freshness_notes={context.freshness_notes}")
    if context.business_rules:
        parts.append(f"business_rules={context.business_rules}")
    return "; ".join(parts) if parts else None


def _is_confident_deterministic_request(request: AnalysisRequest, warnings: list[str]) -> bool:
    if warnings:
        return False
    if request.intent_name is not None:
        return True
    if request.aggregation or request.group_by or request.time_reference:
        return True
    return False


def _contract_guidance_message(
    capability_contract: object,
    fallback_message: str | None = None,
) -> str:
    missing_parameters = getattr(capability_contract, "missing_parameters", [])
    issues = getattr(capability_contract, "validation_issues", [])
    if missing_parameters:
        joined = ", ".join(str(parameter) for parameter in missing_parameters)
        return f"We need clarification before running this analysis. Missing or unresolved inputs: {joined}."
    if issues:
        first_message = getattr(issues[0], "message", None)
        if isinstance(first_message, str) and first_message.strip():
            return first_message
    return fallback_message or "We need clarification or better data support before running this analysis."
