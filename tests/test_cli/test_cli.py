"""Tests for CLI commands."""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest
from click.testing import CliRunner

from shift_solver.cli.main import cli


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def sample_config_file() -> Path:
    """Create a sample config file for testing."""
    yaml_content = """
shift_types:
  - id: day_shift
    name: Day Shift
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
"""
    with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        return Path(f.name)


class TestCLIBasics:
    """Tests for basic CLI functionality."""

    def test_cli_exists(self, runner: CliRunner) -> None:
        """CLI main group exists and is callable."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "shift-solver" in result.output.lower() or "usage" in result.output.lower()

    def test_version_command(self, runner: CliRunner) -> None:
        """Version command shows version."""
        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_verbose_option(self, runner: CliRunner) -> None:
        """Verbose option is accepted."""
        result = runner.invoke(cli, ["-v", "version"])
        assert result.exit_code == 0


class TestCheckConfigCommand:
    """Tests for check-config command."""

    def test_check_config_valid(
        self, runner: CliRunner, sample_config_file: Path
    ) -> None:
        """check-config validates a valid config file."""
        result = runner.invoke(cli, ["check-config", "--config", str(sample_config_file)])

        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_check_config_invalid_file(self, runner: CliRunner, tmp_path: Path) -> None:
        """check-config reports error for missing file."""
        missing_file = tmp_path / "missing.yaml"
        result = runner.invoke(cli, ["check-config", "--config", str(missing_file)])

        assert result.exit_code != 0

    def test_check_config_invalid_yaml(self, runner: CliRunner, tmp_path: Path) -> None:
        """check-config reports error for invalid config."""
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("shift_types: []")  # No shift types

        result = runner.invoke(cli, ["check-config", "--config", str(invalid_file)])

        # Should fail validation (no shift types)
        assert result.exit_code != 0


class TestListCommands:
    """Tests for list commands."""

    def test_list_shifts(self, runner: CliRunner) -> None:
        """list-shifts command exists."""
        result = runner.invoke(cli, ["list-shifts", "--help"])
        assert result.exit_code == 0


class TestGenerateCommand:
    """Tests for generate command (placeholder)."""

    def test_generate_help(self, runner: CliRunner) -> None:
        """generate command shows help."""
        result = runner.invoke(cli, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--start-date" in result.output
        assert "--end-date" in result.output


class TestLoadConstraintConfigs:
    """Tests that config.yaml constraints reach the solver (not discarded)."""

    def _write_config(self, tmp_path: Path) -> Path:
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            """
constraints:
  fairness:
    enabled: false
    is_hard: false
    weight: 777
    parameters:
      categories: ["night"]
shift_types:
  - id: day_shift
    name: Day Shift
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
  - id: night_shift
    name: Night Shift
    category: night
    start_time: "23:00"
    end_time: "07:00"
    duration_hours: 8.0
