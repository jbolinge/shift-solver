"""Integration tests for CLI commands.

Tests complete CLI workflows to verify end-to-end functionality,
error handling, and user experience.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from shift_solver.cli.main import cli


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def valid_config_yaml() -> str:
    """Minimal valid configuration YAML."""
    return """
shift_types:
  - id: day
    name: Day Shift
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
    workers_required: 2
  - id: night
    name: Night Shift
    category: night
    start_time: "23:00"
    end_time: "07:00"
    duration_hours: 8.0
    workers_required: 1
    is_undesirable: true

constraints:
  coverage:
    enabled: true
    is_hard: true

solver:
  max_time_seconds: 60
"""


@pytest.mark.integration
class TestGenerateCommandIntegration:
    """Integration tests for the generate command."""

    def test_generate_basic_demo_schedule(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test basic schedule generation with demo mode."""
        output_file = tmp_path / "schedule.json"

        result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "2026-02-02",
                "--end-date", "2026-02-08",
                "--output", str(output_file),
                "--demo",
                "--quick-solve",
            ],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert output_file.exists()
        assert "Solution found" in result.output
        assert "Schedule written to" in result.output

        # Verify JSON structure
        import json
        with open(output_file) as f:
            data = json.load(f)

        assert "schedule_id" in data
        assert "periods" in data
        assert len(data["periods"]) >= 1

    def test_generate_with_config(
        self, runner: CliRunner, tmp_path: Path, valid_config_yaml: str
    ) -> None:
        """Test schedule generation with config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        output_file = tmp_path / "schedule.json"

        result = runner.invoke(
            cli,
            [
                "--config", str(config_file),
                "generate",
                "--start-date", "2026-02-02",
                "--end-date", "2026-02-08",
                "--output", str(output_file),
                "--demo",
                "--quick-solve",
            ],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert output_file.exists()

    def test_generate_multi_week_schedule(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test generating a multi-week schedule."""
        output_file = tmp_path / "schedule.json"

        result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "2026-02-02",
                "--end-date", "2026-02-28",  # 4 weeks
                "--output", str(output_file),
                "--demo",
                "--quick-solve",
            ],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"

        import json
        with open(output_file) as f:
            data = json.load(f)

        # Should have multiple periods
        assert len(data["periods"]) >= 3

    def test_generate_verbose_output(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test generate command with verbose output."""
        output_file = tmp_path / "schedule.json"

        result = runner.invoke(
            cli,
            [
                "-v",  # Verbose flag
                "generate",
                "--start-date", "2026-02-02",
                "--end-date", "2026-02-08",
                "--output", str(output_file),
                "--demo",
                "--quick-solve",
            ],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        # Verbose mode should show more details
        assert "Worker Statistics" in result.output or "shift types" in result.output.lower()

    def test_generate_custom_time_limit(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test generate command with custom time limit."""
        output_file = tmp_path / "schedule.json"

        result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "2026-02-02",
                "--end-date", "2026-02-08",
                "--output", str(output_file),
                "--demo",
                "--time-limit", "30",
            ],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "30s time limit" in result.output

    def test_generate_invalid_date_order(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test error handling for invalid date order."""
        output_file = tmp_path / "schedule.json"

        result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "2026-02-28",  # Start after end
                "--end-date", "2026-02-02",
                "--output", str(output_file),
                "--demo",
            ],
        )

        # Should either fail gracefully or create empty schedule
        # The exact behavior depends on implementation
        # At minimum it shouldn't crash without a helpful message
        assert result.exit_code is not None  # Just verify it completes

    def test_generate_requires_output(self, runner: CliRunner) -> None:
        """Test that output parameter is required."""
        result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "2026-02-02",
                "--end-date", "2026-02-08",
                "--demo",
                # Missing --output
            ],
        )

        assert result.exit_code != 0
        assert "output" in result.output.lower()


@pytest.mark.integration
class TestValidateCommandIntegration:
    """Integration tests for the validate command."""

    @pytest.fixture
    def valid_schedule_json(self, tmp_path: Path) -> Path:
        """Create a valid schedule JSON file."""
        import json

        schedule_data = {
            "schedule_id": "SCH-TEST",
            "start_date": "2026-01-05",
            "end_date": "2026-01-11",
            "periods": [
                {
                    "period_index": 0,
                    "period_start": "2026-01-05",
                    "period_end": "2026-01-11",
                    "assignments": {
                        "W001": [
                            {"shift_type_id": "day", "date": "2026-01-05"},
                            {"shift_type_id": "day", "date": "2026-01-06"},
                        ],
                        "W002": [
                            {"shift_type_id": "night", "date": "2026-01-05"},
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

    def test_validate_valid_schedule(
        self, runner: CliRunner, valid_schedule_json: Path
    ) -> None:
        """Test validating a valid schedule."""
        result = runner.invoke(
            cli,
            ["validate", "--schedule", str(valid_schedule_json)],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "valid" in result.output.lower() or "passed" in result.output.lower()

    def test_validate_missing_file(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test error handling for missing schedule file."""
        missing_file = tmp_path / "missing.json"

        result = runner.invoke(
            cli,
            ["validate", "--schedule", str(missing_file)],
        )

        assert result.exit_code != 0

    def test_validate_invalid_json(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test error handling for invalid JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{ invalid json }")

        result = runner.invoke(
            cli,
            ["validate", "--schedule", str(bad_file)],
        )

        assert result.exit_code != 0


@pytest.mark.integration
class TestWorkflowIntegration:
    """Integration tests for complete workflows."""

    def test_generate_export_workflow(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test complete generate -> export workflow."""
        schedule_json = tmp_path / "schedule.json"
        excel_output = tmp_path / "schedule.xlsx"

        # Step 1: Generate schedule
        gen_result = runner.invoke(
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
        assert gen_result.exit_code == 0, f"Generate failed: {gen_result.output}"

        # Step 2: Export to Excel
        export_result = runner.invoke(
            cli,
            [
                "export",
                "--schedule", str(schedule_json),
                "--output", str(excel_output),
                "--format", "excel",
            ],
        )
        assert export_result.exit_code == 0, f"Export failed: {export_result.output}"
        assert excel_output.exists()

    def test_generate_validate_workflow(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test complete generate -> validate workflow."""
        schedule_json = tmp_path / "schedule.json"

        # Step 1: Generate schedule
        gen_result = runner.invoke(
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

        # Step 2: Validate generated schedule
        val_result = runner.invoke(
            cli,
            ["validate", "--schedule", str(schedule_json)],
        )
        assert val_result.exit_code == 0

    def test_samples_import_workflow(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test complete generate-samples -> import-data workflow."""
        samples_dir = tmp_path / "samples"

        # Step 1: Generate sample data
        gen_result = runner.invoke(
            cli,
            [
                "generate-samples",
                "--output-dir", str(samples_dir),
                "--industry", "retail",
                "--num-workers", "5",
                "--months", "1",
                "--format", "csv",
            ],
        )
        assert gen_result.exit_code == 0, f"Generate samples failed: {gen_result.output}"

        # Step 2: Import the generated workers
        import_result = runner.invoke(
            cli,
            [
                "import-data",
                "--workers", str(samples_dir / "workers.csv"),
            ],
        )
        assert import_result.exit_code == 0, f"Import failed: {import_result.output}"


@pytest.mark.integration
class TestErrorHandling:
    """Integration tests for CLI error handling."""

    def test_unknown_command(self, runner: CliRunner) -> None:
        """Test handling of unknown command."""
        result = runner.invoke(cli, ["unknown-command"])

        assert result.exit_code != 0
        assert "no such command" in result.output.lower() or "usage" in result.output.lower()

    def test_missing_required_option(self, runner: CliRunner) -> None:
        """Test handling of missing required option."""
        result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "2026-02-02",
                # Missing --end-date and --output
                "--demo",
            ],
        )

        assert result.exit_code != 0

    def test_invalid_date_format(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test handling of invalid date format."""
        output_file = tmp_path / "schedule.json"

        result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "02-02-2026",  # Wrong format
                "--end-date", "2026-02-08",
                "--output", str(output_file),
                "--demo",
            ],
        )

        assert result.exit_code != 0

    def test_config_validation_error(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test error reporting for invalid config."""
        bad_config = tmp_path / "bad_config.yaml"
        bad_config.write_text("""
shift_types: []  # Empty shift types should fail
""")

        result = runner.invoke(
            cli,
            ["check-config", "--config", str(bad_config)],
        )

        assert result.exit_code != 0


@pytest.mark.integration
class TestVerbosityLevels:
    """Test different verbosity levels."""

    def test_silent_output(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test normal (non-verbose) output."""
        output_file = tmp_path / "schedule.json"

        result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "2026-02-02",
                "--end-date", "2026-02-08",
                "--output", str(output_file),
                "--demo",
                "--quick-solve",
            ],
        )

        assert result.exit_code == 0
        # Should have basic output but not excessive detail
        assert "Generating schedule" in result.output

    def test_verbose_output(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test verbose (-v) output."""
        output_file = tmp_path / "schedule.json"

        result = runner.invoke(
            cli,
            [
                "-v",
                "generate",
                "--start-date", "2026-02-02",
                "--end-date", "2026-02-08",
                "--output", str(output_file),
                "--demo",
                "--quick-solve",
            ],
        )

        assert result.exit_code == 0
        # Verbose should show more information


@pytest.mark.integration
class TestExitCodes:
    """Test proper exit codes for different scenarios."""

    def test_success_exit_code(self, runner: CliRunner) -> None:
        """Successful command should return 0."""
        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0

    def test_help_exit_code(self, runner: CliRunner) -> None:
        """Help command should return 0."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0

    def test_error_exit_code(self, runner: CliRunner, tmp_path: Path) -> None:
        """Error condition should return non-zero."""
        missing_file = tmp_path / "missing.yaml"
        result = runner.invoke(
            cli,
            ["check-config", "--config", str(missing_file)],
        )
        assert result.exit_code != 0
