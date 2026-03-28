"""Optional prompt-facing frontend built on top of the core SAIDA runtime."""

from __future__ import annotations

from typing import Any

from saida.config import SaidaConfig
from saida.core.contracts import AnalysisInterpretation, AnalysisPlan, AnalysisResult, Dataset, DatasetProfile
from saida.engine import Saida
from saida.llm import BaseLlmProvider
from saida.plan_generation.canonicalization import InputCanonicalizer
from saida.plan_generation.generators import LlmAssistedPlanGenerator, OpenAIPlanGenerator, RuleBasedPlanGenerator
from saida.plan_generation.planning import PlanBuilder


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
                "plan": True,
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
        plan = self.engine._bind_plan_to_dataset(generation.plan, dataset, profile, interpretation=interpretation)
        if plan.steps:
            self.engine.validator.validate_plan(plan, dataset=dataset, profile=profile, router=self.engine.router)
        return plan

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

        plan = self.engine._bind_plan_to_dataset(generation.plan, dataset, profile, interpretation=interpretation)
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
