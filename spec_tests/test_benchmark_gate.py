from __future__ import annotations

from pathlib import Path

from saida.benchmarking.ci_gate import evaluate_thresholds, run_benchmark_gate
from saida.benchmarking.suite import BenchmarkThresholds, load_benchmark_suite
from saida.models.types import BenchmarkReport, IntelligenceScores


def test_load_benchmark_suite():
    suite = load_benchmark_suite("benchmarks/suites/core_v1.json")
    assert suite.name == "saida-core-v1"
    assert len(suite.cases) >= 1
    assert suite.thresholds.ais >= 95.0


def test_evaluate_thresholds_detects_failures():
    report = BenchmarkReport(
        total=4,
        passed_analytics=2,
        passed_semantic=4,
        passed_reasoning=4,
        successful_executions=4,
        scores=IntelligenceScores(ais=50.0, ses=100.0, ris=100.0, sss=100.0, composite=80.0),
        details=[],
    )
    failures = evaluate_thresholds(report, BenchmarkThresholds(ais=95.0, ses=90.0, ris=90.0, sss=95.0))
    assert failures
    assert any("AIS" in f for f in failures)


def test_run_benchmark_gate_passes_core_suite(tmp_path: Path):
    parquet_root = tmp_path / "parquet"
    report, failures = run_benchmark_gate(
        suite=load_benchmark_suite("benchmarks/suites/core_v1.json"),
        dataset_path="benchmarks/datasets",
        dsn=f"sqlite+pysqlite:///{(tmp_path / 'bench.db').as_posix()}",
        parquet_root=str(parquet_root),
    )
    assert report.total >= 1
    assert failures == []
