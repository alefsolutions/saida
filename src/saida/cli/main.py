"""Minimal CLI entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from saida import PromptAnalysisFrontend, Saida
from saida.config import LlmConfig, SaidaConfig
from saida.core import AnalysisResult, DatasetProfile
from saida.sources import CSVSource


def build_parser() -> argparse.ArgumentParser:
    """Create the SAIDA CLI argument parser."""
    parser = argparse.ArgumentParser(description="SAIDA library CLI")
    subparsers = parser.add_subparsers(dest="command")

    version_parser = subparsers.add_parser("version", help="Show the SAIDA CLI version.")
    version_parser.set_defaults(command="version")

    profile_parser = subparsers.add_parser("profile", help="Profile a CSV dataset.")
    profile_parser.add_argument("--csv", required=True, help="Path to the CSV file.")
    profile_parser.add_argument("--context", help="Optional path to a markdown context file.")
    profile_parser.add_argument("--json", action="store_true", help="Print the profile as JSON.")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a CSV dataset with a question.")
    analyze_parser.add_argument("--csv", required=True, help="Path to the CSV file.")
    analyze_parser.add_argument("--question", required=True, help="Question to analyze.")
    analyze_parser.add_argument("--context", help="Optional path to a markdown context file.")
    analyze_parser.add_argument("--json", action="store_true", help="Print the analysis result as JSON.")
    analyze_parser.add_argument("--show-plan", action="store_true", help="Print plan steps after the summary.")
    analyze_parser.add_argument("--show-trace", action="store_true", help="Print execution trace events after the summary.")
    analyze_parser.add_argument("--llm-provider", help="Optional LLM provider name, for example 'ollama'.")
    analyze_parser.add_argument("--llm-model", help="Optional LLM model name.")
    analyze_parser.add_argument("--llm-base-url", help="Optional LLM provider base URL.")

    return parser


def main() -> int:
    """Run the SAIDA CLI."""
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "version":
        print("SAIDA CLI 0.2.0")
        return 0

    if args.command == "profile":
        dataset = _load_csv_dataset(args.csv, args.context)
        profile = Saida().profile(dataset)
        if args.json:
            print(json.dumps(_profile_payload(profile), indent=2, allow_nan=False))
        else:
            print(f"Dataset: {profile.dataset_name}")
            print(f"Rows: {profile.row_count}")
            print(f"Columns: {profile.column_count}")
            print(f"Measures: {', '.join(profile.measure_columns) or 'none'}")
            print(f"Dimensions: {', '.join(profile.dimension_columns) or 'none'}")
            print(f"Time columns: {', '.join(profile.time_columns) or 'none'}")
        return 0

    if args.command == "analyze":
        dataset = _load_csv_dataset(args.csv, args.context)
        engine = PromptAnalysisFrontend(config=_build_cli_config(args.llm_provider, args.llm_model, args.llm_base_url))
        result = engine.analyze(dataset, args.question)
        if args.json:
            print(json.dumps(_analysis_payload(result), indent=2, allow_nan=False))
        else:
            print(result.summary)
            print("Tables:", ", ".join(table.name for table in result.tables))
            if args.show_plan:
                print("Plan:")
                for step in result.plan.steps:
                    print(f"- {step.step_id}: {step.description}")
            if args.show_trace:
                print("Trace:")
                for event in result.trace:
                    print(f"- {event.stage}: {event.message}")
            if result.warnings:
                print("Warnings:", "; ".join(result.warnings))
        return 0

    parser.print_help()
    return 1


def _load_csv_dataset(csv_path: str, context_path: str | None) -> object:
    """Load a CSV dataset for CLI commands."""
    csv_source = CSVSource(Path(csv_path), context_path=Path(context_path) if context_path else None)
    return csv_source.load()


def _profile_payload(profile: DatasetProfile) -> dict[str, object]:
    """Convert a dataset profile into a small JSON-safe payload."""
    return {
        "dataset_name": profile.dataset_name,
        "row_count": profile.row_count,
        "column_count": profile.column_count,
        "measure_columns": list(profile.measure_columns),
        "dimension_columns": list(profile.dimension_columns),
        "time_columns": list(profile.time_columns),
        "identifier_columns": list(profile.identifier_columns),
        "warnings": list(profile.warnings),
    }


def _analysis_payload(result: AnalysisResult) -> dict[str, object]:
    """Convert an analysis result into a small JSON-safe payload."""
    return result.to_response_dict()


def _build_cli_config(provider: str | None, model: str | None, base_url: str | None) -> SaidaConfig:
    """Build a minimal CLI config with optional LLM settings."""
    if not provider:
        return SaidaConfig()

    return SaidaConfig(
        llm=LlmConfig(
            enabled=True,
            provider=provider,
            model=model,
            base_url=base_url,
            use_for_prompting=True,
            use_for_reasoning=True,
        )
    )
