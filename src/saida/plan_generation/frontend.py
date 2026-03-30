"""Optional prompt-facing frontend built on top of the core SAIDA runtime."""

from __future__ import annotations

from typing import Any

from saida.config import SaidaConfig
from saida.core.contracts import AnalysisInterpretation, AnalysisPlan, AnalysisResult, Dataset, DatasetProfile
from saida.engine import Saida
from saida.exceptions import AdapterError
from saida.llm import BaseLlmProvider
from saida.plan_generation.canonicalization import InputCanonicalizer
from saida.plan_generation.generators import LlmAssistedPlanGenerator, OpenAIPlanGenerator, RuleBasedPlanGenerator
from saida.plan_generation.planning import PlanBuilder, build_prompt_plan_contract
from saida.plan_generation.source_orchestration import (
    PreparedSourceAnalysis,
    SourceClarification,
    SourceMaterializationResult,
    SourcePlanningContext,
    build_source_clarification,
    build_source_planning_context,
    materialize_source_for_request,
)
from saida.sources.interfaces import SourceInterface


class PromptAnalysisFrontend:
    """Generate candidate plans from prompts, then delegate execution to core SAIDA."""

    def __init__(
        self,
        core_engine: Saida | None = None,
        config: SaidaConfig | None = None,
        llm_provider: BaseLlmProvider | None = None,
    ) -> None:
        self.engine = core_engine or Saida(config=config, llm_provider=llm_provider)
        if config is not None and core_engine is not None:
            self.engine.config = config
        if llm_provider is not None and core_engine is not None:
            self.engine.llm_provider = llm_provider

        self.canonicalizer = InputCanonicalizer(self.engine.config.nlp)
        self.plan_builder = PlanBuilder()
        self.rule_based_plan_generator = RuleBasedPlanGenerator(self.canonicalizer, self.plan_builder)
        self.llm_plan_generator = (
            OpenAIPlanGenerator(self.canonicalizer, self.plan_builder, self.engine.llm_provider)
            if self.engine.llm_provider is not None and getattr(self.engine.llm_provider, "provider_name", None) == "openai"
            else (
                LlmAssistedPlanGenerator(self.canonicalizer, self.plan_builder, self.engine.llm_provider)
                if self.engine.llm_provider is not None
                else None
            )
        )

    def __getattr__(self, name: str) -> Any:
        """Delegate non-prompt surface area to the core engine."""
        return getattr(self.engine, name)

    def capabilities(self) -> dict[str, bool]:
        """Return prompt-frontend capabilities layered on top of the core runtime."""
        capabilities = dict(self.engine.capabilities())
        capabilities.update(
            {
                "analyze": True,
                "analyze_source": True,
                "plan": True,
                "plan_source": True,
                "prompt_plan_contract": True,
                "llm_plan_generation": bool(self.engine.llm_provider and self.engine.config.llm.use_for_prompting),
            }
        )
        return capabilities

    def _generate_plan_result(
        self,
        question: str,
        dataset: Dataset,
        profile: DatasetProfile,
    ):
        generator = (
            self.llm_plan_generator
            if self.llm_plan_generator is not None and self.engine.config.llm.use_for_prompting
            else self.rule_based_plan_generator
        )
        return generator.generate(question, dataset, profile, dataset.context)

    def plan(self, dataset: Dataset, question: str) -> AnalysisPlan:
        """Compile a prompt into a candidate plan through the optional frontend path."""
        self.engine.validator.validate_dataset(dataset)
        profile = self.engine.profile(dataset)
        generation = self._generate_plan_result(question, dataset, profile)
        interpretation = AnalysisInterpretation.from_request(generation.request)
        plan = self.engine._prepare_prompt_generated_plan(generation.plan, dataset, profile, interpretation=interpretation)
        if plan.steps:
            self.engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=self.engine.router)
        return plan

    def plan_source(self, source: SourceInterface, question: str) -> AnalysisPlan:
        """Compile a prompt against a source-aware planning/materialization flow."""
        prepared = self.prepare_source_analysis(source, question)
        return prepared.plan

    def analyze(self, dataset: Dataset, question: str) -> AnalysisResult:
        """Compile a prompt into a plan, then execute it through the core runtime."""
        self.engine.validator.validate_dataset(dataset)
        trace = [self.engine._trace("adapter", "dataset loaded", {"dataset": dataset.name})]
        if dataset.context is not None:
            trace.append(
                self.engine._trace(
                    "context",
                    "context attached",
                    {"metric_count": len(dataset.context.metric_definitions)},
                )
            )

        profile = self.engine.profile(dataset)
        trace.append(self.engine._trace("profiling", "profile generated", {"row_count": profile.row_count}))

        generation = self._generate_plan_result(question, dataset, profile)
        request = generation.request
        interpretation = AnalysisInterpretation.from_request(request)
        if generation.trace_event is not None:
            trace.append(generation.trace_event)
        trace.append(
            self.engine._trace(
                "nlp",
                "request normalized",
                {"task_type": request.task_type_hint, "target": request.target},
            )
        )

        prompt_contract = generation.prompt_contract
        trace.append(
            self.engine._trace(
                "contract",
                "prompt plan contract built",
                {
                    "status": prompt_contract.status,
                    "selected_capabilities": list(prompt_contract.selected_capabilities),
                },
            )
        )

        plan = self.engine._prepare_prompt_generated_plan(generation.plan, dataset, profile, interpretation=interpretation)
        if generation.terminal_summary is not None:
            summary = generation.terminal_summary
            trace.append(self.engine._trace("results", "planning clarification returned", {"summary_length": len(summary)}))
            return self.engine.result_canonicalizer.build_analysis_result(
                summary,
                None,
                None,
                "deterministic",
                [],
                [],
                self.engine._merge_warnings(
                    generation.request_warnings,
                    prompt_contract.warnings,
                    generation.contract_warning_messages,
                ),
                plan,
                interpretation,
                profile,
                trace,
                prompt_contract,
            )

        return self.engine._execute_prepared_plan(
            dataset=dataset,
            question=question,
            interpretation=interpretation,
            profile=profile,
            plan=plan,
            trace=trace,
            prompt_contract=prompt_contract,
            warning_groups=(
                profile.warnings,
                generation.request_warnings,
                prompt_contract.warnings,
                generation.contract_warning_messages,
            ),
        )

    def analyze_source(self, source: SourceInterface, question: str) -> AnalysisResult:
        """Compile and execute a prompt through a source-aware materialization flow."""
        prepared = self.prepare_source_analysis(source, question)
        generation = prepared.generation
        request = generation.request
        interpretation = AnalysisInterpretation.from_request(request)

        trace = [
            self.engine._trace(
                "source",
                "source planning context built",
                {
                    "source_name": prepared.planning_context.source_name,
                    "source_type": prepared.planning_context.source_type,
                    "planning_mode": prepared.planning_context.metadata.get("planning_mode"),
                },
            )
        ]
        if generation.trace_event is not None:
            trace.append(generation.trace_event)
        trace.append(
            self.engine._trace(
                "nlp",
                "request normalized",
                {"task_type": request.task_type_hint, "target": request.target},
            )
        )
        trace.append(
            self.engine._trace(
                "contract",
                "prompt plan contract built",
                {
                    "status": prepared.prompt_contract.status,
                    "selected_capabilities": list(prepared.prompt_contract.selected_capabilities),
                },
            )
        )
        trace.append(
            self.engine._trace(
                "source",
                "source dataset materialized",
                {
                    "mode": prepared.materialization.mode,
                    "source_name": prepared.materialization.metadata.get("source_name"),
                    "generated_query": prepared.materialization.generated_query,
                },
            )
        )

        if generation.terminal_summary is not None:
            summary = generation.terminal_summary
            trace.append(self.engine._trace("results", "planning clarification returned", {"summary_length": len(summary)}))
            return self.engine.result_canonicalizer.build_analysis_result(
                summary,
                None,
                None,
                "deterministic",
                [],
                [],
                self.engine._merge_warnings(
                    generation.request_warnings,
                    prepared.prompt_contract.warnings,
                    generation.contract_warning_messages,
                ),
                prepared.plan,
                interpretation,
                prepared.materialization.profile,
                trace,
                prepared.prompt_contract,
            )

        return self.engine._execute_prepared_plan(
            dataset=prepared.materialization.dataset,
            question=question,
            interpretation=interpretation,
            profile=prepared.materialization.profile,
            plan=prepared.plan,
            trace=trace,
            prompt_contract=prepared.prompt_contract,
            warning_groups=(
                prepared.materialization.profile.warnings,
                generation.request_warnings,
                prepared.prompt_contract.warnings,
                generation.contract_warning_messages,
            ),
        )

    def prepare_source_analysis(self, source: SourceInterface, question: str):
        """Prepare a source-aware prompt analysis without touching the core runtime boundary."""
        planning_context = build_source_planning_context(source, discovery=self.engine.discovery)
        generation = self._generate_plan_result(question, planning_context.dataset, planning_context.profile)
        if generation.terminal_summary is not None:
            materialization = SourceMaterializationResult(
                dataset=planning_context.dataset,
                profile=planning_context.profile,
                mode="skipped",
                source_materialization_request=(
                    dict(generation.request.options.get("source_materialization_request"))
                    if isinstance(generation.request.options.get("source_materialization_request"), dict)
                    else None
                ),
                metadata={
                    "source_name": planning_context.source_name,
                    "source_type": planning_context.source_type,
                    "materialization_skipped": True,
                },
            )
        else:
            try:
                materialization = materialize_source_for_request(source, generation.request, discovery=self.engine.discovery)
            except AdapterError as exc:
                clarification = build_source_clarification(
                    exc,
                    source_name=planning_context.source_name,
                    source_type=planning_context.source_type,
                    source_materialization_request=(
                        dict(generation.request.options.get("source_materialization_request"))
                        if isinstance(generation.request.options.get("source_materialization_request"), dict)
                        else None
                    ),
                )
                self._mark_source_clarification(generation, planning_context, clarification)
                materialization = SourceMaterializationResult(
                    dataset=planning_context.dataset,
                    profile=planning_context.profile,
                    mode="clarification",
                    source_materialization_request=(
                        dict(generation.request.options.get("source_materialization_request"))
                        if isinstance(generation.request.options.get("source_materialization_request"), dict)
                        else None
                    ),
                    metadata={
                        "source_name": planning_context.source_name,
                        "source_type": planning_context.source_type,
                        "clarification": clarification.to_dict(),
                    },
                )
        prompt_contract = build_prompt_plan_contract(generation.request, materialization.profile)
        interpretation = AnalysisInterpretation.from_request(generation.request)
        if generation.terminal_summary is not None:
            plan = generation.plan
            plan.warnings = list(dict.fromkeys([*plan.warnings, *generation.request_warnings]))
        else:
            plan = self.plan_builder.build_plan_from_contract(
                prompt_contract,
                generation.request,
                materialization.profile,
                materialization.dataset.context,
            )
            plan = self.engine._prepare_prompt_generated_plan(
                plan,
                materialization.dataset,
                materialization.profile,
                interpretation=interpretation,
            )
        plan.metadata = dict(plan.metadata)
        plan.metadata["source_orchestration"] = {
            "planning_context": planning_context.to_dict(),
            "materialization": materialization.to_dict(),
        }
        if plan.steps:
            self.engine.validator.validate_plan(
                plan,
                dataset=materialization.dataset,
                profile=materialization.profile,
                router=self.engine.router,
            )
        return PreparedSourceAnalysis(
            planning_context=planning_context,
            materialization=materialization,
            generation=generation,
            prompt_contract=prompt_contract,
            plan=plan,
        )

    def _mark_source_clarification(
        self,
        generation: Any,
        planning_context: SourcePlanningContext,
        clarification: SourceClarification,
    ) -> None:
        generation.request.options["analysis_outcome"] = "clarify"
        generation.request.options["llm_message"] = clarification.message
        generation.request.options["clarification_reason"] = clarification.reason
        warning = (
            f"Source materialization was held for clarification because the relational source could not be "
            f"resolved safely: {clarification.detail}"
        )
        if warning not in generation.request_warnings:
            generation.request_warnings.append(warning)
        generation.terminal_summary = clarification.message
        generation.plan = AnalysisPlan(
            task_type="clarification",
            rationale=(
                "Relational source materialization requires clarification before SAIDA can prepare "
                f"a dataset for {planning_context.source_name}."
            ),
            steps=[],
            warnings=list(generation.request_warnings),
        )
