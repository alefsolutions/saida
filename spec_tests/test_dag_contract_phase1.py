from __future__ import annotations

from saida.core.dag_contract import build_default_dag_execution_contract


def test_default_dag_execution_contract_defines_phase_one_target() -> None:
    contract = build_default_dag_execution_contract()

    assert contract.version == "saida.dag.v1"
    assert contract.planning_graph == "capability_graph"
    assert contract.execution_graph == "analysis_execution_dag"
    assert contract.scheduler == "topological"
    assert contract.deterministic is True
    assert contract.parallel_execution is False
    assert contract.acyclic is True
    assert contract.directional_edges is True
    assert contract.final_output_required is True


def test_default_dag_execution_contract_exposes_expected_artifact_taxonomy() -> None:
    contract = build_default_dag_execution_contract()

    assert contract.artifact_kind_names() == [
        "dataset",
        "frame",
        "series",
        "scalar",
        "verification",
        "model",
        "forecast",
    ]
    artifact_lookup = {artifact.kind: artifact for artifact in contract.artifact_types}

    assert artifact_lookup["dataset"].pandas_backed is True
    assert artifact_lookup["dataset"].supported_roles == ("input",)
    assert artifact_lookup["frame"].supported_roles == ("intermediate", "final", "auxiliary")
    assert artifact_lookup["series"].pandas_backed is True
    assert artifact_lookup["scalar"].pandas_backed is False
    assert artifact_lookup["verification"].supported_roles == ("final", "auxiliary")


def test_default_dag_execution_contract_serializes_cleanly() -> None:
    contract = build_default_dag_execution_contract()

    payload = contract.to_dict()

    assert payload["version"] == "saida.dag.v1"
    assert payload["artifact_types"][0]["kind"] == "dataset"
    assert payload["artifact_types"][1]["kind"] == "frame"
    assert "execution DAG" in payload["notes"][1]
