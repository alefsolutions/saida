from __future__ import annotations

from saida import Saida
from saida.llm import BaseLlmProvider, IntentProposal, ResponseContext, ResponseProposal
from saida.plan_generation import AnalysisPlanGeneratorInterface, LlmAssistedPlanGenerator, OpenAIPlanGenerator
from .factories import build_support_dataset


class CanonicalCountProvider(BaseLlmProvider):
    provider_name = "openai"

    def interpret_prompt(
        self,
        question: str,
        dataset_name: str,
        profile_summary: str,
        context_summary: str | None,
    ) -> IntentProposal | None:
        _ = dataset_name
        _ = profile_summary
        _ = context_summary
        if question == "Count total rows in dataset for Q1":
            return IntentProposal(
                status="ready",
                canonical_question="Count rows for Q1",
                prompt_family_hint="row_count",
                confidence=0.94,
            )
        return IntentProposal(status="ready")

    def generate_response(self, response_context: ResponseContext) -> ResponseProposal | None:
        return ResponseProposal(status="ready", summary=response_context.deterministic_summary)


def test_rule_based_plan_generator_produces_row_count_plan() -> None:
    engine = Saida()
    dataset = build_support_dataset()
    profile = engine.profile(dataset)

    generation = engine.rule_based_plan_generator.generate("How many rows do we have?", dataset, profile, dataset.context)

    assert isinstance(engine.rule_based_plan_generator, AnalysisPlanGeneratorInterface)
    assert generation.generator_name == "rule_based"
    assert generation.request.intent_name == "row_count"
    assert generation.plan.steps[0].action == "row_count"
    assert generation.terminal_summary is None


def test_llm_assisted_plan_generator_returns_candidate_plan_and_trace() -> None:
    provider = CanonicalCountProvider()
    engine = Saida(llm_provider=provider)
    dataset = build_support_dataset()
    profile = engine.profile(dataset)
    generator = LlmAssistedPlanGenerator(engine.canonicalizer, engine.plan_builder, provider)

    generation = generator.generate("Count total rows in dataset for Q1", dataset, profile, dataset.context)

    assert isinstance(generator, AnalysisPlanGeneratorInterface)
    assert generation.trace_event is not None
    assert generation.trace_event.stage == "llm"
    assert generation.request.intent_name == "row_count"
    assert generation.plan.steps[0].action == "row_count"


def test_engine_uses_named_openai_plan_generator_when_provider_is_openai() -> None:
    provider = CanonicalCountProvider()
    engine = Saida(llm_provider=provider)

    assert isinstance(engine.llm_plan_generator, OpenAIPlanGenerator)
    assert engine.llm_plan_generator.generator_name == "openai_plan_generator"
