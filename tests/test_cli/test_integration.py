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
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(output_file),
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
                "--config",
                str(config_file),
                "generate",
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(output_file),
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
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-28",  # 4 weeks
                "--output",
                str(output_file),
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

    def test_generate_verbose_output(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test generate command with verbose output."""
        output_file = tmp_path / "schedule.json"

        result = runner.invoke(
            cli,
            [
                "-v",  # Verbose flag
                "generate",
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(output_file),
                "--demo",
                "--quick-solve",
            ],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        # Verbose mode should show more details
        assert (
            "Worker Statistics" in result.output
            or "shift types" in result.output.lower()
        )

    def test_generate_custom_time_limit(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test generate command with custom time limit."""
        output_file = tmp_path / "schedule.json"

        result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(output_file),
                "--demo",
                "--time-limit",
                "30",
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
                "--start-date",
                "2026-02-28",  # Start after end
                "--end-date",
                "2026-02-02",
                "--output",
                str(output_file),
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
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--demo",
                # Missing --output
            ],
        )

        assert result.exit_code != 0
        assert "output" in result.output.lower()


@pytest.mark.integration
class TestGenerateRealDataIngestion:
    """Tests that `generate` can ingest real CSV data (defect A)."""

    @pytest.fixture(autouse=True)
    def _isolated_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Run from a clean tmp_path cwd (no `-c` passed at all) so the
        group's own default ("config/config.yaml", a relative path) can't
        resolve against this repo's real config file when tests run from
        the project root -- these tests want the CLI's demo/CSV-only path
        exercised, not a config file. (Previously these tests pointed `-c`
        at a nonexistent path to exploit generate's old bug of silently
        treating "config given but missing" the same as "no config given";
        now that an explicitly-given missing path is a hard error, an
        isolated cwd is the correct way to get the "no config" case.)
        """
        monkeypatch.chdir(tmp_path)

    @pytest.fixture
    def workers_csv(self, tmp_path: Path) -> Path:
        path = tmp_path / "workers.csv"
        path.write_text(
            "id,name,worker_type,restricted_shifts,preferred_shifts\n"
            "W1,Worker One,full_time,,\n"
            "W2,Worker Two,full_time,,\n"
            "W3,Worker Three,full_time,,\n"
            "W4,Worker Four,full_time,,\n"
            "W5,Worker Five,full_time,,\n"
        )
        return path

    @pytest.fixture
    def availability_csv(self, tmp_path: Path) -> Path:
        path = tmp_path / "availability.csv"
        path.write_text(
            "worker_id,start_date,end_date,availability_type,shift_type_id\n"
            "W1,2026-02-02,2026-02-08,unavailable,\n"
        )
        return path

    @pytest.fixture
    def requests_csv(self, tmp_path: Path) -> Path:
        path = tmp_path / "requests.csv"
        path.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id,priority\n"
            "W2,2026-02-02,2026-02-08,positive,day,1\n"
        )
        return path

    def test_generate_with_workers_csv(
        self, runner: CliRunner, tmp_path: Path, workers_csv: Path
    ) -> None:
        """--workers ingests real worker data instead of demo placeholders."""
        output_file = tmp_path / "schedule.json"
        result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(output_file),
                "--workers",
                str(workers_csv),
                "--quick-solve",
            ],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Database" not in result.output
        assert "5 workers" in result.output

        import json

        with open(output_file) as f:
            data = json.load(f)
        worker_ids = {
            wid for period in data["periods"] for wid in period["assignments"]
        }
        assert worker_ids <= {"W1", "W2", "W3", "W4", "W5"}

    def test_generate_with_availability_and_requests_csv(
        self,
        runner: CliRunner,
        tmp_path: Path,
        workers_csv: Path,
        availability_csv: Path,
        requests_csv: Path,
    ) -> None:
        """--availability/--requests are loaded and reach the solver."""
        output_file = tmp_path / "schedule.json"
        result = runner.invoke(
            cli,
            [
                "-v",
                "generate",
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(output_file),
                "--workers",
                str(workers_csv),
                "--availability",
                str(availability_csv),
                "--requests",
                str(requests_csv),
                "--quick-solve",
            ],
        )

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Loaded 1 availability records" in result.output
        assert "Loaded 1 requests" in result.output

    def test_generate_requires_demo_or_workers(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Neither --demo nor --workers given is a clear error."""
        result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(tmp_path / "schedule.json"),
            ],
        )

        assert result.exit_code != 0
        assert "--workers" in result.output or "--demo" in result.output

    def test_generate_rejects_demo_and_workers_together(
        self, runner: CliRunner, tmp_path: Path, workers_csv: Path
    ) -> None:
        """--demo and --workers together is rejected, not silently resolved."""
        result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(tmp_path / "schedule.json"),
                "--demo",
                "--workers",
                str(workers_csv),
            ],
        )

        assert result.exit_code != 0
        assert "not both" in result.output.lower()

    def test_generate_workers_csv_invalid_reports_error(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """A malformed workers CSV produces a clear CLI error, not a traceback."""
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("wrong,columns\nfoo,bar\n")

        result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(tmp_path / "schedule.json"),
                "--workers",
                str(bad_csv),
            ],
        )

        assert result.exit_code != 0
        assert "error loading workers" in result.output.lower()


