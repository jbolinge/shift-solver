"""Tests for CLI Plotly export integration."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from shift_solver.cli.main import cli


class TestCLIPlotlyExport:
    @pytest.fixture
    def sample_schedule_json(self, tmp_path: Path) -> Path:
        """Create a sample schedule JSON file for CLI testing."""
        schedule_data = {
            "schedule_id": "SCH-PLOTLY",
            "start_date": "2026-02-02",
            "end_date": "2026-02-08",
            "periods": [
                {
                    "period_index": 0,
                    "period_start": "2026-02-02",
                    "period_end": "2026-02-08",
                    "assignments": {
                        "W001": [
                            {"shift_type_id": "day", "date": "2026-02-02"},
                            {"shift_type_id": "night", "date": "2026-02-03"},
                        ],
                        "W002": [
                            {"shift_type_id": "day", "date": "2026-02-02"},
                        ],
                    },
                }
            ],
            "statistics": {},
        }
        schedule_file = tmp_path / "schedule.json"
        with open(schedule_file, "w") as f:
            json.dump(schedule_data, f)
        return schedule_file

    def test_cli_export_plotly_format_accepted(
        self, tmp_path: Path, sample_schedule_json: Path
    ) -> None:
        """'plotly' is accepted as a format choice."""
        output_dir = tmp_path / "charts"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "export",
                "--schedule",
                str(sample_schedule_json),
                "--output",
                str(output_dir),
                "--format",
                "plotly",
            ],
        )
        assert result.exit_code == 0, result.output

    def test_cli_export_plotly_creates_chart_directory(
        self, tmp_path: Path, sample_schedule_json: Path
    ) -> None:
        """Export with --format plotly creates output directory with HTML files."""
        output_dir = tmp_path / "charts"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "export",
                "--schedule",
                str(sample_schedule_json),
                "--output",
                str(output_dir),
                "--format",
                "plotly",
            ],
        )
        assert result.exit_code == 0, result.output
        assert output_dir.exists()
        for name in ["heatmap", "gantt", "fairness", "sunburst", "coverage"]:
            assert (output_dir / f"{name}.html").exists()
        assert (output_dir / "index.html").exists()

    def test_cli_export_plotly_with_real_schedule_json(
        self, tmp_path: Path, sample_schedule_json: Path
    ) -> None:
        """Full round-trip: load schedule JSON, export plotly, verify files."""
        output_dir = tmp_path / "plotly_output"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "export",
                "--schedule",
                str(sample_schedule_json),
                "--output",
                str(output_dir),
                "--format",
                "plotly",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Exported" in result.output
        assert "charts" in result.output.lower() or "index" in result.output.lower()

        # All 6 HTML files should exist
        html_files = list(output_dir.glob("*.html"))
        assert len(html_files) == 6
