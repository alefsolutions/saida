from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from saida import SaidaAgent
from saida.benchmarking.suite import BenchmarkSuite, BenchmarkThresholds, load_benchmark_suite
from saida.connectors.filesystem import FileSystemConnector
from saida.models.types import BenchmarkReport
from saida.utils.config import SaidaConfig


def evaluate_thresholds(report: BenchmarkReport, thresholds: BenchmarkThresholds) -> list[str]:
    failures: list[str] = []
    if report.scores.ais < thresholds.ais:
        failures.append(f"AIS {report.scores.ais:.2f} < {thresholds.ais:.2f}")
    if report.scores.ses < thresholds.ses:
        failures.append(f"SES {report.scores.ses:.2f} < {thresholds.ses:.2f}")
    if report.scores.ris < thresholds.ris:
        failures.append(f"RIS {report.scores.ris:.2f} < {thresholds.ris:.2f}")
    if report.scores.sss < thresholds.sss:
        failures.append(f"SSS {report.scores.sss:.2f} < {thresholds.sss:.2f}")
    return failures


def run_benchmark_gate(suite: BenchmarkSuite, dataset_path: str, dsn: str, parquet_root: str) -> tuple[BenchmarkReport, list[str]]:
    cfg = SaidaConfig(
        control_plane_dsn=dsn,
        llm_provider="mock",
        embedding_provider="mock",
        parquet_root=parquet_root,
    )
    agent = SaidaAgent(cfg)
    agent.add_connector(FileSystemConnector(dataset_path))
    agent.ingest_all()
    report = agent.run_benchmarks(cases=suite.cases)
    failures = evaluate_thresholds(report, suite.thresholds)
    return report, failures


def main() -> None:
    parser = argparse.ArgumentParser(description="SAIDA benchmark threshold gate")
    parser.add_argument("--suite", default="benchmarks/suites/core_v1.json")
    parser.add_argument("--datasets", default="benchmarks/datasets")
    parser.add_argument("--dsn", default="sqlite+pysqlite:///:memory:")
    parser.add_argument("--parquet-root", default="./.saida/bench-parquet")
    args = parser.parse_args()

    suite = load_benchmark_suite(args.suite)
    report, failures = run_benchmark_gate(
        suite=suite,
        dataset_path=args.datasets,
        dsn=args.dsn,
        parquet_root=args.parquet_root,
    )

    print(json.dumps({"suite": suite.name, "report": asdict(report), "failures": failures}, ensure_ascii=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
