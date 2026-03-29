from __future__ import annotations

from saida import PromptAnalysisFrontend
from saida.llm import BaseLlmProvider, IntentProposal, SummaryContext, SummaryProposal
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

    def generate_summary(self, summary_context: SummaryContext) -> SummaryProposal | None:
        return SummaryProposal(status="ready", summary=summary_context.deterministic_summary)


class GroundedEntityProvider(BaseLlmProvider):
    provider_name = "openai"

    def __init__(self) -> None:
        self.last_context_summary: str | None = None

    def interpret_prompt(
        self,
        question: str,
        dataset_name: str,
        profile_summary: str,
        context_summary: str | None,
    ) -> IntentProposal | None:
        _ = question
        _ = dataset_name
        _ = profile_summary
        self.last_context_summary = context_summary
        return IntentProposal(status="ready")

    def generate_summary(self, summary_context: SummaryContext) -> SummaryProposal | None:
        return SummaryProposal(status="ready", summary=summary_context.deterministic_summary)


class TimeBucketRewriteProvider(BaseLlmProvider):
    provider_name = "openai"

    def interpret_prompt(
        self,
        question: str,
        dataset_name: str,
        profile_summary: str,
        context_summary: str | None,
    ) -> IntentProposal | None:
        _ = question
        _ = dataset_name
        _ = profile_summary
        _ = context_summary
        return IntentProposal(
            status="ready",
            canonical_question="Show total total_sales grouped by month from order_date.",
            target="total_sales",
            aggregation="sum",
            operation="sum",
            object_kind="measure",
            object_ref="total_sales",
            expected_result_shape="table",
            confidence=1.0,
        )

    def generate_summary(self, summary_context: SummaryContext) -> SummaryProposal | None:
        return SummaryProposal(status="ready", summary=summary_context.deterministic_summary)


def test_rule_based_plan_generator_produces_row_count_plan() -> None:
    engine = PromptAnalysisFrontend()
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
    engine = PromptAnalysisFrontend(llm_provider=provider)
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
    engine = PromptAnalysisFrontend(llm_provider=provider)

    assert isinstance(engine.llm_plan_generator, OpenAIPlanGenerator)
    assert engine.llm_plan_generator.generator_name == "openai_plan_generator"


def test_llm_assisted_plan_generator_passes_grounded_entity_summary_to_provider() -> None:
    provider = GroundedEntityProvider()
    engine = PromptAnalysisFrontend(llm_provider=provider)
    dataset = build_support_dataset()
    dataset.data = dataset.data.rename(columns={"resolution_hours": "total_sales"})
    profile = engine.profile(dataset)
    generator = LlmAssistedPlanGenerator(engine.canonicalizer, engine.plan_builder, provider)

    generation = generator.generate("Does the dataset contain a total_sales column?", dataset, profile, dataset.context)

    assert generation.request.options["requested_column"] == "total_sales"
    assert provider.last_context_summary is not None
    assert "Resolved fields: total_sales." in provider.last_context_summary
    assert "Masked question: Does the dataset contain a [ENTITY] column?." in provider.last_context_summary


def test_llm_assisted_plan_generator_keeps_time_bucket_breakdown_for_grouped_month_rewrite() -> None:
    provider = TimeBucketRewriteProvider()
    engine = PromptAnalysisFrontend(llm_provider=provider)
    dataset = build_support_dataset()
    dataset.data = dataset.data.rename(columns={"resolution_hours": "total_sales", "created_at": "order_date"})
    profile = engine.profile(dataset)
    generator = LlmAssistedPlanGenerator(engine.canonicalizer, engine.plan_builder, provider)

    generation = generator.generate("Show total total_sales by month.", dataset, profile, dataset.context)

    assert generation.request.intent_name == "time_bucket_breakdown"
    assert generation.request.prompt_family == "time_bucket_breakdown"
    assert generation.request.options["time_bucket"] == "month"
    assert [step.action for step in generation.plan.steps] == ["time_bucket_frame", "aggregate_frame"]
