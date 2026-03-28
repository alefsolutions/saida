"""Structured prompt-to-plan compilation for the optional frontend."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from saida.core.analytics_registry import get_analytics_registry
from saida.exceptions import PlanningError
from saida.core.contracts import AnalysisPlan, AnalysisRequest, DatasetProfile, PlanStep, SourceContext
from saida.plan_generation.prompt_family_catalog import derive_prompt_family, get_prompt_family_catalog


_PROMPT_FAMILY_TO_INTENT = {
    "row_count": "row_count",
    "distinct_value_count": "distinct_value_count",
    "distinct_value_listing": "distinct_values",
    "representation_ranking": "representation_ranking",
    "row_ranking": "row_ranking",
    "group_ranking": "group_ranking",
    "column_count": "column_count",
    "column_inventory": "column_inventory",
    "column_type_lookup": "column_type_inventory",
    "column_type_inventory": "column_type_inventory",
    "numeric_column_count": "numeric_column_count",
    "numeric_column_inventory": "numeric_column_inventory",
    "categorical_column_count": "categorical_column_count",
    "categorical_column_inventory": "categorical_column_inventory",
    "measure_count": "measure_count",
    "measure_inventory": "measure_inventory",
    "dimension_count": "dimension_count",
    "dimension_inventory": "dimension_inventory",
    "time_column_count": "time_column_count",
    "time_column_inventory": "time_column_inventory",
    "missing_value_inventory": "missing_value_inventory",
    "identifier_count": "identifier_count",
    "identifier_inventory": "identifier_inventory",
    "high_cardinality_count": "high_cardinality_count",
    "high_cardinality_inventory": "high_cardinality_inventory",
    "column_presence_check": "existence_check",
    "column_property_check": "existence_check",
    "null_verification": "existence_check",
    "threshold_verification": "existence_check",
    "time_value_verification": "existence_check",
    "row_existence_check": "existence_check",
    "time_coverage": "time_coverage",
    "time_bucket_counts": "time_bucket_counts",
    "time_bucket_breakdown": "time_bucket_breakdown",
    "time_period_comparison": "time_period_comparison",
    "tabular_record_retrieval": "tabular_query",
    "grouped_entity_count": "grouped_tabular_query",
    "grouped_metric_table": "grouped_tabular_query",
}

_PROMPT_FAMILY_TO_EXISTENCE_MODE = {
    "column_presence_check": "column_presence_check",
    "column_property_check": "column_property_check",
    "null_verification": "null_check",
    "threshold_verification": "threshold_check",
    "time_value_verification": "time_value",
    "row_existence_check": "row_existence",
}

_STATISTICAL_PROMPT_FAMILIES = {
    "significance_inference",
    "confidence_interval",
    "power_analysis",
    "sample_size_estimate",
    "t_test",
    "anova",
    "mann_whitney",
    "regression_significance",
    "chi_square",
}

_METADATA_PROMPT_FAMILY_TO_ACTION = {
    "column_count": "column_count",
    "column_inventory": "column_inventory",
    "column_type_lookup": "column_type_inventory",
    "column_type_inventory": "column_type_inventory",
    "numeric_column_count": "numeric_column_count",
    "numeric_column_inventory": "numeric_column_inventory",
    "categorical_column_count": "categorical_column_count",
    "categorical_column_inventory": "categorical_column_inventory",
    "measure_count": "measure_count",
    "measure_inventory": "measure_inventory",
    "dimension_count": "dimension_count",
    "dimension_inventory": "dimension_inventory",
    "time_column_count": "time_column_count",
    "time_column_inventory": "time_column_inventory",
    "missing_value_inventory": "missing_value_inventory",
    "identifier_count": "identifier_count",
    "identifier_inventory": "identifier_inventory",
    "high_cardinality_count": "high_cardinality_count",
    "high_cardinality_inventory": "high_cardinality_inventory",
}

PromptContractStatus = Literal[
    "supported_and_data_feasible",
    "supported_but_data_infeasible",
    "supported_but_data_insufficient",
    "supported_with_partial_fallback",
    "unsupported_capability",
]
IssueSeverity = Literal["error", "warning", "info"]
RequirementStatus = Literal["satisfied", "missing", "insufficient", "unknown"]
ParameterSource = Literal["prompt", "llm", "rule", "context", "default", "derived"]

_TASK_TYPE_TO_DOMAINS = {
    "descriptive": ["descriptive"],
    "diagnostic": ["diagnostic"],
    "statistical": ["statistical"],
    "predictive": ["predictive"],
    "forecasting": ["predictive", "trend"],
}

_INTENT_TO_PATTERNS = {
    "column_inventory": ["metadata_inventory"],
    "column_type_inventory": ["metadata_inventory"],
    "numeric_column_inventory": ["metadata_inventory"],
    "categorical_column_inventory": ["metadata_inventory"],
    "measure_inventory": ["metadata_inventory"],
    "dimension_inventory": ["metadata_inventory"],
    "time_column_inventory": ["metadata_inventory"],
    "missing_value_inventory": ["metadata_inventory"],
    "identifier_inventory": ["metadata_inventory"],
    "high_cardinality_inventory": ["metadata_inventory"],
    "distinct_values": ["distinct_value_listing"],
    "representation_ranking": ["representation_ranking"],
    "row_ranking": ["top_n_by_metric"],
    "group_ranking": ["top_n_by_metric", "segmentation"],
    "time_coverage": ["grouped_trend"],
    "time_bucket_counts": ["grouped_trend"],
    "time_bucket_breakdown": ["grouped_trend"],
    "time_period_comparison": ["period_over_period_comparison"],
    "tabular_query": ["tabular_record_retrieval"],
    "grouped_tabular_query": ["grouped_tabular_retrieval", "segmentation"],
}

_STATISTICAL_TEST_TO_PATTERNS = {
    "significance_inference": ["significance_inference"],
    "confidence_interval": ["confidence_interval"],
    "power_analysis": ["power_analysis"],
    "sample_size_estimate": ["sample_size_estimate"],
}

_CONSTRAINT_PARAMETER_NAMES = {
    "requires_metric": "target",
    "requires_dimension": "group_by",
    "requires_time_field": "time_columns",
    "requires_reference_period": "time_reference",
    "requires_target_column": "target",
    "requires_filter": "filters",
}


@dataclass(slots=True)
class CapabilityActivation:
    """A candidate or selected analytics concept activated by the prompt."""

    capability_id: str
    category: str
    confidence: float | None = None
    source: str = "derived"
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ResolvedParameter:
    """Resolved prompt-side parameter captured before plan compilation."""

    name: str
    value: Any
    source: ParameterSource
    confidence: float | None = None
    resolved_from: str | None = None


@dataclass(slots=True)
class ValidationIssue:
    """Structured validation issue raised during prompt-to-plan compilation."""

    code: str
    severity: IssueSeverity
    message: str
    capability_id: str | None = None
    parameter_name: str | None = None


@dataclass(slots=True)
class DataFeasibilityCheck:
    """Outcome of a prompt-side support or data check."""

    requirement: str
    status: RequirementStatus
    detail: str
    capability_id: str | None = None
    field_names: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PromptPlanContract:
    """Typed bridge between normalized prompt input and plan compilation."""

    question: str
    dataset_name: str
    status: PromptContractStatus
    prompt_family: str | None = None
    task_type_hint: str | None = None
    intent_name: str | None = None
    family_spec: dict[str, Any] | None = None
    analytics_family_ids: list[str] = field(default_factory=list)
    analytics_method_ids: list[str] = field(default_factory=list)
    candidate_capabilities: list[CapabilityActivation] = field(default_factory=list)
    selected_capabilities: list[str] = field(default_factory=list)
    resolved_parameters: list[ResolvedParameter] = field(default_factory=list)
    missing_parameters: list[str] = field(default_factory=list)
    unsupported_capabilities: list[str] = field(default_factory=list)
    ambiguity_flags: list[str] = field(default_factory=list)
    validation_issues: list[ValidationIssue] = field(default_factory=list)
    data_feasibility: list[DataFeasibilityCheck] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def parameter_map(self) -> dict[str, Any]:
        return {parameter.name: parameter.value for parameter in self.resolved_parameters}

    def has_blocking_issues(self) -> bool:
        return any(issue.severity == "error" for issue in self.validation_issues)

    def refresh_status(self) -> PromptContractStatus:
        self.status = derive_prompt_contract_status(self)
        return self.status

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "dataset_name": self.dataset_name,
            "status": self.status,
            "prompt_family": self.prompt_family,
            "task_type_hint": self.task_type_hint,
            "intent_name": self.intent_name,
            "family_spec": dict(self.family_spec or {}) if self.family_spec is not None else None,
            "analytics_family_ids": list(self.analytics_family_ids),
            "analytics_method_ids": list(self.analytics_method_ids),
            "candidate_capabilities": [
                {
                    "capability_id": candidate.capability_id,
                    "category": candidate.category,
                    "confidence": candidate.confidence,
                    "source": candidate.source,
                    "evidence": list(candidate.evidence),
                }
                for candidate in self.candidate_capabilities
            ],
            "selected_capabilities": list(self.selected_capabilities),
            "resolved_parameters": [
                {
                    "name": parameter.name,
                    "value": parameter.value,
                    "source": parameter.source,
                    "confidence": parameter.confidence,
                    "resolved_from": parameter.resolved_from,
                }
                for parameter in self.resolved_parameters
            ],
            "missing_parameters": list(self.missing_parameters),
            "unsupported_capabilities": list(self.unsupported_capabilities),
            "ambiguity_flags": list(self.ambiguity_flags),
            "validation_issues": [
                {
                    "code": issue.code,
                    "severity": issue.severity,
                    "message": issue.message,
                    "capability_id": issue.capability_id,
                    "parameter_name": issue.parameter_name,
                }
                for issue in self.validation_issues
            ],
            "data_feasibility": [
                {
                    "requirement": check.requirement,
                    "status": check.status,
                    "detail": check.detail,
                    "capability_id": check.capability_id,
                    "field_names": list(check.field_names),
                }
                for check in self.data_feasibility
            ],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }


def build_prompt_plan_contract(
    request: AnalysisRequest,
    profile: DatasetProfile,
    registry: object | None = None,
) -> PromptPlanContract:
    """Build the prompt-side contract used before plan compilation."""

    active_registry = registry or get_analytics_registry()
    family_catalog = get_prompt_family_catalog()
    prompt_family = request.prompt_family or derive_prompt_family(request, family_catalog)
    family_spec = family_catalog.get(prompt_family)
    analytics_method_ids = _resolve_analytics_methods(request, family_spec)
    analytics_family_ids = sorted(
        {
            family_id
            for family_id in (active_registry.family_for_method(method_id) for method_id in analytics_method_ids)
            if family_id is not None
        }
    )
    selected_capabilities = _select_capabilities(request, active_registry)
    candidate_capabilities = _build_capability_activations(request, selected_capabilities, active_registry)
    resolved_parameters = _build_resolved_parameters(request)
    data_feasibility, missing_parameters, issues = _evaluate_feasibility(
        request,
        profile,
        selected_capabilities,
        active_registry,
    )

    warnings: list[str] = []
    notes: list[str] = [
        "This contract is an optional frontend artifact derived from the normalized AnalysisRequest.",
        "Core SAIDA still validates and executes only authored or generated AnalysisPlan objects.",
    ]
    if prompt_family is None:
        warnings.append("No explicit prompt family was derived from the normalized request.")
    elif family_spec is not None:
        family_issues = family_spec.request_invariant_issues(request)
        if family_issues:
            issues.extend(
                ValidationIssue(
                    code="prompt_family_request_invariant",
                    severity="warning",
                    message=message,
                    capability_id=prompt_family,
                )
                for message in family_issues
            )
        else:
            notes.append(f"Prompt family {prompt_family!r} matched the request-level family invariants.")

    if request.options.get("analysis_outcome") == "clarify":
        warnings.append(
            "The normalized request stopped before planning because no safe supported prompt family or metric target could be resolved."
        )
    elif request.options.get("target_resolution_source") == "first_measure_fallback":
        warnings.append("The normalized request used the first measure fallback inside exploratory metric overview.")

    prompt_contract = PromptPlanContract(
        question=request.question,
        dataset_name=profile.dataset_name,
        status="supported_and_data_feasible",
        prompt_family=prompt_family,
        task_type_hint=request.task_type_hint,
        intent_name=request.intent_name,
        family_spec=family_spec.to_dict() if family_spec is not None else None,
        analytics_family_ids=analytics_family_ids,
        analytics_method_ids=analytics_method_ids,
        candidate_capabilities=candidate_capabilities,
        selected_capabilities=selected_capabilities,
        resolved_parameters=resolved_parameters,
        missing_parameters=missing_parameters,
        unsupported_capabilities=[
            capability_id
            for capability_id in selected_capabilities
            if active_registry.get_concept(capability_id) is None
        ],
        ambiguity_flags=_derive_ambiguity_flags(request),
        validation_issues=issues,
        data_feasibility=data_feasibility,
        warnings=warnings,
        notes=notes,
    )
    prompt_contract.refresh_status()
    return prompt_contract


def derive_prompt_contract_status(prompt_contract: PromptPlanContract) -> PromptContractStatus:
    """Derive the high-level prompt contract status."""

    if prompt_contract.unsupported_capabilities:
        return "unsupported_capability"
    if any(check.status == "insufficient" for check in prompt_contract.data_feasibility):
        return "supported_but_data_insufficient"
    if prompt_contract.missing_parameters or prompt_contract.ambiguity_flags:
        return "supported_with_partial_fallback"
    if prompt_contract.has_blocking_issues():
        return "supported_but_data_infeasible"
    return "supported_and_data_feasible"


def _select_capabilities(request: AnalysisRequest, registry: object) -> list[str]:
    selected: list[str] = []

    for capability_id in _TASK_TYPE_TO_DOMAINS.get(request.task_type_hint or "", []):
        if registry.get_concept(capability_id) is not None:
            selected.append(capability_id)

    for capability_id in _INTENT_TO_PATTERNS.get(request.intent_name or "", []):
        if registry.get_concept(capability_id) is not None:
            selected.append(capability_id)

    statistical_test = request.options.get("statistical_test")
    if isinstance(statistical_test, str):
        for capability_id in _STATISTICAL_TEST_TO_PATTERNS.get(statistical_test, []):
            if registry.get_concept(capability_id) is not None:
                selected.append(capability_id)

    if request.group_by:
        selected.append("segmentation")
    if request.time_reference or request.intent_name in {
        "time_coverage",
        "time_bucket_counts",
        "time_bucket_breakdown",
        "time_period_comparison",
    }:
        selected.append("trend")
    if request.intent_name == "existence_check":
        existence_mode = request.options.get("existence_mode", "filtered_rows")
        selected.extend(_capabilities_for_existence_mode(existence_mode))
    if request.task_type_hint == "forecasting":
        selected.append("forecast_series")

    return list(dict.fromkeys(selected))


def _resolve_analytics_methods(
    request: AnalysisRequest,
    family_spec: object | None,
) -> list[str]:
    methods: list[str] = []
    if family_spec is not None:
        methods.extend(step.action for step in getattr(family_spec, "plan_steps", ()) if getattr(step, "action", None))
        methods.extend(getattr(family_spec, "allowed_plan_actions", ()))
    if not methods and request.intent_name == "row_count":
        methods.append("row_count")
    if not methods and request.intent_name == "distinct_values":
        methods.append("distinct_values")
    if not methods and request.intent_name == "distinct_value_count":
        methods.append("distinct_value_count")
    if not methods and request.intent_name == "tabular_query":
        methods.append("tabular_query")
    if not methods and request.intent_name == "grouped_tabular_query":
        methods.append("grouped_tabular_query")
    if not methods and request.intent_name == "time_period_comparison":
        methods.append("period_comparison")
    if request.task_type_hint == "forecasting":
        methods.append("forecast")
    return list(dict.fromkeys(methods))


def _build_capability_activations(
    request: AnalysisRequest,
    selected_capabilities: list[str],
    registry: object,
) -> list[CapabilityActivation]:
    activations: list[CapabilityActivation] = []
    seen: set[tuple[str, str]] = set()

    llm_candidates = request.options.get("candidate_capabilities", [])
    if isinstance(llm_candidates, list):
        for capability_id in llm_candidates:
            if not isinstance(capability_id, str):
                continue
            node = registry.get_concept(capability_id)
            category = node.category if node is not None else "unknown"
            key = (capability_id, "llm")
            if key in seen:
                continue
            seen.add(key)
            activations.append(
                CapabilityActivation(
                    capability_id=capability_id,
                    category=category,
                    confidence=0.7 if node is not None else 0.3,
                    source="llm",
                    evidence=["provider_candidate_capability"],
                )
            )

    for capability_id in selected_capabilities:
        node = registry.get_concept(capability_id)
        if node is None:
            continue
        evidence = []
        if request.intent_name:
            evidence.append(f"intent={request.intent_name}")
        if request.task_type_hint:
            evidence.append(f"task_type={request.task_type_hint}")
        key = (capability_id, "derived")
        if key in seen:
            continue
        seen.add(key)
        activations.append(
            CapabilityActivation(
                capability_id=capability_id,
                category=node.category,
                confidence=1.0,
                source="derived",
                evidence=evidence,
            )
        )
    return activations


def _build_resolved_parameters(request: AnalysisRequest) -> list[ResolvedParameter]:
    parameters: list[ResolvedParameter] = []

    def add(name: str, value: Any, source: ParameterSource = "rule") -> None:
        if value is None:
            return
        parameters.append(ResolvedParameter(name=name, value=value, source=source, confidence=1.0))

    add("target", request.target)
    add("aggregation", request.aggregation)
    add("group_by", request.group_by)
    add("filters", request.filters)
    add("time_reference", request.time_reference)
    add("horizon", request.horizon)

    for option_name in (
        "statistical_test",
        "ranking_limit",
        "ranking_direction",
        "selected_columns",
        "sort_by",
        "sort_direction",
        "limit",
        "page",
        "page_size",
        "existence_mode",
    ):
        if option_name in request.options:
            add(option_name, request.options.get(option_name), "derived")

    return parameters


def _evaluate_feasibility(
    request: AnalysisRequest,
    profile: DatasetProfile,
    selected_capabilities: list[str],
    registry: object,
) -> tuple[list[DataFeasibilityCheck], list[str], list[ValidationIssue]]:
    checks: list[DataFeasibilityCheck] = []
    missing_parameters: list[str] = []
    issues: list[ValidationIssue] = []
    profile_columns = {column.name for column in profile.columns}
    measure_columns = set(profile.measure_columns)
    dimension_columns = set(profile.dimension_columns)

    existence_mode = request.options.get("existence_mode", "filtered_rows")
    allows_missing_target_lookup = (
        request.intent_name == "existence_check"
        and existence_mode in {"column_property_check", "column_presence_check"}
    )
    if request.target is not None and request.target not in profile_columns and not allows_missing_target_lookup:
        issues.append(
            ValidationIssue(
                code="unknown_target",
                severity="error",
                message=f"Target column '{request.target}' does not exist in the dataset profile.",
                parameter_name="target",
            )
        )
    if request.group_by:
        invalid_groups = [column for column in request.group_by if column not in profile_columns]
        if invalid_groups:
            issues.append(
                ValidationIssue(
                    code="unknown_group_by",
                    severity="error",
                    message=f"Grouping columns do not exist in the dataset profile: {', '.join(invalid_groups)}.",
                    parameter_name="group_by",
                )
            )

    for capability_id in selected_capabilities:
        node = registry.get_concept(capability_id)
        if node is None:
            continue
        for constraint_id in registry.related(capability_id, "requires"):
            parameter_name = _CONSTRAINT_PARAMETER_NAMES.get(constraint_id, constraint_id)
            status, detail, fields = _evaluate_requirement(
                constraint_id,
                request,
                profile,
                measure_columns,
                dimension_columns,
            )
            checks.append(
                DataFeasibilityCheck(
                    requirement=constraint_id,
                    status=status,
                    detail=detail,
                    capability_id=capability_id,
                    field_names=fields,
                )
            )
            if status == "missing":
                missing_parameters.append(parameter_name)
                issues.append(
                    ValidationIssue(
                        code="missing_requirement",
                        severity="warning",
                        message=detail,
                        capability_id=capability_id,
                        parameter_name=parameter_name,
                    )
                )
            elif status == "insufficient":
                issues.append(
                    ValidationIssue(
                        code="insufficient_data_support",
                        severity="warning",
                        message=detail,
                        capability_id=capability_id,
                        parameter_name=parameter_name,
                    )
                )

    return checks, list(dict.fromkeys(missing_parameters)), issues


def _evaluate_requirement(
    constraint_id: str,
    request: AnalysisRequest,
    profile: DatasetProfile,
    measure_columns: set[str],
    dimension_columns: set[str],
) -> tuple[RequirementStatus, str, list[str]]:
    if constraint_id == "requires_metric":
        if request.target and request.target in measure_columns:
            return "satisfied", f"Resolved numeric target '{request.target}' is available.", [request.target]
        if not profile.measure_columns:
            return "insufficient", "No measure columns are available in the dataset profile.", []
        return "missing", "A numeric metric target is required but was not resolved.", []

    if constraint_id == "requires_dimension":
        if request.group_by and all(column in dimension_columns for column in request.group_by):
            return "satisfied", "Grouping dimensions were resolved from the request.", list(request.group_by)
        if request.intent_name == "representation_ranking" and request.target in dimension_columns:
            return "satisfied", "Representation ranking target resolves to a dimension column.", [request.target]
        if not profile.dimension_columns:
            return "insufficient", "No dimension columns are available in the dataset profile.", []
        return "missing", "A grouping dimension is required but was not resolved.", []

    if constraint_id == "requires_time_field":
        if profile.time_columns:
            return "satisfied", f"Time column '{profile.time_columns[0]}' is available.", [profile.time_columns[0]]
        return "insufficient", "A valid time column is required but none was detected.", []

    if constraint_id == "requires_reference_period":
        if request.time_reference:
            return "satisfied", "A time reference was resolved from the request.", []
        return "missing", "A reference period is required but was not resolved.", []

    if constraint_id == "requires_target_column":
        existence_mode = request.options.get("existence_mode", "filtered_rows")
        if (
            request.intent_name == "existence_check"
            and existence_mode in {"column_property_check", "column_presence_check"}
            and request.options.get("requested_column")
        ):
            requested_column = str(request.options["requested_column"])
            return "satisfied", f"Requested column lookup '{requested_column}' was resolved from the prompt.", [requested_column]
        if request.target and request.target in {column.name for column in profile.columns}:
            return "satisfied", f"Target column '{request.target}' is available.", [request.target]
        return "missing", "A target column is required but was not resolved.", []

    if constraint_id == "requires_filter":
        if request.filters:
            return "satisfied", "One or more filters were resolved from the request.", list(request.filters)
        return "missing", "A filter condition is required but was not resolved.", []

    return "unknown", f"No evaluator is registered for requirement '{constraint_id}'.", []


def _derive_ambiguity_flags(request: AnalysisRequest) -> list[str]:
    flags: list[str] = []
    if request.intent_name is None:
        flags.append("no_explicit_intent")
    if request.task_type_hint is None:
        flags.append("no_explicit_task_type")
    if (
        request.target is None
        and request.aggregation is not None
        and request.intent_name not in {"grouped_tabular_query", "row_count", "representation_ranking"}
    ):
        flags.append("aggregation_without_target")
    if request.group_by and request.target is None and request.intent_name not in {
        "grouped_tabular_query",
        "representation_ranking",
    }:
        flags.append("grouping_without_target")
    return flags


def _capabilities_for_existence_mode(existence_mode: object) -> list[str]:
    if existence_mode == "time_value":
        return ["verification", "time_value_existence_check"]
    if existence_mode == "column_presence_check":
        return ["verification"]
    if existence_mode == "null_check":
        return ["verification", "null_verification"]
    if existence_mode == "threshold_check":
        return ["verification", "threshold_verification"]
    if existence_mode == "column_property_check":
        return ["verification", "column_property_verification"]
    return ["verification", "filtered_existence_check"]


class PlanBuilder:
    """Create executable analytical plans from canonical requests."""

    def build_plan_from_contract(
        self,
        prompt_contract: PromptPlanContract,
        request: AnalysisRequest,
        profile: DatasetProfile,
        context: SourceContext | None = None,
    ) -> AnalysisPlan:
        """Compile a plan through the prompt contract layer."""

        if prompt_contract.status == "unsupported_capability":
            raise PlanningError("Prompt contract resolved to an unsupported capability.")
        if prompt_contract.status in {"supported_but_data_infeasible", "supported_but_data_insufficient"}:
            raise PlanningError("Prompt contract failed data feasibility checks.")
        if request.prompt_family is None:
            request.prompt_family = prompt_contract.prompt_family or derive_prompt_family(request)
        plan = self.build_plan(request, profile, context)
        prompt_family = request.prompt_family or prompt_contract.prompt_family
        if prompt_family:
            self._validate_family_plan(prompt_family, plan)
        return plan

    def build_plan(
        self,
        request: AnalysisRequest,
        profile: DatasetProfile,
        context: SourceContext | None = None,
    ) -> AnalysisPlan:
        """Build an executable plan from the request and profile."""
        self._validate_request(request, profile)
        if request.prompt_family is None:
            request.prompt_family = derive_prompt_family(request)
        task_type = request.task_type_hint or "descriptive"
        warnings: list[str] = []
        family_plan = self._build_plan_for_prompt_family(request, profile, context, task_type, warnings)
        if family_plan is not None:
            return family_plan

        if task_type in {"descriptive", "diagnostic", "statistical"}:
            raise PlanningError("The request did not resolve to a safe supported prompt family.")

        if task_type == "forecasting":
            if not profile.time_columns:
                raise PlanningError("Forecasting requires a datetime column.")
            if request.target is None:
                raise PlanningError("Forecasting requires a target metric.")
            steps = [
                PlanStep(
                    step_id="forecast",
                    tool_family="ml",
                    action="forecast",
                    parameters={"target": request.target, "time_column": profile.time_columns[0], "horizon": request.horizon or 3},
                    description="Generate a forecast for the requested target.",
                )
            ]
            rationale = self._build_rationale(task_type, request, context)
            return AnalysisPlan(task_type=task_type, rationale=rationale, steps=steps, warnings=warnings)

        if task_type == "predictive":
            warnings.append("Predictive model training is not implemented yet.")

        rationale = self._build_rationale(task_type, request, context)
        return AnalysisPlan(task_type=task_type, rationale=rationale, steps=[], warnings=warnings)

    def _build_plan_for_prompt_family(
        self,
        request: AnalysisRequest,
        profile: DatasetProfile,
        context: SourceContext | None,
        task_type: str,
        warnings: list[str],
    ) -> AnalysisPlan | None:
        prompt_family = request.prompt_family
        if not prompt_family:
            return None
        family_spec = get_prompt_family_catalog().get(prompt_family)
        if family_spec is not None and family_spec.plan_steps:
            steps = family_spec.compile_steps(request, profile)
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family == "metric_aggregate":
            steps = self._build_metric_overview_steps(request, profile, task_type, include_aggregate_step=True)
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family == "exploratory_metric_overview":
            steps = self._build_metric_overview_steps(request, profile, task_type, include_aggregate_step=False)
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family in _STATISTICAL_PROMPT_FAMILIES:
            steps = [
                PlanStep(
                    step_id=prompt_family,
                    tool_family="stats",
                    action=prompt_family,
                    parameters={
                        "target": request.target,
                        "group_by": request.group_by,
                        "filters": request.filters,
                        "alpha": request.options.get("alpha", 0.05),
                        "confidence_level": request.options.get("confidence_level", 0.95),
                        "desired_power": request.options.get("desired_power", 0.80),
                        "feature_columns": request.options.get("feature_columns", []),
                        "comparison_columns": request.options.get("comparison_columns", []),
                    },
                    description=f"Run the deterministic {prompt_family} workflow selected from the prompt family.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family in _METADATA_PROMPT_FAMILY_TO_ACTION:
            action = _METADATA_PROMPT_FAMILY_TO_ACTION[prompt_family]
            steps = [
                PlanStep(
                    step_id=action,
                    tool_family="metadata",
                    action=action,
                    parameters={"target": request.target},
                    description="Return dataset inventory information for the requested metadata family.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family == "time_coverage":
            steps = [
                PlanStep(
                    step_id="time_coverage",
                    tool_family="duckdb",
                    action="time_coverage",
                    parameters={
                        "time_column": profile.time_columns[0],
                        "filters": request.filters,
                        "mode": request.options.get("time_coverage_mode", "years_present"),
                    },
                    description="Inspect time coverage in the dataset without treating the datetime column as a metric.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family == "time_bucket_counts":
            steps = [
                PlanStep(
                    step_id="time_bucket_counts",
                    tool_family="duckdb",
                    action="time_bucket_counts",
                    parameters={
                        "time_column": profile.time_columns[0],
                        "filters": request.filters,
                        "bucket": request.options.get("time_bucket", "year"),
                    },
                    description="Count rows across derived time buckets such as years or months.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family == "time_bucket_breakdown":
            steps = [
                PlanStep(
                    step_id="time_bucket_breakdown",
                    tool_family="duckdb",
                    action="time_bucket_breakdown",
                    parameters={
                        "target": request.target,
                        "time_column": profile.time_columns[0],
                        "bucket": request.options.get("time_bucket", "month"),
                        "aggregation": request.aggregation or "sum",
                        "group_by": request.group_by,
                        "filters": request.filters,
                    },
                    description="Aggregate a numeric target across derived time buckets such as month, quarter, or year.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family == "time_period_comparison":
            comparison_action = "grouped_period_comparison" if request.group_by else "period_comparison"
            steps = [
                PlanStep(
                    step_id=comparison_action,
                    tool_family="duckdb",
                    action=comparison_action,
                    parameters={
                        "target": request.target,
                        "group_by": request.group_by,
                        "time_column": profile.time_columns[0],
                        "time_reference": request.time_reference,
                        "bucket": request.options.get("time_bucket", "month"),
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                    },
                    description="Compare adjacent derived time periods such as month, quarter, or year.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family in {
            "column_presence_check",
            "column_property_check",
            "null_verification",
            "threshold_verification",
            "time_value_verification",
            "row_existence_check",
        }:
            return self._build_existence_family_plan(request, profile, context, task_type, warnings, prompt_family)

        if prompt_family == "grouped_metric_table":
            steps = [
                PlanStep(
                    step_id="grouped_tabular_query",
                    tool_family="duckdb",
                    action="grouped_tabular_query",
                    parameters={
                        "target": request.target,
                        "group_by": request.group_by,
                        "aggregation": request.aggregation or ("count" if request.target is None else "sum"),
                        "filters": request.filters,
                        "sort_by": request.options.get("sort_by"),
                        "sort_direction": request.options.get("sort_direction", "desc"),
                        "limit": request.options.get("limit"),
                        "page": request.options.get("page", 1),
                        "page_size": request.options.get("page_size", 50),
                    },
                    description="Return a grouped, tabular dataset slice for discovery-style analysis.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family == "row_ranking" and request.target:
            steps = [
                PlanStep(
                    step_id="ranked_rows",
                    tool_family="duckdb",
                    action="ranked_rows",
                    parameters={
                        "target": request.target,
                        "filters": request.filters,
                        "ascending": request.options.get("ranking_direction") == "asc",
                        "limit": int(request.options.get("ranking_limit", 5)),
                    },
                    description="Rank individual rows by the requested numeric target.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        if prompt_family == "group_ranking" and request.target and request.group_by:
            steps = [
                PlanStep(
                    step_id="ranked_breakdown",
                    tool_family="duckdb",
                    action="ranked_breakdown",
                    parameters={
                        "target": request.target,
                        "group_by": request.group_by,
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                        "limit": int(request.options.get("ranking_limit", 5)),
                        "ascending": request.options.get("ranking_direction") == "asc",
                    },
                    description="Rank grouped results according to the requested top or bottom limit.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        return None

    def _build_metric_overview_steps(
        self,
        request: AnalysisRequest,
        profile: DatasetProfile,
        task_type: str,
        *,
        include_aggregate_step: bool,
    ) -> list[PlanStep]:
        if request.target is None or request.target not in set(profile.measure_columns):
            raise PlanningError("Exploratory metric workflows require a numeric target.")

        steps: list[PlanStep] = []
        if include_aggregate_step and request.aggregation:
            steps.append(
                PlanStep(
                    step_id="aggregate_value",
                    tool_family="duckdb",
                    action="aggregate_value",
                    parameters={
                        "target": request.target,
                        "aggregation": request.aggregation,
                        "filters": request.filters,
                    },
                    description=f"Compute the {request.aggregation} value for the requested target.",
                )
            )

        steps.append(
            PlanStep(
                step_id="summary_metrics",
                tool_family="duckdb",
                action="dataset_summary",
                parameters={"target": request.target, "filters": request.filters},
                description="Compute top-level dataset metrics.",
            )
        )
        if profile.time_columns:
            steps.append(
                PlanStep(
                    step_id="time_trend",
                    tool_family="duckdb",
                    action="time_trend",
                    parameters={
                        "target": request.target,
                        "time_column": profile.time_columns[0],
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                    },
                    description="Compute the target trend over time.",
                )
            )
        if request.time_reference and profile.time_columns:
            steps.append(
                PlanStep(
                    step_id="period_comparison",
                    tool_family="duckdb",
                    action="period_comparison",
                    parameters={
                        "target": request.target,
                        "time_column": profile.time_columns[0],
                        "time_reference": request.time_reference,
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                    },
                    description="Compare the requested period against the previous comparable period.",
                )
            )
            if request.group_by:
                steps.append(
                    PlanStep(
                        step_id="grouped_period_comparison",
                        tool_family="duckdb",
                        action="grouped_period_comparison",
                        parameters={
                            "target": request.target,
                            "group_by": request.group_by,
                            "time_column": profile.time_columns[0],
                            "time_reference": request.time_reference,
                            "aggregation": request.aggregation or "sum",
                            "filters": request.filters,
                        },
                        description="Compare grouped totals between adjacent periods.",
                    )
                )
        if request.group_by:
            steps.append(
                PlanStep(
                    step_id="group_breakdown",
                    tool_family="duckdb",
                    action="group_breakdown",
                    parameters={
                        "target": request.target,
                        "group_by": request.group_by,
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                    },
                    description="Break down the target metric by requested dimensions.",
                )
            )
            steps.append(
                PlanStep(
                    step_id="ranked_breakdown",
                    tool_family="duckdb",
                    action="ranked_breakdown",
                    parameters={
                        "target": request.target,
                        "group_by": request.group_by,
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                        "limit": 5,
                    },
                    description="Rank the largest grouped contributors.",
                )
            )
            if request.time_reference and profile.time_columns:
                steps.append(
                    PlanStep(
                        step_id="top_movers",
                        tool_family="duckdb",
                        action="top_movers",
                        parameters={
                            "target": request.target,
                            "group_by": request.group_by,
                            "time_column": profile.time_columns[0],
                            "time_reference": request.time_reference,
                            "aggregation": request.aggregation or "sum",
                            "filters": request.filters,
                            "limit": 5,
                        },
                        description="Identify the largest grouped movers between adjacent periods.",
                    )
                )
        elif task_type == "diagnostic" and profile.dimension_columns:
            steps.append(
                PlanStep(
                    step_id="top_dimension_breakdown",
                    tool_family="duckdb",
                    action="group_breakdown",
                    parameters={
                        "target": request.target,
                        "group_by": [profile.dimension_columns[0]],
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                    },
                    description="Break down the target metric by the leading dimension candidate.",
                )
            )
            steps.append(
                PlanStep(
                    step_id="top_dimension_ranking",
                    tool_family="duckdb",
                    action="ranked_breakdown",
                    parameters={
                        "target": request.target,
                        "group_by": [profile.dimension_columns[0]],
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                        "limit": 5,
                    },
                    description="Rank the leading grouped contributors for the diagnostic workflow.",
                )
            )
            if request.time_reference and profile.time_columns:
                steps.append(
                    PlanStep(
                        step_id="top_dimension_movers",
                        tool_family="duckdb",
                        action="top_movers",
                        parameters={
                            "target": request.target,
                            "group_by": [profile.dimension_columns[0]],
                            "time_column": profile.time_columns[0],
                            "time_reference": request.time_reference,
                            "aggregation": request.aggregation or "sum",
                            "filters": request.filters,
                            "limit": 5,
                        },
                        description="Identify the largest movers for the leading dimension candidate.",
                    )
                )
        if task_type == "diagnostic" and profile.dimension_columns:
            steps.append(
                PlanStep(
                    step_id="contribution_breakdown",
                    tool_family="duckdb",
                    action="contribution_breakdown",
                    parameters={
                        "target": request.target,
                        "group_by": request.group_by or [profile.dimension_columns[0]],
                        "time_column": profile.time_columns[0] if profile.time_columns else None,
                        "time_reference": request.time_reference,
                        "aggregation": request.aggregation or "sum",
                        "filters": request.filters,
                    },
                    description="Estimate group-level contribution changes for the diagnostic workflow.",
                )
            )
        steps.append(
            PlanStep(
                step_id="missingness_summary",
                tool_family="stats",
                action="missingness_summary",
                parameters={},
                description="Summarize missing values by column.",
            )
        )
        steps.append(
            PlanStep(
                step_id="numeric_summary",
                tool_family="stats",
                action="numeric_summary",
                parameters={},
                description="Summarize numeric columns with deterministic statistics.",
            )
        )
        steps.append(
            PlanStep(
                step_id="distribution_summary",
                tool_family="stats",
                action="distribution_summary",
                parameters={"target": request.target},
                description="Summarize the target distribution.",
            )
        )
        steps.append(
            PlanStep(
                step_id="target_correlation",
                tool_family="stats",
                action="target_correlation",
                parameters={"target": request.target},
                description="Measure correlations between the target and other numeric columns.",
            )
        )
        steps.append(
            PlanStep(
                step_id="anomaly_summary",
                tool_family="stats",
                action="anomaly_summary",
                parameters={
                    "target": request.target,
                    "time_column": profile.time_columns[0] if profile.time_columns else None,
                },
                description="Flag simple anomaly candidates for the target.",
            )
        )
        if profile.time_columns:
            steps.append(
                PlanStep(
                    step_id="time_series_diagnostics",
                    tool_family="stats",
                    action="time_series_diagnostics",
                    parameters={"target": request.target, "time_column": profile.time_columns[0]},
                    description="Compute simple time-series diagnostics for the target.",
                )
            )
        candidate_dimensions = request.group_by or profile.dimension_columns
        comparison_dimension = [column for column in candidate_dimensions if column != request.target][:1]
        if comparison_dimension:
            steps.append(
                PlanStep(
                    step_id="group_mean_comparison",
                    tool_family="stats",
                    action="group_mean_comparison",
                    parameters={"target": request.target, "group_column": comparison_dimension[0]},
                    description="Compare the target mean across the first available grouping dimension.",
                )
            )
        return steps

    def _build_existence_family_plan(
        self,
        request: AnalysisRequest,
        profile: DatasetProfile,
        context: SourceContext | None,
        task_type: str,
        warnings: list[str],
        prompt_family: str,
    ) -> AnalysisPlan:
        if prompt_family == "time_value_verification":
            steps = [
                PlanStep(
                    step_id="time_value_exists",
                    tool_family="duckdb",
                    action="time_value_exists",
                    parameters={
                        "time_column": request.target or profile.time_columns[0],
                        "filters": request.filters,
                        "expected_year": request.options.get("expected_year"),
                        "time_reference": request.time_reference,
                    },
                    description="Verify whether the requested time value exists in the dataset.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)
        if prompt_family == "null_verification":
            steps = [
                PlanStep(
                    step_id="null_check",
                    tool_family="duckdb",
                    action="null_check",
                    parameters={
                        "target": request.target,
                        "filters": request.filters,
                        "null_expectation": request.options.get("null_expectation", "has_nulls"),
                    },
                    description="Verify whether the requested column has missing values or is complete.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)
        if prompt_family == "threshold_verification":
            steps = [
                PlanStep(
                    step_id="threshold_check",
                    tool_family="duckdb",
                    action="threshold_check",
                    parameters={
                        "target": request.target,
                        "filters": request.filters,
                        "threshold_operator": request.options.get("threshold_operator"),
                        "threshold_value": request.options.get("threshold_value"),
                        "lower_bound": request.options.get("lower_bound"),
                        "upper_bound": request.options.get("upper_bound"),
                    },
                    description="Verify whether the requested numeric threshold condition is present in the data.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)
        if prompt_family == "column_property_check":
            steps = [
                PlanStep(
                    step_id="column_property_check",
                    tool_family="metadata",
                    action="column_property_check",
                    parameters={
                        "target": request.target,
                        "expected_property": request.options.get("expected_property"),
                    },
                    description="Verify whether the requested column has the expected schema property.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)
        if prompt_family == "column_presence_check":
            steps = [
                PlanStep(
                    step_id="column_presence_check",
                    tool_family="metadata",
                    action="column_presence_check",
                    parameters={
                        "requested_column": request.options.get("requested_column"),
                    },
                    description="Verify whether the requested column exists in the dataset schema.",
                )
            ]
            return self._finalize_plan(task_type, request, context, steps, warnings)

        steps = [
            PlanStep(
                step_id="row_existence",
                tool_family="duckdb",
                action="row_existence",
                parameters={"filters": request.filters or {}},
                description="Verify whether any rows match the requested filters.",
            )
        ]
        return self._finalize_plan(task_type, request, context, steps, warnings)

    def _finalize_plan(
        self,
        task_type: str,
        request: AnalysisRequest,
        context: SourceContext | None,
        steps: list[PlanStep],
        warnings: list[str],
    ) -> AnalysisPlan:
        normalized_steps = [self._normalize_step_parameters(step) for step in steps]
        rationale = self._build_rationale(task_type, request, context)
        plan = AnalysisPlan(task_type=task_type, rationale=rationale, steps=normalized_steps, warnings=list(warnings))
        if request.prompt_family:
            self._validate_family_plan(request.prompt_family, plan)
        return plan

    def _normalize_step_parameters(self, step: PlanStep) -> PlanStep:
        method_id = step.method_id or step.action
        method_spec = get_analytics_registry().get_method(method_id)
        if method_spec is None:
            return step
        supported_parameters = {
            value
            for value in (*method_spec.required_inputs, *method_spec.allowed_configs)
            if value != "dataset"
        }
        step.parameters = {
            name: value
            for name, value in step.parameters.items()
            if name in supported_parameters and value is not None
        }
        return step

    def _validate_family_plan(self, prompt_family: str, plan: AnalysisPlan) -> None:
        family_spec = get_prompt_family_catalog().get(prompt_family)
        if family_spec is None:
            return
        issues = family_spec.plan_invariant_issues(plan)
        if not issues:
            return
        if family_spec.governance == "governed":
            raise PlanningError(f"Prompt family {prompt_family!r} produced an invalid plan: {' '.join(issues)}")
        plan.warnings.extend(issues)

    def validate(self, plan: AnalysisPlan) -> None:
        """Validate a plan before execution."""
        if not plan.steps:
            raise PlanningError("Analysis plan contains no executable steps.")

    def _validate_request(self, request: AnalysisRequest, profile: DatasetProfile) -> None:
        supported_tasks = {"descriptive", "diagnostic", "statistical", "predictive", "forecasting"}
        supported_aggregations = {"sum", "mean", "max", "min", "count"}
        task_type = request.task_type_hint or "descriptive"
        prompt_family = request.prompt_family or derive_prompt_family(request)
        effective_intent_name = request.intent_name or _PROMPT_FAMILY_TO_INTENT.get(prompt_family)
        effective_existence_mode = request.options.get("existence_mode") or _PROMPT_FAMILY_TO_EXISTENCE_MODE.get(prompt_family, "filtered_rows")
        effective_statistical_test = request.options.get("statistical_test")
        if effective_statistical_test is None and prompt_family in _STATISTICAL_PROMPT_FAMILIES:
            effective_statistical_test = prompt_family
        if task_type not in supported_tasks:
            raise PlanningError(f"Unsupported analysis task type: {task_type}")

        profile_columns = {column.name for column in profile.columns}
        if not profile_columns:
            raise PlanningError("Dataset profile contains no columns.")

        existence_mode = effective_existence_mode
        allows_missing_target_lookup = (
            effective_intent_name == "existence_check"
            and existence_mode in {"column_property_check", "column_presence_check"}
        )
        if request.target is not None and request.target not in profile_columns and not allows_missing_target_lookup:
            raise PlanningError(f"Target column '{request.target}' does not exist in the dataset profile.")
        if request.options.get("distinct_values") and request.target not in set(profile.dimension_columns):
            raise PlanningError("Distinct value listing requires a dimension target.")
        if effective_intent_name == "distinct_value_count" and request.target not in set(profile.dimension_columns):
            raise PlanningError("Distinct value count requires a dimension target.")
        if effective_intent_name == "representation_ranking" and request.target not in set(profile.dimension_columns):
            raise PlanningError("Representation ranking requires a dimension target.")
        if effective_intent_name == "row_ranking" and request.target not in set(profile.measure_columns):
            raise PlanningError("Row ranking requires a numeric target.")
        if effective_intent_name == "group_ranking":
            if request.target not in set(profile.measure_columns) or not request.group_by:
                raise PlanningError("Group ranking requires a numeric target and one grouping column.")
        if effective_intent_name == "tabular_query":
            selected_columns = request.options.get("selected_columns", [])
            invalid_selected = [column for column in selected_columns if column not in profile_columns]
            if invalid_selected:
                joined = ", ".join(invalid_selected)
                raise PlanningError(f"Selected columns do not exist in the dataset profile: {joined}")
            sort_by = request.options.get("sort_by")
            if sort_by is not None and sort_by not in profile_columns:
                raise PlanningError(f"Sort column '{sort_by}' does not exist in the dataset profile.")
        if effective_intent_name == "grouped_tabular_query":
            if not request.group_by:
                raise PlanningError("Grouped tabular querying requires at least one grouping column.")
            if request.target is not None and request.target not in set(profile.measure_columns):
                raise PlanningError("Grouped tabular querying requires a numeric target when a target is provided.")
            grouped_sort_by = request.options.get("sort_by")
            if grouped_sort_by is not None and grouped_sort_by not in {
                *(request.group_by or []),
                request.target,
                "row_count",
                "target_total",
            }:
                raise PlanningError("Grouped tabular query sort column must be a grouping column or aggregate output.")
        if request.aggregation and request.aggregation != "count" and effective_intent_name not in {
            "time_bucket_breakdown",
            "time_period_comparison",
            "group_ranking",
            "grouped_tabular_query",
        }:
            if request.target not in set(profile.measure_columns):
                raise PlanningError(f"Aggregation '{request.aggregation}' requires a numeric target.")
        if (
            request.group_by
            and effective_intent_name not in {"representation_ranking", "group_ranking", "time_bucket_breakdown", "time_period_comparison", "grouped_tabular_query"}
            and effective_statistical_test != "chi_square"
            and request.target is not None
            and request.target not in set(profile.measure_columns)
        ):
            raise PlanningError("Grouped descriptive analysis requires a numeric target or a dedicated dimension intent.")
        if effective_intent_name == "time_coverage" and not profile.time_columns:
            raise PlanningError("Time coverage analysis requires a datetime column.")
        if effective_intent_name == "time_bucket_counts" and not profile.time_columns:
            raise PlanningError("Time bucket count analysis requires a datetime column.")
        if effective_intent_name == "time_bucket_breakdown" and not profile.time_columns:
            raise PlanningError("Time bucket breakdown analysis requires a datetime column.")
        if effective_intent_name == "time_period_comparison" and not profile.time_columns:
            raise PlanningError("Time period comparison requires a datetime column.")
        if effective_intent_name == "time_column_inventory" and not profile.time_columns:
            raise PlanningError("Time column inventory requires at least one datetime column.")
        if effective_intent_name == "time_bucket_breakdown" and request.target not in set(profile.measure_columns):
            raise PlanningError("Time bucket breakdown requires a numeric target.")
        if effective_intent_name == "time_period_comparison":
            if request.target not in set(profile.measure_columns):
                raise PlanningError("Time period comparison requires a numeric target.")
            if not request.time_reference:
                raise PlanningError("Time period comparison requires an explicit time reference.")
        if effective_intent_name == "existence_check":
            if existence_mode == "time_value":
                if not profile.time_columns:
                    raise PlanningError("Time existence verification requires a datetime column.")
                if request.target is not None and request.target not in set(profile.time_columns):
                    raise PlanningError("Time existence verification requires a datetime target column.")
                if request.options.get("expected_year") is None and not request.time_reference:
                    raise PlanningError("Time existence verification requires a concrete year or time reference.")
            elif existence_mode == "null_check":
                if request.target is None:
                    raise PlanningError("Null verification requires a target column.")
                if request.options.get("null_expectation") not in {"has_nulls", "no_nulls"}:
                    raise PlanningError("Null verification requires a supported missing-value expectation.")
            elif existence_mode == "threshold_check":
                if request.target is None or request.target not in set(profile.measure_columns):
                    raise PlanningError("Threshold verification requires a numeric target.")
                operator = request.options.get("threshold_operator")
                if operator == "between":
                    if request.options.get("lower_bound") is None or request.options.get("upper_bound") is None:
                        raise PlanningError("Between-threshold verification requires lower and upper bounds.")
                elif operator not in {"gt", "gte", "lt", "lte"} or request.options.get("threshold_value") is None:
                    raise PlanningError("Threshold verification requires a supported comparator and threshold value.")
            elif existence_mode == "column_property_check":
                if request.target is None:
                    raise PlanningError("Column property verification requires a target column.")
                if request.options.get("expected_property") not in {
                    "datetime",
                    "numeric",
                    "categorical",
                    "identifier",
                    "dimension",
                    "measure",
                    "high_cardinality",
                }:
                    raise PlanningError("Column property verification requires a supported expected property.")
            elif existence_mode == "column_presence_check":
                if not request.options.get("requested_column"):
                    raise PlanningError("Column presence verification requires a requested column name.")
            elif not request.filters:
                raise PlanningError("Existence verification requires filters or a time-value check.")
        if effective_intent_name in {"tabular_query", "grouped_tabular_query"}:
            page = int(request.options.get("page", 1))
            page_size = int(request.options.get("page_size", 50))
            if page <= 0:
                raise PlanningError("Tabular pagination requires page to be 1 or greater.")
            if page_size <= 0:
                raise PlanningError("Tabular pagination requires page_size to be 1 or greater.")
        if effective_statistical_test == "chi_square":
            comparison_columns = request.options.get("comparison_columns", [])
            if len(comparison_columns) < 2:
                raise PlanningError("Chi-square testing requires two categorical columns.")
        if effective_statistical_test in {"t_test", "anova", "mann_whitney", "significance_inference", "power_analysis", "sample_size_estimate"}:
            if request.target is None or not request.group_by:
                raise PlanningError("Group-based statistical testing requires a numeric target and one grouping column.")
        if effective_statistical_test == "confidence_interval" and request.target is None:
            raise PlanningError("Confidence interval analysis requires a numeric target.")
        if effective_statistical_test == "regression_significance":
            feature_columns = request.options.get("feature_columns", [])
            if request.target is None or not feature_columns:
                raise PlanningError("Regression significance testing requires a target and at least one feature column.")

        if request.group_by:
            invalid_groups = [column for column in request.group_by if column not in profile_columns]
            if invalid_groups:
                joined = ", ".join(invalid_groups)
                raise PlanningError(f"Grouping columns do not exist in the dataset profile: {joined}")

        if request.filters:
            invalid_filters = [column for column in request.filters if column not in profile_columns]
            if invalid_filters:
                joined = ", ".join(invalid_filters)
                raise PlanningError(f"Filter columns do not exist in the dataset profile: {joined}")

        if request.time_reference and not profile.time_columns:
            raise PlanningError("Time-based analysis requires a datetime column.")

        supported_time_reference_types = {"month_name", "quarter", "relative_period"}
        if request.time_reference and request.time_reference.get("type") not in supported_time_reference_types:
            raise PlanningError("Unsupported time reference in analysis request.")

        if request.time_reference:
            reference_type = request.time_reference.get("type")
            if reference_type == "relative_period" and effective_intent_name != "time_period_comparison":
                raise PlanningError("Relative time references are only supported for period-comparison analysis right now.")

        if request.aggregation and request.aggregation not in supported_aggregations:
            raise PlanningError(f"Unsupported aggregation: {request.aggregation}")

        if task_type in {"diagnostic", "statistical", "predictive"} and request.target is None:
            raise PlanningError(f"{task_type.title()} analysis requires a target metric.")
        if task_type == "forecasting" and request.target is None:
            raise PlanningError("Forecasting requires a target metric.")

    def _build_rationale(self, task_type: str, request: AnalysisRequest, context: SourceContext | None) -> str:
        rationale = f"Selected a {task_type} workflow based on the normalized request."
        if request.prompt_family:
            rationale += f" Prompt family: {request.prompt_family}."
        if request.target:
            rationale += f" Target metric: {request.target}."
        if request.aggregation:
            rationale += f" Aggregation: {request.aggregation}."
        if context and context.metric_definitions:
            rationale += " Semantic metric definitions were available."
        if request.filters:
            rationale += f" Filters were detected for: {', '.join(request.filters)}."
        if request.options.get("distinct_values"):
            rationale += " A distinct value listing was requested."
        if request.intent_name == "row_ranking":
            rationale += " Ranked row retrieval was requested."
        if request.intent_name == "group_ranking":
            rationale += " Group ranking was requested."
        if request.intent_name == "tabular_query":
            rationale += " Tabular record retrieval was requested."
        if request.intent_name == "grouped_tabular_query":
            rationale += " Grouped tabular querying was requested."
        if request.intent_name:
            rationale += f" Intent: {request.intent_name}."
        if request.intent_name == "time_coverage":
            rationale += f" Time coverage mode: {request.options.get('time_coverage_mode', 'years_present')}."
        if request.intent_name == "time_bucket_counts":
            rationale += f" Time bucket counts: {request.options.get('time_bucket', 'year')}."
        if request.intent_name == "time_bucket_breakdown":
            rationale += f" Time bucket breakdown: {request.options.get('time_bucket', 'month')}."
        if request.intent_name == "time_period_comparison":
            rationale += f" Time period comparison bucket: {request.options.get('time_bucket', 'month')}."
        if request.intent_name == "existence_check":
            rationale += f" Existence mode: {request.options.get('existence_mode', 'filtered_rows')}."
        if request.intent_name in {"tabular_query", "grouped_tabular_query"}:
            if request.options.get("selected_columns"):
                rationale += f" Selected columns: {', '.join(request.options['selected_columns'])}."
            if request.options.get("sort_by"):
                rationale += f" Sort: {request.options['sort_by']} {request.options.get('sort_direction', 'asc')}."
            rationale += (
                f" Pagination: page {request.options.get('page', 1)} "
                f"with page size {request.options.get('page_size', 50)}."
            )
        if request.options.get("statistical_test"):
            rationale += f" Statistical test: {request.options['statistical_test']}."
        return rationale


AnalysisPlanner = PlanBuilder
