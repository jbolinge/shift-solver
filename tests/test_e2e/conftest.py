"""End-to-end test fixtures and configuration."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from shift_solver.cli import cli


@pytest.fixture
def e2e_runner() -> CliRunner:
    """CLI runner for E2E tests."""
    return CliRunner()


@pytest.fixture
def e2e_workspace(tmp_path: Path) -> Path:
    """Create a workspace directory structure for E2E tests."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "data").mkdir()
    (workspace / "output").mkdir()
    (workspace / "config").mkdir()
    return workspace


@pytest.fixture
def sample_config_file(e2e_workspace: Path) -> Path:
    """Create a sample config file for E2E tests."""
    config_content = """
solver:
  max_time_seconds: 120
  num_workers: 4
  quick_solution_seconds: 30

schedule:
  period_type: week
  num_periods: 4

constraints:
  coverage:
    enabled: true
    is_hard: true
  restriction:
    enabled: true
    is_hard: true
  availability:
    enabled: true
    is_hard: true
  fairness:
    enabled: true
    is_hard: false
    weight: 100

shift_types:
  - id: morning
    name: Morning Shift
    category: day
    start_time: "06:00"
    end_time: "14:00"
    duration_hours: 8.0
    workers_required: 2
  - id: afternoon
    name: Afternoon Shift
    category: day
    start_time: "14:00"
    end_time: "22:00"
    duration_hours: 8.0
    workers_required: 2
  - id: night
    name: Night Shift
    category: night
    start_time: "22:00"
    end_time: "06:00"
    duration_hours: 8.0
    workers_required: 1
    is_undesirable: true

database:
  path: shift_solver.db

logging:
  level: WARNING
"""
    config_file = e2e_workspace / "config" / "config.yaml"
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def cli_with_config(e2e_runner: CliRunner, sample_config_file: Path):
    """Helper to run CLI commands with config file."""
    def run(*args: str, **kwargs) -> object:
        full_args = ["--config", str(sample_config_file)] + list(args)
        return e2e_runner.invoke(cli, full_args, **kwargs)
    return run
