"""DAG execution contract definitions for SAIDA's graph-oriented roadmap."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

ArtifactKind = Literal["dataset", "frame", "series", "scalar", "verification", "model", "forecast"]
ArtifactRole = Literal["input", "intermediate", "final", "auxiliary"]
PlanningGraphKind = Literal["capability_graph"]
ExecutionGraphKind = Literal["analysis_execution_dag"]
ExecutionScheduler = Literal["topological"]


@dataclass(slots=True)
class ArtifactTypeSpec:
    """Describe one portable artifact kind used in graph-oriented execution."""

    kind: ArtifactKind
    pandas_backed: bool
    supported_roles: tuple[ArtifactRole, ...]
    description: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class DagExecutionContract:
    """Describe the intended Phase 1 DAG execution target for SAIDA."""

    version: str
    planning_graph: PlanningGraphKind
    execution_graph: ExecutionGraphKind
    scheduler: ExecutionScheduler
    deterministic: bool
    parallel_execution: bool
    acyclic: bool
    directional_edges: bool
    final_output_required: bool
    artifact_types: list[ArtifactTypeSpec] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def artifact_kind_names(self) -> list[str]:
        return [artifact.kind for artifact in self.artifact_types]

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "planning_graph": self.planning_graph,
            "execution_graph": self.execution_graph,
            "scheduler": self.scheduler,
            "deterministic": self.deterministic,
            "parallel_execution": self.parallel_execution,
            "acyclic": self.acyclic,
            "directional_edges": self.directional_edges,
            "final_output_required": self.final_output_required,
            "artifact_types": [artifact.to_dict() for artifact in self.artifact_types],
            "notes": list(self.notes),
        }


def build_default_dag_execution_contract() -> DagExecutionContract:
    """Return the default Phase 1 DAG execution contract for SAIDA."""

    return DagExecutionContract(
        version="saida.dag.v1",
        planning_graph="capability_graph",
        execution_graph="analysis_execution_dag",
        scheduler="topological",
        deterministic=True,
        parallel_execution=False,
        acyclic=True,
        directional_edges=True,
        final_output_required=True,
        artifact_types=[
            ArtifactTypeSpec(
                kind="dataset",
                pandas_backed=True,
                supported_roles=("input",),
                description="Named dataset input registered before node execution begins.",
            ),
            ArtifactTypeSpec(
                kind="frame",
                pandas_backed=True,
                supported_roles=("intermediate", "final", "auxiliary"),
                description="Tabular pandas DataFrame artifact used for most relational and grouped results.",
            ),
            ArtifactTypeSpec(
                kind="series",
                pandas_backed=True,
                supported_roles=("intermediate", "final", "auxiliary"),
                description="Single-column pandas Series artifact for vector-like node outputs.",
            ),
            ArtifactTypeSpec(
                kind="scalar",
                pandas_backed=False,
                supported_roles=("intermediate", "final", "auxiliary"),
                description="Scalar value artifact for counts, aggregates, and other reduced outputs.",
            ),
            ArtifactTypeSpec(
                kind="verification",
                pandas_backed=False,
                supported_roles=("final", "auxiliary"),
                description="Structured verification artifact for yes or no style checks with supporting detail.",
            ),
            ArtifactTypeSpec(
                kind="model",
                pandas_backed=False,
                supported_roles=("final", "auxiliary"),
                description="Reserved artifact kind for model-training outputs in later phases.",
            ),
            ArtifactTypeSpec(
                kind="forecast",
                pandas_backed=False,
                supported_roles=("final", "auxiliary"),
                description="Reserved artifact kind for forecast outputs in later phases.",
            ),
        ],
        notes=[
            "The capability graph is used for planning-time support checks and legal plan compilation.",
            "The execution DAG is a runtime graph of nodes, edges, and typed artifacts.",
            "Phase 1 keeps the execution target deterministic and single-threaded.",
            "Pandas remains the low-level payload for frame and series artifacts.",
        ],
    )