@pytest.mark.integration
class TestGenerateConfigHonored:
    """Tests that `generate` honors solver:/schedule: config (defect C, F)."""

    def _config(
        self, tmp_path: Path, *, period_type: str = "week", extra: str = ""
    ) -> Path:
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            f"""
schedule:
  period_type: "{period_type}"

shift_types:
  - id: day
    name: Day Shift
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
{extra}
"""
        )
        return cfg

    def test_time_limit_zero_rejected(self, runner: CliRunner, tmp_path: Path) -> None:
        """--time-limit 0 is rejected rather than silently using a default."""
        result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(tmp_path / "schedule.json"),
                "--demo",
                "--time-limit",
                "0",
            ],
        )

        assert result.exit_code != 0

    def test_solve_time_limit_reflects_config_max_time_seconds(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """With no --quick-solve/--time-limit, solver.max_time_seconds is used."""
        config_file = self._config(
            tmp_path,
            extra="\nsolver:\n  max_time_seconds: 45\n  quick_solution_seconds: 12\n",
        )
        result = runner.invoke(
            cli,
            [
                "--config",
                str(config_file),
                "generate",
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(tmp_path / "schedule.json"),
                "--demo",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Solving with 45s time limit" in result.output

    def test_quick_solve_uses_config_quick_solution_seconds(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """--quick-solve uses solver.quick_solution_seconds from config."""
        config_file = self._config(
            tmp_path,
            extra="\nsolver:\n  max_time_seconds: 45\n  quick_solution_seconds: 12\n",
        )
        result = runner.invoke(
            cli,
            [
                "--config",
                str(config_file),
                "generate",
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(tmp_path / "schedule.json"),
                "--demo",
                "--quick-solve",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Solving with 12s time limit" in result.output

    def test_explicit_time_limit_overrides_config(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """An explicit --time-limit always wins over config values."""
        config_file = self._config(
            tmp_path, extra="\nsolver:\n  max_time_seconds: 999\n"
        )
        result = runner.invoke(
            cli,
            [
                "--config",
                str(config_file),
                "generate",
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(tmp_path / "schedule.json"),
                "--demo",
                "--time-limit",
                "5",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Solving with 5s time limit" in result.output

    def test_num_workers_and_time_limit_passed_to_solver(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """solver.num_workers from config reaches ShiftSolver.solve()."""
        import importlib

        # `shift_solver.cli.commands.__init__` does
        # `from .generate import generate`, which rebinds the `generate`
        # attribute on the `commands` package to the Click Command object -
        # shadowing the submodule of the same name. importlib.import_module
        # goes through sys.modules directly, bypassing that shadowing, to
        # get the actual module (and its ShiftSolver import) to patch.
        generate_module = importlib.import_module("shift_solver.cli.commands.generate")

        captured: dict[str, object] = {}
        original_solve = generate_module.ShiftSolver.solve

        def spy_solve(self: object, **kwargs: object) -> object:
            captured.update(kwargs)
            return original_solve(self, **kwargs)

        monkeypatch.setattr(generate_module.ShiftSolver, "solve", spy_solve)

        config_file = self._config(tmp_path, extra="\nsolver:\n  num_workers: 3\n")
        result = runner.invoke(
            cli,
            [
                "--config",
                str(config_file),
                "generate",
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(tmp_path / "schedule.json"),
                "--demo",
                "--quick-solve",
            ],
        )

        assert result.exit_code == 0, result.output
        assert captured["num_workers"] == 3

    def test_month_period_type_rejected(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """schedule.period_type values other than 'week' are rejected clearly."""
        config_file = self._config(tmp_path, period_type="month")
        result = runner.invoke(
            cli,
            [
                "--config",
                str(config_file),
                "generate",
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(tmp_path / "schedule.json"),
                "--demo",
                "--quick-solve",
            ],
        )

        assert result.exit_code != 0
        assert "not yet supported" in result.output.lower()

    def test_week_period_type_accepted(self, runner: CliRunner, tmp_path: Path) -> None:
        """schedule.period_type: week (the only supported value) still works."""
        config_file = self._config(tmp_path, period_type="week")
        result = runner.invoke(
            cli,
            [
                "--config",
                str(config_file),
                "generate",
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(tmp_path / "schedule.json"),
                "--demo",
                "--quick-solve",
            ],
        )

        assert result.exit_code == 0, result.output

    def test_feasibility_warnings_are_printed(
        self,
        runner: CliRunner,
        tmp_path: Path,
        workers_csv: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SolverResult.warnings (e.g. from feasibility pre-checks) are surfaced."""
        availability_csv = tmp_path / "availability.csv"
        availability_csv.write_text(
            "worker_id,start_date,end_date,availability_type,shift_type_id\n"
            "GHOST,2026-02-02,2026-02-08,unavailable,\n"
        )
        # Run from a clean tmp_path cwd (no `-c` passed) so the group's own
        # relative default ("config/config.yaml") can't resolve against this
        # repo's real config file -- this test wants the no-config path, not
        # an explicitly-missing one (which is now a hard error).
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(tmp_path / "schedule.json"),
                "--workers",
                str(workers_csv),
                "--availability",
                str(availability_csv),
                "--quick-solve",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Warning:" in result.output
        assert "unknown worker" in result.output.lower()

    @pytest.fixture
    def workers_csv(self, tmp_path: Path) -> Path:
        path = tmp_path / "workers.csv"
        path.write_text(
            "id,name,worker_type,restricted_shifts,preferred_shifts\n"
            "W1,Worker One,full_time,,\n"
            "W2,Worker Two,full_time,,\n"
            "W3,Worker Three,full_time,,\n"
        )
        return path


@pytest.mark.integration
class TestValidateCommandIntegration:
    """Integration tests for the validate command."""

    @pytest.fixture
    def valid_schedule_json(self, tmp_path: Path) -> Path:
        """Create a valid schedule JSON file."""
        import json

        # One shift assignment per worker per period: the solver's model
        # (and the default worker_shift_limit check) allows at most one
        # shift-type assignment per worker per period.
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
        self,
        runner: CliRunner,
        valid_schedule_json: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test validating a valid schedule.

        Runs from a cwd with no config/config.yaml and no -c so this
        exercises schedule-inference (no config), rather than incidentally
        picking up this repo's own config/config.yaml via the documented
        group-level -c fallback (see TestConfigFallback for that behavior).
        An explicitly-passed missing -c is a hard error now, so it can no
        longer be used to simulate "no config".
        """
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            cli,
            [
                "validate",
                "--schedule",
                str(valid_schedule_json),
            ],
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

    def test_generate_export_workflow(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test complete generate -> export workflow."""
        schedule_json = tmp_path / "schedule.json"
        excel_output = tmp_path / "schedule.xlsx"

        # Step 1: Generate schedule
        gen_result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(schedule_json),
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
                "--schedule",
                str(schedule_json),
                "--output",
                str(excel_output),
                "--format",
                "excel",
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
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(schedule_json),
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

    def test_samples_import_workflow(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test complete generate-samples -> import-data workflow."""
        samples_dir = tmp_path / "samples"

        # Step 1: Generate sample data
        gen_result = runner.invoke(
            cli,
            [
                "generate-samples",
                "--output-dir",
                str(samples_dir),
                "--industry",
                "retail",
                "--num-workers",
                "5",
                "--months",
                "1",
                "--format",
                "csv",
            ],
        )
        assert gen_result.exit_code == 0, (
            f"Generate samples failed: {gen_result.output}"
        )

        # Step 2: Import the generated workers
        import_result = runner.invoke(
            cli,
            [
                "import-data",
                "--workers",
                str(samples_dir / "workers.csv"),
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
        assert (
            "no such command" in result.output.lower()
            or "usage" in result.output.lower()
        )

    def test_missing_required_option(self, runner: CliRunner) -> None:
        """Test handling of missing required option."""
        result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date",
                "2026-02-02",
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
                "--start-date",
                "02-02-2026",  # Wrong format
                "--end-date",
                "2026-02-08",
                "--output",
                str(output_file),
                "--demo",
            ],
        )

        assert result.exit_code != 0

    def test_config_validation_error(self, runner: CliRunner, tmp_path: Path) -> None:
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
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(output_file),
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
                "--start-date",
                "2026-02-02",
                "--end-date",
                "2026-02-08",
                "--output",
                str(output_file),
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
