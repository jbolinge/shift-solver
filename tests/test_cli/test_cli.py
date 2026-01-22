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


class TestInitDbCommand:
    """Tests for init-db command."""

    def test_init_db_creates_database(self, runner: CliRunner, tmp_path: Path) -> None:
        """init-db creates a SQLite database file."""
        db_path = tmp_path / "test.db"
        result = runner.invoke(cli, ["init-db", "--db", str(db_path)])

        assert result.exit_code == 0
        assert db_path.exists()
        assert "initialized" in result.output.lower() or "created" in result.output.lower()


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
    """Tests for list commands (placeholders for now)."""

    def test_list_workers(self, runner: CliRunner) -> None:
        """list-workers command exists."""
        result = runner.invoke(cli, ["list-workers", "--help"])
        assert result.exit_code == 0

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
