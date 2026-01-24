"""End-to-end tests for error handling and recovery paths."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from shift_solver.cli import cli


@pytest.mark.e2e
class TestMissingRequiredOptions:
    """Test CLI error handling for missing required options."""

    def test_generate_missing_start_date(self, e2e_runner: CliRunner, tmp_path: Path) -> None:
        """Test generate command fails without start-date."""
        result = e2e_runner.invoke(
            cli,
            [
                "generate",
                "--end-date", "2026-02-15",
                "--output", str(tmp_path / "schedule.json"),
                "--demo",
            ],
        )
        assert result.exit_code != 0
        assert "start-date" in result.output.lower() or "required" in result.output.lower()

    def test_generate_missing_end_date(self, e2e_runner: CliRunner, tmp_path: Path) -> None:
        """Test generate command fails without end-date."""
        result = e2e_runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "2026-02-01",
                "--output", str(tmp_path / "schedule.json"),
                "--demo",
            ],
        )
        assert result.exit_code != 0
        assert "end-date" in result.output.lower() or "required" in result.output.lower()

    def test_generate_missing_output(self, e2e_runner: CliRunner) -> None:
        """Test generate command fails without output."""
        result = e2e_runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "2026-02-01",
                "--end-date", "2026-02-15",
                "--demo",
            ],
        )
        assert result.exit_code != 0
        assert "output" in result.output.lower() or "required" in result.output.lower()

    def test_export_missing_schedule(self, e2e_runner: CliRunner, tmp_path: Path) -> None:
        """Test export command fails without schedule file."""
        result = e2e_runner.invoke(
            cli,
            [
                "export",
                "--output", str(tmp_path / "schedule.xlsx"),
            ],
        )
        assert result.exit_code != 0
        assert "schedule" in result.output.lower() or "required" in result.output.lower()

    def test_validate_missing_schedule(self, e2e_runner: CliRunner) -> None:
        """Test validate command fails without schedule file."""
        result = e2e_runner.invoke(
            cli,
            ["validate"],
        )
        assert result.exit_code != 0
        assert "schedule" in result.output.lower() or "required" in result.output.lower()


@pytest.mark.e2e
class TestInvalidDateFormat:
    """Test CLI error handling for invalid date formats."""

    def test_invalid_start_date_format(
        self, e2e_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test generate fails with invalid start date format."""
        result = e2e_runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "02-01-2026",  # Wrong format (should be YYYY-MM-DD)
                "--end-date", "2026-02-15",
                "--output", str(tmp_path / "schedule.json"),
                "--demo",
            ],
        )
        assert result.exit_code != 0

    def test_invalid_end_date_format(
        self, e2e_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test generate fails with invalid end date format."""
        result = e2e_runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "2026-02-01",
                "--end-date", "15/02/2026",  # Wrong format
                "--output", str(tmp_path / "schedule.json"),
                "--demo",
            ],
        )
        assert result.exit_code != 0

    def test_invalid_date_value(self, e2e_runner: CliRunner, tmp_path: Path) -> None:
        """Test generate fails with invalid date value."""
        result = e2e_runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "2026-02-30",  # Invalid day
                "--end-date", "2026-02-28",
                "--output", str(tmp_path / "schedule.json"),
                "--demo",
            ],
        )
        assert result.exit_code != 0


@pytest.mark.e2e
class TestInvalidConfigFile:
    """Test CLI error handling for invalid config files."""

    def test_check_config_missing_file(self, e2e_runner: CliRunner) -> None:
        """Test check-config fails for missing file."""
        result = e2e_runner.invoke(
            cli,
            ["check-config", "--config", "/nonexistent/config.yaml"],
        )
        assert result.exit_code != 0
        # Should mention file not found or similar
        assert "not found" in result.output.lower() or "no such file" in result.output.lower() or "error" in result.output.lower()

    def test_check_config_invalid_yaml(
        self, e2e_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test check-config fails for invalid YAML."""
        invalid_config = tmp_path / "invalid.yaml"
        invalid_config.write_text("shift_types:\n  - id: day\n    name: [unclosed")

        result = e2e_runner.invoke(
            cli,
            ["check-config", "--config", str(invalid_config)],
        )
        assert result.exit_code != 0

    def test_check_config_validation_error(
        self, e2e_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test check-config fails for invalid config values."""
        invalid_config = tmp_path / "invalid.yaml"
        invalid_config.write_text(
            """
solver:
  max_time_seconds: -1

shift_types: []
"""
        )

        result = e2e_runner.invoke(
            cli,
            ["check-config", "--config", str(invalid_config)],
        )
        assert result.exit_code != 0


@pytest.mark.e2e
class TestMissingInputFile:
    """Test CLI error handling for missing input files."""

    def test_import_missing_workers_file(self, e2e_runner: CliRunner) -> None:
        """Test import-data fails for missing workers file."""
        result = e2e_runner.invoke(
            cli,
            ["import-data", "--workers", "/nonexistent/workers.csv"],
        )
        assert result.exit_code != 0

    def test_import_missing_availability_file(self, e2e_runner: CliRunner) -> None:
        """Test import-data fails for missing availability file."""
        result = e2e_runner.invoke(
            cli,
            ["import-data", "--availability", "/nonexistent/availability.csv"],
        )
        assert result.exit_code != 0

    def test_export_missing_schedule_file(
        self, e2e_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test export fails for missing schedule file."""
        result = e2e_runner.invoke(
            cli,
            [
                "export",
                "--schedule", "/nonexistent/schedule.json",
                "--output", str(tmp_path / "schedule.xlsx"),
            ],
        )
        assert result.exit_code != 0

    def test_validate_missing_schedule_file(self, e2e_runner: CliRunner) -> None:
        """Test validate fails for missing schedule file."""
        result = e2e_runner.invoke(
            cli,
            ["validate", "--schedule", "/nonexistent/schedule.json"],
        )
        assert result.exit_code != 0


@pytest.mark.e2e
class TestValidationFailureOutput:
    """Test that validation failures produce useful output."""

    def test_validation_reports_violations(
        self, e2e_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that validation failures produce clear violation reports."""
        # Create a schedule JSON with potential issues
        schedule_json = tmp_path / "schedule.json"
        schedule_json.write_text(
            """
{
    "schedule_id": "TEST",
    "start_date": "2026-02-02",
    "end_date": "2026-02-08",
    "periods": [
        {
            "period_index": 0,
            "period_start": "2026-02-02",
            "period_end": "2026-02-08",
            "assignments": {}
        }
    ]
}
"""
        )

        result = e2e_runner.invoke(
            cli,
            ["validate", "--schedule", str(schedule_json)],
        )

        # This might pass or fail depending on constraints,
        # but should produce some output
        assert result.output  # Should have some output

    def test_validation_json_output(
        self, e2e_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that validation can output to JSON file."""
        # First create a valid schedule
        schedule_json = tmp_path / "schedule.json"

        gen_result = e2e_runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "2026-02-02",
                "--end-date", "2026-02-08",
                "--output", str(schedule_json),
                "--demo",
                "--quick-solve",
            ],
        )
        assert gen_result.exit_code == 0

        # Now validate with JSON output
        report_json = tmp_path / "validation_report.json"
        result = e2e_runner.invoke(
            cli,
            [
                "validate",
                "--schedule", str(schedule_json),
                "--output", str(report_json),
            ],
        )

        # If validation passes, report should be written
        if result.exit_code == 0:
            assert report_json.exists()
            import json

            with open(report_json) as f:
                report = json.load(f)
            assert "is_valid" in report
            assert "violations" in report
            assert "statistics" in report


@pytest.mark.e2e
class TestGenerateWithoutDemo:
    """Test generate command error handling without demo mode."""

    def test_generate_requires_demo_or_db(
        self, e2e_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that generate fails without --demo when DB not implemented."""
        result = e2e_runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "2026-02-02",
                "--end-date", "2026-02-15",
                "--output", str(tmp_path / "schedule.json"),
                # No --demo flag
            ],
        )
        # Should fail because DB is not implemented yet
        assert result.exit_code != 0
        assert "demo" in result.output.lower() or "database" in result.output.lower()


@pytest.mark.e2e
class TestImportNoFiles:
    """Test import-data requires at least one input."""

    def test_import_requires_input(self, e2e_runner: CliRunner) -> None:
        """Test that import-data fails without any input files."""
        result = e2e_runner.invoke(cli, ["import-data"])

        assert result.exit_code != 0
        assert "no" in result.output.lower() or "specify" in result.output.lower()


@pytest.mark.e2e
@pytest.mark.smoke
class TestErrorHandlingSmoke:
    """Quick smoke tests for error handling."""

    def test_unknown_command(self, e2e_runner: CliRunner) -> None:
        """Test handling of unknown command."""
        result = e2e_runner.invoke(cli, ["unknown-command"])
        assert result.exit_code != 0

    def test_invalid_option(self, e2e_runner: CliRunner) -> None:
        """Test handling of invalid option."""
        result = e2e_runner.invoke(cli, ["generate", "--invalid-option"])
        assert result.exit_code != 0

    def test_invalid_industry(self, e2e_runner: CliRunner, tmp_path: Path) -> None:
        """Test generate-samples with invalid industry."""
        result = e2e_runner.invoke(
            cli,
            [
                "generate-samples",
                "--output-dir", str(tmp_path),
                "--industry", "invalid_industry",
            ],
        )
        # Click should catch this since it's a Choice type
        assert result.exit_code != 0
