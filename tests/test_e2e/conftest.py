"""End-to-end test fixtures and configuration."""

from datetime import date, time, timedelta
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from shift_solver.cli import cli
from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import Availability, SchedulingRequest, ShiftType, Worker
from shift_solver.solver import ShiftSolver

# -----------------------------------------------------------------------------
# Pytest Markers
# -----------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")
    config.addinivalue_line("markers", "slow: mark test as slow (>30s)")


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def create_period_dates(
    start_date: date = date(2026, 2, 2),
    num_periods: int = 4,
    period_length_days: int = 7,
) -> list[tuple[date, date]]:
    """Create a list of period date ranges."""
    periods = []
    current = start_date
    for _ in range(num_periods):
        period_end = current + timedelta(days=period_length_days - 1)
        periods.append((current, period_end))
        current = period_end + timedelta(days=1)
    return periods


def solve_and_verify(
    workers: list[Worker],
    shift_types: list[ShiftType],
    period_dates: list[tuple[date, date]],
    availabilities: list[Availability] | None = None,
    requests: list[SchedulingRequest] | None = None,
    constraint_configs: dict[str, ConstraintConfig] | None = None,
    schedule_id: str = "TEST",
    time_limit_seconds: int = 60,
    expect_feasible: bool = True,
) -> Any:
    """Helper to solve and optionally verify feasibility."""
    solver = ShiftSolver(
        workers=workers,
        shift_types=shift_types,
        period_dates=period_dates,
        schedule_id=schedule_id,
        availabilities=availabilities or [],
        requests=requests or [],
        constraint_configs=constraint_configs,
    )
    result = solver.solve(time_limit_seconds=time_limit_seconds)

    if expect_feasible:
        assert result.success, f"Expected feasible but got: {result.status_name}"
    else:
        assert not result.success, f"Expected infeasible but got: {result.status_name}"

    return result


# -----------------------------------------------------------------------------
# Worker Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def worker_factory():
    """Factory for creating workers with auto-incrementing IDs."""
    counter = [0]

    def create(
        id: str | None = None,
        name: str | None = None,
        restricted_shifts: frozenset[str] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Worker:
        counter[0] += 1
        return Worker(
            id=id or f"W{counter[0]:03d}",
            name=name or f"Worker {counter[0]}",
            restricted_shifts=restricted_shifts or frozenset(),
            attributes=attributes or {},
        )

    return create


@pytest.fixture
def workers_10(worker_factory) -> list[Worker]:
    """Create 10 workers."""
    return [worker_factory() for _ in range(10)]


@pytest.fixture
def workers_20(worker_factory) -> list[Worker]:
    """Create 20 workers."""
    return [worker_factory() for _ in range(20)]


# -----------------------------------------------------------------------------
# Shift Type Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def standard_shifts() -> list[ShiftType]:
    """Standard day/night/weekend shift types."""
    return [
        ShiftType(
            id="day",
            name="Day Shift",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=2,
        ),
        ShiftType(
            id="night",
            name="Night Shift",
            category="night",
            start_time=time(23, 0),
            end_time=time(7, 0),
            duration_hours=8.0,
            workers_required=1,
            is_undesirable=True,
        ),
        ShiftType(
            id="weekend",
            name="Weekend Shift",
            category="weekend",
            start_time=time(8, 0),
            end_time=time(16, 0),
            duration_hours=8.0,
            workers_required=1,
            is_undesirable=True,
        ),
    ]


@pytest.fixture
def minimal_shift() -> list[ShiftType]:
    """Single shift type requiring 1 worker."""
    return [
        ShiftType(
            id="shift",
            name="Shift",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            workers_required=1,
        ),
    ]


# -----------------------------------------------------------------------------
# Period Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def periods_4() -> list[tuple[date, date]]:
    """4 weekly periods starting Feb 2, 2026."""
    return create_period_dates(num_periods=4)


@pytest.fixture
def periods_12() -> list[tuple[date, date]]:
    """12 weekly periods (quarterly)."""
    return create_period_dates(num_periods=12)


# -----------------------------------------------------------------------------
# Constraint Config Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def all_constraints() -> dict[str, ConstraintConfig]:
    """All constraints enabled with default weights."""
    return {
        "coverage": ConstraintConfig(enabled=True, is_hard=True),
        "restriction": ConstraintConfig(enabled=True, is_hard=True),
        "availability": ConstraintConfig(enabled=True, is_hard=True),
        "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        "frequency": ConstraintConfig(enabled=True, is_hard=False, weight=50),
        "request": ConstraintConfig(enabled=True, is_hard=False, weight=75),
    }


@pytest.fixture
def hard_constraints_only() -> dict[str, ConstraintConfig]:
    """Only hard constraints enabled."""
    return {
        "coverage": ConstraintConfig(enabled=True, is_hard=True),
        "restriction": ConstraintConfig(enabled=True, is_hard=True),
        "availability": ConstraintConfig(enabled=True, is_hard=True),
    }


# -----------------------------------------------------------------------------
# CLI Fixtures
# -----------------------------------------------------------------------------


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
