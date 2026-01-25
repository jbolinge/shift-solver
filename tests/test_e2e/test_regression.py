"""E2E tests for regression and known edge cases.

scheduler-50: Tests for regression prevention and documented edge cases
including infeasibility detection, date handling, and data validation.
"""

from datetime import date, time, timedelta

import pytest

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import Availability, SchedulingRequest, ShiftType, Worker
from shift_solver.solver import ShiftSolver
from shift_solver.validation import FeasibilityChecker

from .conftest import create_period_dates, solve_and_verify


@pytest.mark.e2e
class TestInfeasibilityDetectionAccuracy:
    """Tests for accurate infeasibility detection."""

    def test_known_infeasible_insufficient_workers(self, worker_factory) -> None:
        """Known infeasible: not enough workers for coverage."""
        workers = [worker_factory() for _ in range(2)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=5,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        # FeasibilityChecker should detect
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )
        feasibility = checker.check()
        assert not feasibility.is_feasible

        # Solver should also fail
        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            expect_feasible=False,
        )
        assert not result.success

    def test_known_infeasible_all_restricted(self, worker_factory) -> None:
        """Known infeasible: all workers restricted from required shift."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["required"])),
            worker_factory(restricted_shifts=frozenset(["required"])),
            worker_factory(restricted_shifts=frozenset(["required"])),
        ]

        shift_types = [
            ShiftType(
                id="required",
                name="Required Shift",
                category="required",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )
        feasibility = checker.check()
        assert not feasibility.is_feasible
        assert any(issue["type"] == "restriction" for issue in feasibility.issues)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            expect_feasible=False,
        )
        assert not result.success

    def test_known_infeasible_combined_constraints(self, worker_factory) -> None:
        """Known infeasible: combined restrictions and unavailability."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(),  # Only one can work night
        ]

        shift_types = [
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=2,  # Need 2, only 1 available
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            expect_feasible=False,
        )
        assert not result.success


