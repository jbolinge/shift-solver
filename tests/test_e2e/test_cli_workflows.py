"""End-to-end tests for CLI command workflows."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from shift_solver.cli import cli


@pytest.mark.e2e
class TestGenerateSamplesWorkflow:
    """Test the generate-samples command workflow."""

    def test_generate_samples_csv(self, e2e_runner: CliRunner, tmp_path: Path) -> None:
        """Test generating sample data to CSV."""
        output_dir = tmp_path / "samples"

        result = e2e_runner.invoke(
            cli,
            [
                "generate-samples",
                "--output-dir", str(output_dir),
                "--industry", "retail",
                "--num-workers", "10",
                "--months", "1",
                "--format", "csv",
                "--seed", "42",
            ],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert (output_dir / "workers.csv").exists()
        assert (output_dir / "shift_types.csv").exists()
        assert (output_dir / "availability.csv").exists()
        assert (output_dir / "requests.csv").exists()

    def test_generate_samples_excel(self, e2e_runner: CliRunner, tmp_path: Path) -> None:
        """Test generating sample data to Excel."""
        output_dir = tmp_path / "samples"

        result = e2e_runner.invoke(
            cli,
            [
                "generate-samples",
                "--output-dir", str(output_dir),
                "--industry", "healthcare",
                "--num-workers", "15",
                "--months", "2",
                "--format", "excel",
                "--seed", "123",
            ],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert (output_dir / "sample_data.xlsx").exists()

    def test_generate_samples_both_formats(
        self, e2e_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test generating sample data to both CSV and Excel."""
        output_dir = tmp_path / "samples"

        result = e2e_runner.invoke(
            cli,
            [
                "generate-samples",
                "--output-dir", str(output_dir),
                "--industry", "warehouse",
                "--num-workers", "12",
                "--format", "both",
            ],
        )

        assert result.exit_code == 0
        # CSV goes to csv/ subdirectory
        assert (output_dir / "csv" / "workers.csv").exists()
        # Excel goes to excel/ subdirectory
        assert (output_dir / "excel" / "sample_data.xlsx").exists()


