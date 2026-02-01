"""Tests for FeasibilityChecker pre-solve validation."""

from datetime import date, time

import pytest

from shift_solver.models import Availability, ShiftType, Worker
from shift_solver.validation.feasibility import FeasibilityChecker, FeasibilityResult


@pytest.fixture
def workers() -> list[Worker]:
    """Sample workers for testing."""
    return [
        Worker(id="W1", name="Alice"),
        Worker(id="W2", name="Bob"),
        Worker(id="W3", name="Charlie"),
    ]


@pytest.fixture
def shift_types() -> list[ShiftType]:
    """Sample shift types for testing."""
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
        ),
    ]


@pytest.fixture
def period_dates() -> list[tuple[date, date]]:
    """Sample period dates."""
    return [
        (date(2026, 1, 1), date(2026, 1, 7)),
        (date(2026, 1, 8), date(2026, 1, 14)),
    ]


class TestFeasibilityResult:
    """Test FeasibilityResult data class."""

    def test_feasible_result(self) -> None:
        """Feasible result has no issues."""
        result = FeasibilityResult(is_feasible=True, issues=[])
        assert result.is_feasible
        assert len(result.issues) == 0

    def test_infeasible_result_with_issues(self) -> None:
        """Infeasible result contains issues."""
        issues = [
            {"type": "coverage", "message": "Not enough workers", "severity": "error"}
        ]
        result = FeasibilityResult(is_feasible=False, issues=issues)
        assert not result.is_feasible
        assert len(result.issues) == 1

    def test_result_with_warnings(self) -> None:
        """Result can contain warnings even if feasible."""
        warnings = [
            {"type": "balance", "message": "Uneven distribution", "severity": "warning"}
        ]
        result = FeasibilityResult(is_feasible=True, issues=[], warnings=warnings)
        assert result.is_feasible
        assert len(result.warnings) == 1


class TestFeasibilityChecker:
    """Test FeasibilityChecker class."""

    def test_checker_creation(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Checker should be created with required data."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        assert checker is not None

    def test_valid_inputs_are_feasible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Valid inputs should be feasible."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()
        assert result.is_feasible


class TestCoverageChecks:
    """Test coverage requirement checks."""

    def test_insufficient_workers_for_coverage(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Should detect when there aren't enough workers."""
        # Only 1 worker but day shift requires 2
        workers = [Worker(id="W1", name="Alice")]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()
        assert not result.is_feasible
        assert any(i["type"] == "coverage" for i in result.issues)

    def test_sufficient_workers_for_coverage(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Should pass when enough workers available."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()
        assert result.is_feasible

    def test_empty_workers_list(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Empty workers list should be infeasible."""
        checker = FeasibilityChecker(
            workers=[],
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()
        assert not result.is_feasible
        assert any(i["type"] == "coverage" for i in result.issues)


class TestAvailabilityChecks:
    """Test availability conflict checks."""

    def test_all_workers_unavailable_same_period(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Should detect when all workers unavailable for a period."""
        # All workers unavailable for first period
        availabilities = [
            Availability(
                worker_id="W1",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
            ),
            Availability(
                worker_id="W2",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
            ),
            Availability(
                worker_id="W3",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
        )
        result = checker.check()
        assert not result.is_feasible
        assert any(i["type"] == "availability" for i in result.issues)

    def test_partial_availability_is_feasible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Should pass when some workers available."""
        # Only one worker unavailable
        availabilities = [
            Availability(
                worker_id="W1",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
        )
        result = checker.check()
        assert result.is_feasible


class TestRestrictionChecks:
    """Test worker restriction checks."""

    def test_all_workers_restricted_from_shift(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Should detect when all workers restricted from a shift type."""
        # All workers restricted from day shift
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["day"])),
            Worker(id="W2", name="Bob", restricted_shifts=frozenset(["day"])),
        ]
        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()
        assert not result.is_feasible
        assert any(i["type"] == "restriction" for i in result.issues)

    def test_some_workers_can_work_shift(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Should pass when at least required workers can work shift."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["day"])),
            Worker(id="W2", name="Bob"),  # No restrictions
            Worker(id="W3", name="Charlie"),  # No restrictions
        ]
        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()
        assert result.is_feasible


class TestDateRangeChecks:
    """Test date range validation."""

    def test_empty_period_dates(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Empty period dates should be infeasible."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=[],
        )
        result = checker.check()
        assert not result.is_feasible
        assert any(i["type"] == "period" for i in result.issues)

    def test_valid_period_dates(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Valid period dates should pass."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()
        assert result.is_feasible


class TestCombinedChecks:
    """Test combined feasibility scenarios."""

    def test_restriction_plus_availability_makes_infeasible(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Combination of restrictions and availability can make infeasible."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["day"])),
            Worker(id="W2", name="Bob"),
            Worker(id="W3", name="Charlie"),
        ]
        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=2,  # Need 2 workers
            ),
        ]
        # W2 and W3 unavailable, only W1 left but restricted
        availabilities = [
            Availability(
                worker_id="W2",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 14),
                availability_type="unavailable",
            ),
            Availability(
                worker_id="W3",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 14),
                availability_type="unavailable",
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
        )
        result = checker.check()
        assert not result.is_feasible


class TestCoverageVsRestrictions:
    """Tests for coverage vs restrictions check (scheduler-53)."""

    def test_all_workers_restricted_from_required_shift(self) -> None:
        """All workers restricted from shift that requires coverage."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["night"])),
            Worker(id="W2", name="Bob", restricted_shifts=frozenset(["night"])),
            Worker(id="W3", name="Charlie", restricted_shifts=frozenset(["night"])),
        ]
        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]
        period_dates = [(date(2026, 1, 1), date(2026, 1, 7))]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()

        assert not result.is_feasible
        assert any(i["type"] == "restriction" for i in result.issues)
        # Check error message is descriptive
        restriction_issue = next(i for i in result.issues if i["type"] == "restriction")
        assert "Night Shift" in restriction_issue["message"]
        assert "0 available" in restriction_issue["message"]
        assert "2 required" in restriction_issue["message"]

    def test_partial_restrictions_sufficient_workers(self) -> None:
        """Some workers restricted but still enough available."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["night"])),
            Worker(id="W2", name="Bob"),
            Worker(id="W3", name="Charlie"),
        ]
        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]
        period_dates = [(date(2026, 1, 1), date(2026, 1, 7))]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()
        assert result.is_feasible

    def test_restrictions_plus_unavailability_combined(self) -> None:
        """Workers restricted and remaining unavailable."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["night"])),
            Worker(id="W2", name="Bob"),
            Worker(id="W3", name="Charlie"),
        ]
        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]
        period_dates = [(date(2026, 1, 1), date(2026, 1, 7))]
        # Bob and Charlie unavailable
        availabilities = [
            Availability(
                worker_id="W2",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
            ),
            Availability(
                worker_id="W3",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
            ),
        ]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
        )
        result = checker.check()

        assert not result.is_feasible
        # Should get combined issue
        assert any(i["type"] == "combined" for i in result.issues)
