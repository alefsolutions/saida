from __future__ import annotations

from pathlib import Path


def test_dag_plan_authoring_guide_documents_explicit_plan_contracts() -> None:
    guide_path = Path(__file__).resolve().parents[1] / "docs" / "guides" / "dag-plan-authoring.md"
    content = guide_path.read_text(encoding="utf-8")

    assert "DAG Plan Authoring" in content
    assert "`final_output_ref`" in content
    assert "`PromptAnalysisFrontend.plan(...)` now emits graph-valid plans" in content
    assert "existing single-step authored plans still execute" in content


def test_schema_spec_and_api_usage_describe_dag_runtime_contracts() -> None:
    docs_root = Path(__file__).resolve().parents[1] / "docs"
    schema_spec = (docs_root / "reference" / "schema-spec.md").read_text(encoding="utf-8")
    api_usage = (docs_root / "reference" / "api-usage.md").read_text(encoding="utf-8")
    architecture = (docs_root / "overview" / "architecture.md").read_text(encoding="utf-8")

    assert "`StepInputRef`" in schema_spec
    assert "`StepOutputSpec`" in schema_spec
    assert "`ExecutionArtifact`" in schema_spec
    assert "deterministic DAG scheduler" in api_usage
    assert "execution artifact store" in architecture
    assert "`artifact_index` and `node_results` expose graph execution lineage" in architecture
