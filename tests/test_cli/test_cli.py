"""Tests for CLI commands."""

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
