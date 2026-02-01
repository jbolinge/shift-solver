"""Shared test fixtures for shift_solver tests."""

from datetime import date, time, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import (
    Availability,
    SchedulingRequest,
    ShiftType,
    Worker,
)

# -----------------------------------------------------------------------------
# Worker Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_workers() -> list[Worker]:
    """Create a basic set of 5 workers."""
    return [
        Worker(id=f"W{i:03d}", name=f"Worker {i}")
        for i in range(1, 6)
    ]


@pytest.fixture
def sample_workers_large() -> list[Worker]:
    """Create a larger set of 15 workers."""
    return [
        Worker(id=f"W{i:03d}", name=f"Worker {i}")
        for i in range(1, 16)
    ]


@pytest.fixture
def sample_workers_with_restrictions() -> list[Worker]:
    """Create workers with shift restrictions."""
    return [
        Worker(id="W001", name="Alice", restricted_shifts=frozenset(["night"])),
        Worker(id="W002", name="Bob", restricted_shifts=frozenset(["weekend"])),
        Worker(id="W003", name="Charlie"),  # No restrictions
        Worker(id="W004", name="Diana", restricted_shifts=frozenset(["night", "weekend"])),
        Worker(id="W005", name="Eve"),  # No restrictions
    ]


@pytest.fixture
def sample_workers_with_types() -> list[Worker]:
    """Create workers with different worker types."""
    return [
        Worker(id="W001", name="Alice", worker_type="full_time"),
        Worker(id="W002", name="Bob", worker_type="full_time"),
        Worker(id="W003", name="Charlie", worker_type="part_time"),
        Worker(id="W004", name="Diana", worker_type="part_time"),
        Worker(id="W005", name="Eve", worker_type="contractor"),
    ]


# -----------------------------------------------------------------------------
# Shift Type Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_shift_types() -> list[ShiftType]:
    """Create a standard set of shift types (day, night, weekend)."""
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
def single_shift_type() -> list[ShiftType]:
    """Create a minimal single shift type for simple tests."""
    return [
        ShiftType(
            id="day",
            name="Day Shift",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            workers_required=1,
        ),
    ]


@pytest.fixture
def healthcare_shift_types() -> list[ShiftType]:
    """Create healthcare-style 12-hour shifts."""
    return [
        ShiftType(
            id="day_12",
            name="Day Shift (12h)",
            category="day",
            start_time=time(7, 0),
            end_time=time(19, 0),
            duration_hours=12.0,
            workers_required=2,
        ),
        ShiftType(
            id="night_12",
            name="Night Shift (12h)",
            category="night",
            start_time=time(19, 0),
            end_time=time(7, 0),
            duration_hours=12.0,
            workers_required=2,
            is_undesirable=True,
        ),
    ]


@pytest.fixture
def warehouse_shift_types() -> list[ShiftType]:
    """Create warehouse 3-shift rotation."""
    return [
        ShiftType(
            id="first",
            name="First Shift",
            category="day",
            start_time=time(6, 0),
            end_time=time(14, 0),
            duration_hours=8.0,
            workers_required=3,
        ),
        ShiftType(
            id="second",
            name="Second Shift",
            category="evening",
            start_time=time(14, 0),
            end_time=time(22, 0),
            duration_hours=8.0,
            workers_required=3,
        ),
        ShiftType(
            id="third",
            name="Third Shift",
            category="night",
            start_time=time(22, 0),
            end_time=time(6, 0),
            duration_hours=8.0,
            workers_required=2,
            is_undesirable=True,
        ),
    ]


# -----------------------------------------------------------------------------
# Period Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_period_dates() -> list[tuple[date, date]]:
    """Create 4 weekly periods starting from a fixed date."""
    base = date(2026, 2, 2)  # A Monday
    return [
        (base + timedelta(weeks=i), base + timedelta(weeks=i, days=6))
        for i in range(4)
    ]


@pytest.fixture
def single_period_dates() -> list[tuple[date, date]]:
    """Create a single weekly period."""
    base = date(2026, 2, 2)  # A Monday
    return [(base, base + timedelta(days=6))]


@pytest.fixture
def period_dates_factory():
    """Factory for creating custom period date ranges."""
    def _create(
        start_date: date = date(2026, 2, 2),
        num_periods: int = 4,
        period_length_days: int = 7,
    ) -> list[tuple[date, date]]:
        periods = []
        current = start_date
        for _ in range(num_periods):
            period_end = current + timedelta(days=period_length_days - 1)
            periods.append((current, period_end))
            current = period_end + timedelta(days=1)
        return periods
    return _create


# -----------------------------------------------------------------------------
# Availability Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_availability(sample_period_dates: list[tuple[date, date]]) -> list[Availability]:
    """Create sample availability records."""
    start_date, end_date = sample_period_dates[0]
    return [
        Availability(
            worker_id="W001",
            start_date=start_date,
            end_date=end_date,
            availability_type="unavailable",
        ),
        Availability(
            worker_id="W002",
            start_date=start_date,
            end_date=start_date + timedelta(days=2),
            availability_type="preferred",
            shift_type_id="day",
        ),
    ]