@pytest.mark.e2e
class TestDemoScheduleWorkflow:
    """Test the demo schedule generation workflow."""

    def test_generate_demo_quick_solve(
        self, e2e_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test generating a schedule with demo data and quick solve."""
        output_file = tmp_path / "schedule.json"

        result = e2e_runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "2026-02-02",
                "--end-date", "2026-02-15",
                "--output", str(output_file),
                "--demo",
                "--quick-solve",
            ],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert output_file.exists()

        # Verify JSON structure
        with open(output_file) as f:
            schedule_data = json.load(f)

        assert "schedule_id" in schedule_data
        assert "start_date" in schedule_data
        assert "end_date" in schedule_data
        assert "periods" in schedule_data
        assert len(schedule_data["periods"]) > 0

    def test_generate_demo_custom_time_limit(
        self, e2e_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test generating with custom time limit."""
        output_file = tmp_path / "schedule.json"

        result = e2e_runner.invoke(
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

        assert result.exit_code == 0
        assert output_file.exists()


@pytest.mark.e2e
class TestGenerateAndExportWorkflow:
    """Test generate -> export workflow."""

    def test_generate_then_export_excel(
        self, e2e_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test generating schedule then exporting to Excel."""
        schedule_json = tmp_path / "schedule.json"
        excel_output = tmp_path / "schedule.xlsx"

        # Step 1: Generate schedule
        result = e2e_runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "2026-02-02",
                "--end-date", "2026-02-22",
                "--output", str(schedule_json),
                "--demo",
                "--quick-solve",
            ],
        )
        assert result.exit_code == 0, f"Generate failed: {result.output}"

        # Step 2: Export to Excel
        result = e2e_runner.invoke(
            cli,
            [
                "export",
                "--schedule", str(schedule_json),
                "--output", str(excel_output),
                "--format", "excel",
            ],
        )
        assert result.exit_code == 0, f"Export failed: {result.output}"
        assert excel_output.exists()

        # Verify Excel file has content
        import openpyxl

        wb = openpyxl.load_workbook(excel_output)
        assert len(wb.sheetnames) > 0


@pytest.mark.e2e
class TestGenerateValidateWorkflow:
    """Test generate -> validate workflow."""

    def test_generate_then_validate(
        self, e2e_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test generating schedule then validating it."""
        schedule_json = tmp_path / "schedule.json"

        # Step 1: Generate schedule
        result = e2e_runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "2026-02-02",
                "--end-date", "2026-02-15",
                "--output", str(schedule_json),
                "--demo",
                "--quick-solve",
            ],
        )
        assert result.exit_code == 0, f"Generate failed: {result.output}"

        # Step 2: Validate schedule
        result = e2e_runner.invoke(
            cli,
            [
                "validate",
                "--schedule", str(schedule_json),
            ],
        )
        # Should pass validation
        assert result.exit_code == 0, f"Validate failed: {result.output}"
        assert "PASSED" in result.output or "valid" in result.output.lower()


@pytest.mark.e2e
class TestCompleteWorkflowCSV:
    """Test complete workflow: samples -> import -> generate -> export -> validate."""

    def test_complete_csv_workflow(
        self, e2e_runner: CliRunner, tmp_path: Path, sample_config_file: Path
    ) -> None:
        """Test complete end-to-end workflow with CSV data."""
        data_dir = tmp_path / "data"
        schedule_json = tmp_path / "schedule.json"
        schedule_xlsx = tmp_path / "schedule.xlsx"

        # Step 1: Generate sample data
        result = e2e_runner.invoke(
            cli,
            [
                "generate-samples",
                "--output-dir", str(data_dir),
                "--industry", "retail",
                "--num-workers", "8",
                "--months", "1",
                "--format", "csv",
                "--seed", "42",
            ],
        )
        assert result.exit_code == 0, f"Generate samples failed: {result.output}"

        # Step 2: Import data (validation only - no DB persistence yet)
        result = e2e_runner.invoke(
            cli,
            [
                "import-data",
                "--workers", str(data_dir / "workers.csv"),
                "--availability", str(data_dir / "availability.csv"),
                "--requests", str(data_dir / "requests.csv"),
            ],
        )
        assert result.exit_code == 0, f"Import failed: {result.output}"

        # Step 3: Generate schedule (demo mode since DB not yet implemented)
        result = e2e_runner.invoke(
            cli,
            [
                "-c", str(sample_config_file),
                "generate",
                "--start-date", "2026-02-02",
                "--end-date", "2026-02-22",
                "--output", str(schedule_json),
                "--demo",
                "--quick-solve",
            ],
        )
        assert result.exit_code == 0, f"Generate failed: {result.output}"

        # Step 4: Export to Excel
        result = e2e_runner.invoke(
            cli,
            [
                "export",
                "--schedule", str(schedule_json),
                "--output", str(schedule_xlsx),
                "--format", "excel",
            ],
        )
        assert result.exit_code == 0, f"Export failed: {result.output}"

        # Step 5: Validate
        result = e2e_runner.invoke(
            cli,
            [
                "validate",
                "--schedule", str(schedule_json),
            ],
        )
        assert result.exit_code == 0, f"Validate failed: {result.output}"

        # Verify all files exist
        assert schedule_json.exists()
        assert schedule_xlsx.exists()


@pytest.mark.e2e
@pytest.mark.smoke
class TestCLISmoke:
    """Quick smoke tests for CLI commands."""

    def test_version_command(self, e2e_runner: CliRunner) -> None:
        """Test version command works."""
        result = e2e_runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert "shift-solver" in result.output

    def test_help_command(self, e2e_runner: CliRunner) -> None:
        """Test help command works."""
        result = e2e_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "shift-solver" in result.output

    def test_check_config_valid(
        self, e2e_runner: CliRunner, sample_config_file: Path
    ) -> None:
        """Test check-config with valid config."""
        result = e2e_runner.invoke(
            cli,
            ["check-config", "--config", str(sample_config_file)],
        )
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_list_shifts_with_config(
        self, e2e_runner: CliRunner, sample_config_file: Path
    ) -> None:
        """Test list-shifts command."""
        result = e2e_runner.invoke(
            cli,
            ["list-shifts", "--config", str(sample_config_file)],
        )
        assert result.exit_code == 0
        assert "Shift Types" in result.output

    def test_init_db(self, e2e_runner: CliRunner, tmp_path: Path) -> None:
        """Test init-db command."""
        db_path = tmp_path / "test.db"
        result = e2e_runner.invoke(
            cli,
            ["init-db", "--db", str(db_path)],
        )
        assert result.exit_code == 0
        assert db_path.exists()