"""
        )
        return cfg

    def test_converts_to_base_constraint_config(self, tmp_path: Path) -> None:
        """Loader returns solver-side ConstraintConfig objects with get_param."""
        from shift_solver.cli.commands.generate import _load_constraint_configs
        from shift_solver.constraints.base import ConstraintConfig as BaseConfig

        configs = _load_constraint_configs(self._write_config(tmp_path), verbose=0)

        assert "fairness" in configs
        fairness = configs["fairness"]
        assert isinstance(fairness, BaseConfig)
        assert fairness.enabled is False
        assert fairness.weight == 777
        # get_param is the behaviour the dataclass adds over the schema model
        assert fairness.get_param("categories") == ["night"]

    def test_no_config_returns_empty(self, tmp_path: Path) -> None:
        """Missing config => empty dict (solver uses registry defaults)."""
        from shift_solver.cli.commands.generate import _load_constraint_configs

        assert _load_constraint_configs(tmp_path / "missing.yaml", verbose=0) == {}

    def test_generate_demo_honors_config(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """End-to-end: generate --demo with a config runs and writes output."""
        out = tmp_path / "sched.json"
        result = runner.invoke(
            cli,
            [
                "--config",
                str(self._write_config(tmp_path)),
                "generate",
                "--demo",
                "--quick-solve",
                "--start-date",
                "2026-06-01",
                "--end-date",
                "2026-06-07",
                "-o",
                str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out.exists()


class TestDetermineTimeLimit:
    """Unit tests for solver: config honoring in time limit resolution
    (defect C)."""

    def test_explicit_cli_flag_always_wins(self) -> None:
        from shift_solver.cli.commands.generate import _determine_time_limit
        from shift_solver.config.schema import SolverConfig

        solver_config = SolverConfig(max_time_seconds=999, quick_solution_seconds=111)
        assert _determine_time_limit(45, True, solver_config) == 45
        assert _determine_time_limit(45, False, solver_config) == 45

    def test_quick_solve_uses_config_quick_solution_seconds(self) -> None:
        from shift_solver.cli.commands.generate import _determine_time_limit
        from shift_solver.config.schema import SolverConfig

        solver_config = SolverConfig(quick_solution_seconds=17)
        assert _determine_time_limit(None, True, solver_config) == 17

    def test_default_uses_config_max_time_seconds(self) -> None:
        from shift_solver.cli.commands.generate import _determine_time_limit
        from shift_solver.config.schema import SolverConfig

        solver_config = SolverConfig(max_time_seconds=42)
        assert _determine_time_limit(None, False, solver_config) == 42

    def test_falls_back_to_solverconfig_defaults_with_no_config_file(self) -> None:
        from shift_solver.cli.commands.generate import _determine_time_limit
        from shift_solver.config.schema import SolverConfig

        defaults = SolverConfig()
        assert _determine_time_limit(None, True, defaults) == 60
        assert _determine_time_limit(None, False, defaults) == 3600


class TestExplicitVsDefaultConfigPath:
    """A -c/--config path the user explicitly typed must error clearly if
    missing, distinct from click's own 'config/config.yaml' default simply
    not existing (in which case there is no config file, not a bad one)."""

    def test_generate_bad_explicit_config_path_errors(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """An explicit group-level -c pointing at a missing file is a hard
        error for `generate`, not silently treated as 'no config'."""
        missing = tmp_path / "does-not-exist.yaml"
        result = runner.invoke(
            cli,
            [
                "-c", str(missing),
                "generate",
                "--start-date", "2026-06-01",
                "--end-date", "2026-06-07",
                "--output", str(tmp_path / "sched.json"),
                "--demo",
                "--quick-solve",
            ],
        )

        assert result.exit_code != 0
        assert str(missing) in result.output
        assert not (tmp_path / "sched.json").exists()

    def test_list_shifts_bad_explicit_config_path_errors(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """An explicit group-level -c pointing at a missing file is a hard
        error for `list-shifts` too, instead of the misleading 'No
        configuration file found. Specify with --config.' message (which
        implies none was given, when one *was* given -- it just doesn't
        exist)."""
        missing = tmp_path / "does-not-exist.yaml"
        result = runner.invoke(cli, ["-c", str(missing), "list-shifts"])

        assert result.exit_code != 0
        assert str(missing) in result.output
        assert "no configuration file found" not in result.output.lower()

    def test_list_shifts_own_bad_config_path_errors(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """list-shifts' own --config option also errors clearly on a
        missing path (click's exists=True catches this before the command
        body runs)."""
        missing = tmp_path / "does-not-exist.yaml"
        result = runner.invoke(cli, ["list-shifts", "--config", str(missing)])

        assert result.exit_code != 0
        assert str(missing) in result.output

    def test_validate_bad_explicit_config_path_errors(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """An explicit group-level -c pointing at a missing file is a hard
        error for `validate` too -- silently validating against registry
        defaults instead of the intended config produces confidently wrong
        violations."""
        schedule = tmp_path / "schedule.json"
        schedule.write_text(
            '{"schedule_id": "s1", "start_date": "2026-06-01", '
            '"end_date": "2026-06-07", "period_type": "week", "periods": []}'
        )
        missing = tmp_path / "does-not-exist.yaml"
        result = runner.invoke(
            cli,
            ["-c", str(missing), "validate", "--schedule", str(schedule)],
        )

        assert result.exit_code != 0
        assert str(missing) in result.output

    def test_generate_default_config_absent_still_allowed(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No -c given at all, and the default 'config/config.yaml' doesn't
        exist relative to cwd => still falls back to demo shift types (not
        an error) -- this is 'no config specified', not 'a bad path'."""
        monkeypatch.chdir(tmp_path)
        assert not (tmp_path / "config" / "config.yaml").exists()

        output = tmp_path / "sched.json"
        result = runner.invoke(
            cli,
            [
                "generate",
                "--start-date", "2026-06-01",
                "--end-date", "2026-06-07",
                "--output", str(output),
                "--demo",
                "--quick-solve",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "demo shift types" in result.output.lower()
        assert output.exists()

    def test_list_shifts_default_config_absent_still_friendly(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No -c given at all, and the default doesn't exist => the
        friendly 'No configuration file found' message, not an error."""
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(cli, ["list-shifts"])

        assert result.exit_code == 0, result.output
        assert "no configuration file found" in result.output.lower()


class TestWorkerAttributesEndToEnd:
    """CSV `attributes` column -> Worker.attributes -> `skills` constraint,
    exercised through the actual `generate` CLI command (defect 2)."""

    def test_generate_with_attributes_assigns_only_qualified_worker(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
shift_types:
  - id: icu_shift
    name: ICU Shift
    category: day
    start_time: "07:00"
    end_time: "15:00"
    duration_hours: 8.0
    workers_required: 1
    required_attributes:
      certification: icu
"""
        )

        workers_csv = tmp_path / "workers.csv"
        workers_csv.write_text(
            "id,name,attributes\n"
            "W001,Alice,certification=icu;seniority=senior\n"
            "W002,Bob,\n"
        )

        output = tmp_path / "sched.json"
        result = runner.invoke(
            cli,
            [
                "-c", str(config_file),
                "generate",
                "--start-date", "2026-06-01",
                "--end-date", "2026-06-07",
                "--output", str(output),
                "--workers", str(workers_csv),
                "--quick-solve",
            ],
        )

        assert result.exit_code == 0, result.output

        with open(output) as f:
            data = json.load(f)

        assigned_worker_ids = {
            worker_id
            for period in data["periods"]
            for worker_id, shifts in period["assignments"].items()
            if shifts
        }
        assert assigned_worker_ids == {"W001"}


class TestShiftTypeFromConfig:
    """Unit tests for the shift_type_from_config helper (defect E): config
    ShiftTypes must carry required_attributes/applicable_days through,
    rather than silently dropping them like the old ad-hoc call sites did.
    """

    def test_carries_required_attributes_and_applicable_days(self) -> None:
        from shift_solver.cli.helpers import shift_type_from_config
        from shift_solver.config.schema import ShiftTypeConfig

        st_config = ShiftTypeConfig(
            id="icu",
            name="ICU Shift",
            category="day",
            start_time="07:00",
            end_time="15:00",
            duration_hours=8.0,
            workers_required=2,
            required_attributes={"certification": "ICU"},
            applicable_days=[0, 1, 2, 3, 4],
        )

        shift_type = shift_type_from_config(st_config)

        assert shift_type.required_attributes == {"certification": "ICU"}
        assert shift_type.applicable_days == frozenset({0, 1, 2, 3, 4})

    def test_defaults_stay_empty_and_none(self) -> None:
        from shift_solver.cli.helpers import shift_type_from_config
        from shift_solver.config.schema import ShiftTypeConfig

        st_config = ShiftTypeConfig(
            id="day",
            name="Day Shift",
            category="day",
            start_time="09:00",
            end_time="17:00",
            duration_hours=8.0,
        )

        shift_type = shift_type_from_config(st_config)

        assert shift_type.applicable_days is None
        assert shift_type.required_attributes == {}
