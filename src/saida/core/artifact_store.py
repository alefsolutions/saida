"""Execution-scoped artifact storage for DAG-oriented SAIDA workflows."""

from __future__ import annotations

from dataclasses import dataclass, field

from saida.core.artifacts import RuntimeArtifact, artifact_from_value
from saida.core.contracts import Dataset, PlanInput
from saida.exceptions import PlanningError


@dataclass(slots=True)
class ArtifactStore:
    """In-memory execution artifact registry for one plan execution."""

    artifacts: dict[str, RuntimeArtifact] = field(default_factory=dict)

    def register(self, artifact: RuntimeArtifact) -> RuntimeArtifact:
        """Register one artifact and enforce unique artifact ids."""
        if artifact.artifact_id in self.artifacts:
            raise PlanningError(f"Artifact store already contains artifact id {artifact.artifact_id!r}.")
        self.artifacts[artifact.artifact_id] = artifact
        return artifact

    def register_value(
        self,
        artifact_id: str,
        value: object,
        *,
        role: str = "intermediate",
        producer_step_id: str | None = None,
        logical_shape: str | None = None,
        physical_shape: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> RuntimeArtifact:
        """Build and register an artifact from a concrete runtime value."""
        artifact = artifact_from_value(
            artifact_id,
            value,
            role=role,
            producer_step_id=producer_step_id,
            logical_shape=logical_shape,
            physical_shape=physical_shape,
            metadata=metadata,
        )
        return self.register(artifact)

    def register_plan_inputs(self, dataset: Dataset, plan_inputs: list[PlanInput]) -> list[RuntimeArtifact]:
        """Register plan-level inputs as runtime artifacts."""
        registered: list[RuntimeArtifact] = []
        if not plan_inputs:
            registered.append(
                self.register_value(
                    "primary_dataset",
                    dataset.data,
                    role="input",
                    metadata={"dataset_name": dataset.name, "source_type": dataset.source_type},
                )
            )
            return registered

        for plan_input in plan_inputs:
            if plan_input.kind != "dataset":
                raise PlanningError(f"Unsupported plan input kind for artifact registration: {plan_input.kind!r}.")
            if plan_input.ref != dataset.name:
                raise PlanningError(
                    f"Plan input {plan_input.input_id!r} references dataset {plan_input.ref!r}, expected {dataset.name!r}."
                )
            registered.append(
                self.register_value(
                    plan_input.input_id,
                    dataset.data,
                    role="input",
                    metadata={
                        "dataset_name": dataset.name,
                        "dataset_ref": plan_input.ref,
                        "source_type": dataset.source_type,
                        **dict(plan_input.metadata),
                    },
                )
            )
        return registered

    def get(self, artifact_id: str) -> RuntimeArtifact:
        """Return one registered artifact or raise a planning error."""
        artifact = self.artifacts.get(artifact_id)
        if artifact is None:
            raise PlanningError(f"Artifact store does not contain artifact id {artifact_id!r}.")
        return artifact

    def has(self, artifact_id: str) -> bool:
        """Return whether the artifact id is present."""
        return artifact_id in self.artifacts

    def list_ids(self) -> list[str]:
        """Return artifact ids in insertion order."""
        return list(self.artifacts)

    def intermediates(self) -> list[RuntimeArtifact]:
        """Return all registered intermediate artifacts."""
        return [artifact for artifact in self.artifacts.values() if artifact.role == "intermediate"]