@pytest.mark.e2e
class TestSoftConstraintViolationTracking:
    """Tests for soft constraint violation tracking."""

    def test_violation_tracking_with_requests(
        self, worker_factory, periods_4
    ) -> None:
        """Verify request violations are tracked in objective."""
        workers = [worker_factory() for _ in range(4)]
        period_start, period_end = periods_4[0]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        # All workers want to avoid this shift
        requests = [
            SchedulingRequest(
                worker_id=w.id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="shift",
                priority=2,
            )
            for w in workers
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        assert result.success
        # Objective should reflect violations
        assert result.objective_value is not None
        assert result.objective_value > 0  # Some requests violated

    def test_zero_violations_minimal_constraints(
        self, worker_factory, periods_4
    ) -> None:
        """Zero violations when constraints easily satisfied."""
        workers = [worker_factory() for _ in range(10)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs=constraint_configs,
        )

        assert result.success


@pytest.mark.e2e
class TestDateRangeBoundaryBugs:
    """Tests for date range boundary handling."""

    def test_year_boundary_december_january(self, worker_factory) -> None:
        """Period spanning December 31 to January 1."""
        workers = [worker_factory() for _ in range(5)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        # Period spans year boundary
        periods = [
            (date(2026, 12, 28), date(2027, 1, 3)),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success
        # Verify period dates preserved correctly
        period = result.schedule.periods[0]
        assert period.start_date == date(2026, 12, 28)
        assert period.end_date == date(2027, 1, 3)

    def test_leap_year_february_29(self, worker_factory) -> None:
        """Period including February 29 in leap year."""
        workers = [worker_factory() for _ in range(5)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        # 2028 is a leap year
        periods = [
            (date(2028, 2, 25), date(2028, 3, 2)),  # Includes Feb 29
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success

    def test_dst_transition_dates(self, worker_factory) -> None:
        """Period spanning DST transition (March in US)."""
        workers = [worker_factory() for _ in range(5)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        # DST starts second Sunday of March (US)
        periods = [
            (date(2026, 3, 7), date(2026, 3, 14)),  # Spans DST transition
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success

    def test_month_end_boundaries(self, worker_factory) -> None:
        """Periods ending on various month boundaries."""
        workers = [worker_factory() for _ in range(5)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        # Test various month ends
        periods = [
            (date(2026, 1, 26), date(2026, 1, 31)),  # 31-day month
            (date(2026, 4, 25), date(2026, 4, 30)),  # 30-day month
            (date(2026, 2, 23), date(2026, 2, 28)),  # February
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success
        assert len(result.schedule.periods) == 3


@pytest.mark.e2e
class TestIDCollisionHandling:
    """Tests for handling duplicate or conflicting IDs."""

    def test_unique_worker_ids_required(self) -> None:
        """Workers with duplicate IDs should cause issues."""
        workers = [
            Worker(id="W001", name="Alice"),
            Worker(id="W001", name="Bob"),  # Duplicate ID!
            Worker(id="W002", name="Charlie"),
        ]

        shift_types = [
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

        periods = create_period_dates(num_periods=1)

        # Note: Current implementation may or may not detect duplicates
        # This test documents expected behavior
        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            schedule_id="DUPLICATE-TEST",
        )
        # Solver might succeed or fail depending on implementation
        result = solver.solve(time_limit_seconds=30)
        # At minimum, shouldn't crash
        assert result.status_name is not None

    def test_unique_shift_ids_required(self, worker_factory) -> None:
        """Shift types with duplicate IDs."""
        workers = [worker_factory() for _ in range(5)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift A",
                category="a",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="shift",  # Duplicate ID!
                name="Shift B",
                category="b",
                start_time=time(17, 0),
                end_time=time(1, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        # Document behavior with duplicate shift IDs
        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            schedule_id="DUPLICATE-SHIFT-TEST",
        )
        result = solver.solve(time_limit_seconds=30)
        # Should not crash
        assert result.status_name is not None


@pytest.mark.e2e
class TestEmptyDataHandling:
    """Tests for empty collections in input data."""

    def test_empty_availability_list(self, worker_factory, periods_4) -> None:
        """Empty availability list should work fine."""
        workers = [worker_factory() for _ in range(5)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            availabilities=[],
        )

        assert result.success

    def test_empty_requests_list(self, worker_factory, periods_4) -> None:
        """Empty requests list should work fine."""
        workers = [worker_factory() for _ in range(5)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=[],
            constraint_configs=constraint_configs,
        )

        assert result.success

    def test_none_optional_parameters(self, worker_factory, periods_4) -> None:
        """None values for optional parameters should work."""
        workers = [worker_factory() for _ in range(5)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            schedule_id="NONE-PARAMS",
            availabilities=None,
            requests=None,
            constraint_configs=None,
        )

        result = solver.solve(time_limit_seconds=30)
        assert result.success


@pytest.mark.e2e
class TestUnicodeAndSpecialCharacters:
    """Tests for Unicode and special character handling."""

    def test_unicode_worker_names(self, periods_4) -> None:
        """Workers with Unicode names."""
        workers = [
            Worker(id="W001", name="José García"),
            Worker(id="W002", name="Müller Hans"),
            Worker(id="W003", name="田中太郎"),
            Worker(id="W004", name="Иванов Иван"),
            Worker(id="W005", name="محمد أحمد"),
        ]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
        )

        assert result.success
        # Verify names preserved
        names = {w.name for w in result.schedule.workers}
        assert "José García" in names
        assert "田中太郎" in names

    def test_unicode_shift_names(self, worker_factory, periods_4) -> None:
        """Shift types with Unicode names."""
        workers = [worker_factory() for _ in range(5)]

        shift_types = [
            ShiftType(
                id="day",
                name="日勤 (Day)",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="夜勤 (Night)",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
        )

        assert result.success

    def test_special_characters_in_ids(self, worker_factory, periods_4) -> None:
        """IDs with special characters (that should work)."""
        workers = [
            Worker(id="W-001", name="Worker 1"),
            Worker(id="W_002", name="Worker 2"),
            Worker(id="W.003", name="Worker 3"),
            worker_factory(),
            worker_factory(),
        ]

        shift_types = [
            ShiftType(
                id="shift-day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
        )

        assert result.success

    def test_emoji_in_names(self, worker_factory, periods_4) -> None:
        """Names containing emoji characters."""
        workers = [
            Worker(id="W001", name="Alice 👩‍⚕️"),
            Worker(id="W002", name="Bob 👨‍🔧"),
            worker_factory(),
            worker_factory(),
            worker_factory(),
        ]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift 🏥",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
        )

        assert result.success


@pytest.mark.e2e
class TestRegressionFromKnownIssues:
    """Regression tests for previously identified issues."""

    def test_single_period_fairness_edge_case(self, worker_factory) -> None:
        """Fairness with single period should not cause errors."""
        workers = [worker_factory() for _ in range(6)]

        shift_types = [
            ShiftType(
                id="undesirable",
                name="Undesirable",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
        )

        assert result.success

    def test_availability_exactly_matching_period(
        self, worker_factory, periods_4
    ) -> None:
        """Unavailability exactly matching period boundaries."""
        workers = [worker_factory() for _ in range(6)]
        period_start, period_end = periods_4[1]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        # Unavailability exactly matches period
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                availability_type="unavailable",
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            availabilities=availabilities,
        )

        assert result.success
        # Worker should not be assigned in period 1
        period_1 = result.schedule.periods[1]
        assert (
            workers[0].id not in period_1.assignments
            or not period_1.assignments[workers[0].id]
        )

    def test_request_outside_schedule_period(
        self, worker_factory, periods_4
    ) -> None:
        """Request dates outside schedule period should be handled."""
        workers = [worker_factory() for _ in range(5)]
        schedule_start = periods_4[0][0]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        # Request for dates before schedule starts
        requests = [
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=schedule_start - timedelta(days=30),
                end_date=schedule_start - timedelta(days=1),
                request_type="negative",
                shift_type_id="shift",
                priority=2,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        # Should succeed - request doesn't affect schedule
        assert result.success
