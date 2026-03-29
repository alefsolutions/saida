from __future__ import annotations

from pathlib import Path
import json

import pytest

from saida.cli.main import main


def test_cli_analyze_runs_with_sample_csv(monkeypatch: object, tmp_path: Path, capsys: object) -> None:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text(
        "posted_at,revenue,region\n"
        "2026-01-01,100,West\n"
        "2026-02-01,90,West\n"
        "2026-03-01,80,East\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        ["saida", "analyze", "--csv", str(csv_path), "--question", "Why did revenue drop in March?"],
    )

    exit_code = main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Completed a diagnostic analysis for revenue on sales." in output


def test_cli_profile_supports_json_output(monkeypatch: object, tmp_path: Path, capsys: object) -> None:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text(
        "posted_at,revenue,region\n"
        "2026-01-01,100,West\n"
        "2026-02-01,90,West\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("sys.argv", ["saida", "profile", "--csv", str(csv_path), "--json"])

    exit_code = main()
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 0
    assert payload["dataset_name"] == "sales"
    assert payload["row_count"] == 2
    assert "revenue" in payload["measure_columns"]


def test_cli_analyze_supports_json_plan_and_trace_output(monkeypatch: object, tmp_path: Path, capsys: object) -> None:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text(
        "posted_at,revenue,region\n"
        "2026-01-01,100,West\n"
        "2026-02-01,90,West\n"
        "2026-03-01,80,East\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        ["saida", "analyze", "--csv", str(csv_path), "--question", "Why did revenue drop in March?", "--json"],
    )

    exit_code = main()
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 0
    assert payload["schema_version"] == "saida.response.v2"
    assert payload["status"] == "ok"
    assert payload["interpretation"]["task_type"] == "diagnostic"
    assert payload["history"][0]["stage"] == "adapter"
    assert any(table["name"] == "period_comparison" for table in payload["tables"])


def test_cli_version_command(monkeypatch: object, capsys: object) -> None:
    monkeypatch.setattr("sys.argv", ["saida", "version"])

    exit_code = main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "SAIDA CLI 0.3.0" in output


def test_cli_without_command_prints_help(monkeypatch: object, capsys: object) -> None:
    monkeypatch.setattr("sys.argv", ["saida"])

    exit_code = main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "usage:" in output.lower()


def test_cli_analyze_supports_plan_and_trace_flags(monkeypatch: object, tmp_path: Path, capsys: object) -> None:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text(
        "posted_at,revenue,region\n"
        "2026-01-01,100,West\n"
        "2026-02-01,90,West\n"
        "2026-03-01,80,East\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "saida",
            "analyze",
            "--csv",
            str(csv_path),
            "--question",
            "Why did revenue drop in March?",
            "--show-plan",
            "--show-trace",
        ],
    )

    exit_code = main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Plan:" in output
    assert "Trace:" in output
    assert "- summary_metrics:" in output
    assert "- adapter:" in output


def test_cli_profile_human_readable_output(monkeypatch: object, tmp_path: Path, capsys: object) -> None:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("posted_at,revenue,region\n2026-01-01,100,West\n", encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["saida", "profile", "--csv", str(csv_path)])

    exit_code = main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Dataset: sales" in output
    assert "Measures: revenue" in output


_CLI_PROFILE_JSON_CASES = [(index, index + 2) for index in range(1, 95)]


@pytest.mark.parametrize(("case_id", "row_count"), _CLI_PROFILE_JSON_CASES)
def test_cli_profile_json_handles_many_inputs(
    monkeypatch: object,
    tmp_path: Path,
    capsys: object,
    case_id: int,
    row_count: int,
) -> None:
    rows = ["posted_at,revenue,region"]
    for offset in range(row_count):
        rows.append(f"2026-03-{offset + 1:02d},{case_id + offset},Region{offset % 4}")
    csv_path = tmp_path / f"sales_{case_id}.csv"
    csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["saida", "profile", "--csv", str(csv_path), "--json"])

    exit_code = main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["dataset_name"] == f"sales_{case_id}"
    assert payload["row_count"] == row_count
    assert payload["column_count"] == 3