@pytest.fixture
def full_unavailability(sample_period_dates: list[tuple[date, date]]) -> list[Availability]:
    """Create availability that marks workers unavailable for entire schedule."""
    start_date = sample_period_dates[0][0]
    end_date = sample_period_dates[-1][1]
    return [
        Availability(
            worker_id="W001",
            start_date=start_date,
            end_date=end_date,
            availability_type="unavailable",
        ),
    ]


# -----------------------------------------------------------------------------
# Request Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_requests(sample_period_dates: list[tuple[date, date]]) -> list[SchedulingRequest]:
    """Create sample scheduling requests."""
    start_date, _ = sample_period_dates[0]
    return [
        SchedulingRequest(
            worker_id="W001",
            start_date=start_date,
            end_date=start_date + timedelta(days=6),
            request_type="positive",
            shift_type_id="day",
            priority=2,
        ),
        SchedulingRequest(
            worker_id="W002",
            start_date=start_date,
            end_date=start_date + timedelta(days=6),
            request_type="negative",
            shift_type_id="night",
            priority=1,
        ),
    ]


# -----------------------------------------------------------------------------
# Constraint Config Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def all_constraints_enabled() -> dict[str, ConstraintConfig]:
    """Constraint config with all constraints enabled."""
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
    """Constraint config with only hard constraints enabled."""
    return {
        "coverage": ConstraintConfig(enabled=True, is_hard=True),
        "restriction": ConstraintConfig(enabled=True, is_hard=True),
        "availability": ConstraintConfig(enabled=True, is_hard=True),
        "fairness": ConstraintConfig(enabled=False),
        "frequency": ConstraintConfig(enabled=False),
        "request": ConstraintConfig(enabled=False),
    }


@pytest.fixture
def minimal_constraints() -> dict[str, ConstraintConfig]:
    """Minimal constraint config (coverage only)."""
    return {
        "coverage": ConstraintConfig(enabled=True, is_hard=True),
    }


# -----------------------------------------------------------------------------
# CLI Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def cli_runner() -> CliRunner:
    """Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def isolated_cli_runner() -> CliRunner:
    """Click CLI test runner."""
    return CliRunner()


# -----------------------------------------------------------------------------
# Config File Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_config_yaml(tmp_path: Path) -> Path:
    """Create a temporary valid config YAML file."""
    config_content = """
solver:
  max_time_seconds: 300
  num_workers: 4
  quick_solution_seconds: 30

schedule:
  period_type: week
  num_periods: 4

constraints:
  coverage:
    enabled: true
    is_hard: true
  fairness:
    enabled: true
    is_hard: false
    weight: 100

shift_types:
  - id: day
    name: Day Shift
    category: day
    start_time: "07:00"
    end_time: "15:00"
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

database:
  path: test.db

logging:
  level: WARNING
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def invalid_config_yaml(tmp_path: Path) -> Path:
    """Create a temporary invalid config YAML file."""
    config_content = """
solver:
  max_time_seconds: -1  # Invalid: must be positive

shift_types: []  # Invalid: must have at least one
"""
    config_file = tmp_path / "invalid_config.yaml"
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def malformed_yaml(tmp_path: Path) -> Path:
    """Create a malformed YAML file."""
    config_file = tmp_path / "malformed.yaml"
    config_file.write_text("shift_types:\n  - id: day\n    name: [unclosed")
    return config_file


# -----------------------------------------------------------------------------
# CSV Data Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_workers_csv(tmp_path: Path) -> Path:
    """Create a sample workers CSV file."""
    csv_content = """id,name,worker_type,restricted_shifts,preferred_shifts
W001,Alice Smith,full_time,night,day
W002,Bob Jones,full_time,,
W003,Charlie Brown,part_time,night;weekend,
W004,Diana Ross,contractor,,day;night
W005,Eve Wilson,full_time,,
"""
    csv_file = tmp_path / "workers.csv"
    csv_file.write_text(csv_content)
    return csv_file


@pytest.fixture
def sample_availability_csv(tmp_path: Path) -> Path:
    """Create a sample availability CSV file."""
    csv_content = """worker_id,start_date,end_date,availability_type,shift_type_id
W001,2026-02-02,2026-02-08,unavailable,
W002,2026-02-09,2026-02-15,preferred,day
W003,2026-02-02,2026-02-04,unavailable,night
"""
    csv_file = tmp_path / "availability.csv"
    csv_file.write_text(csv_content)
    return csv_file


@pytest.fixture
def sample_requests_csv(tmp_path: Path) -> Path:
    """Create a sample requests CSV file."""
    csv_content = """worker_id,start_date,end_date,request_type,shift_type_id,priority
W001,2026-02-16,2026-02-22,positive,day,2
W002,2026-02-16,2026-02-22,negative,night,1
W004,2026-02-09,2026-02-15,positive,weekend,3
"""
    csv_file = tmp_path / "requests.csv"
    csv_file.write_text(csv_content)
    return csv_file


# -----------------------------------------------------------------------------
# Temporary Directory Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Create and return a temporary output directory."""
    output = tmp_path / "output"
    output.mkdir()
    return output


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create and return a temporary data directory."""
    data = tmp_path / "data"
    data.mkdir()
    return data


