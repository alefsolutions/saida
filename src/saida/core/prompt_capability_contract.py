"""Typed prompt capability contract scaffolding."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from saida.core.capability_registry import CapabilityRegistry, build_default_capability_registry
from saida.core.contracts import AnalysisRequest, DatasetProfile
from saida.core.prompt_family_catalog import (
    PromptFamilyCatalog,
    derive_prompt_family,
    get_prompt_family_catalog,
)

ContractStatus = Literal[
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
    """A candidate or selected capability node activated by the prompt."""

    capability_id: str
    category: str
    confidence: float | None = None
    source: str = "derived"
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ResolvedParameter:
    """Resolved parameter captured before plan compilation."""

    name: str
    value: Any
    source: ParameterSource
    confidence: float | None = None
    resolved_from: str | None = None


@dataclass(slots=True)
class ValidationIssue:
    """Structured validation issue against the capability contract."""

    code: str
    severity: IssueSeverity
    message: str
    capability_id: str | None = None
    parameter_name: str | None = None


@dataclass(slots=True)
class DataFeasibilityCheck:
    """Outcome of a capability or data support check."""

    requirement: str
    status: RequirementStatus
    detail: str
    capability_id: str | None = None
    field_names: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PromptCapabilityContract:
    """Typed handoff between prompt interpretation and deterministic planning."""

    question: str
    dataset_name: str
    status: ContractStatus
    prompt_family: str | None = None
    task_type_hint: str | None = None
    intent_name: str | None = None
    family_spec: dict[str, Any] | None = None
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

    def refresh_status(self) -> ContractStatus:
        self.status = derive_contract_status(self)
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


def build_prompt_capability_contract(
    request: AnalysisRequest,
    profile: DatasetProfile,
    registry: CapabilityRegistry | None = None,
    family_catalog: PromptFamilyCatalog | None = None,
) -> PromptCapabilityContract:
    """Bootstrap a prompt capability contract from the current normalized request."""

    active_registry = registry or build_default_capability_registry()
    active_family_catalog = family_catalog or get_prompt_family_catalog()
    prompt_family = request.prompt_family or derive_prompt_family(request, active_family_catalog)
    family_spec = active_family_catalog.get(prompt_family)
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
        "This contract is currently a bootstrap layer derived from the normalized AnalysisRequest.",
        "The live planner is not yet compiling directly from the capability registry.",
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
        warnings.append("The normalized request was stopped before planning because no safe supported prompt family or metric target could be resolved.")
    elif request.options.get("target_resolution_source") == "first_measure_fallback":
        warnings.append("The normalized request used the first measure fallback inside exploratory metric overview.")

    contract = PromptCapabilityContract(
        question=request.question,
        dataset_name=profile.dataset_name,
        status="supported_and_data_feasible",
        prompt_family=prompt_family,
        task_type_hint=request.task_type_hint,
        intent_name=request.intent_name,
        family_spec=family_spec.to_dict() if family_spec is not None else None,
        candidate_capabilities=candidate_capabilities,
        selected_capabilities=selected_capabilities,
        resolved_parameters=resolved_parameters,
        missing_parameters=missing_parameters,
        unsupported_capabilities=[capability_id for capability_id in selected_capabilities if active_registry.get_node(capability_id) is None],
        ambiguity_flags=_derive_ambiguity_flags(request),
        validation_issues=issues,
        data_feasibility=data_feasibility,
        warnings=warnings,
        notes=notes,
    )
    contract.refresh_status()
    return contract


def derive_contract_status(contract: PromptCapabilityContract) -> ContractStatus:
    """Derive the high-level status for the current contract."""

    if contract.unsupported_capabilities:
        return "unsupported_capability"
    if any(check.status == "insufficient" for check in contract.data_feasibility):
        return "supported_but_data_insufficient"
    if contract.missing_parameters or contract.ambiguity_flags:
        return "supported_with_partial_fallback"
    if contract.has_blocking_issues():
        return "supported_but_data_infeasible"
    return "supported_and_data_feasible"


def _select_capabilities(
    request: AnalysisRequest,
    registry: CapabilityRegistry,
) -> list[str]:
    selected: list[str] = []

    for capability_id in _TASK_TYPE_TO_DOMAINS.get(request.task_type_hint or "", []):
        if registry.get_node(capability_id) is not None:
            selected.append(capability_id)

    for capability_id in _INTENT_TO_PATTERNS.get(request.intent_name or "", []):
        if registry.get_node(capability_id) is not None:
            selected.append(capability_id)

    statistical_test = request.options.get("statistical_test")
    if isinstance(statistical_test, str):
        for capability_id in _STATISTICAL_TEST_TO_PATTERNS.get(statistical_test, []):
            if registry.get_node(capability_id) is not None:
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


def _build_capability_activations(
    request: AnalysisRequest,
    selected_capabilities: list[str],
    registry: CapabilityRegistry,
) -> list[CapabilityActivation]:
    activations: list[CapabilityActivation] = []
    seen: set[tuple[str, str]] = set()

    llm_candidates = request.options.get("candidate_capabilities", [])
    if isinstance(llm_candidates, list):
        for capability_id in llm_candidates:
            if not isinstance(capability_id, str):
                continue
            node = registry.get_node(capability_id)
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
        node = registry.get_node(capability_id)
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
    registry: CapabilityRegistry,
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
        node = registry.get_node(capability_id)
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
