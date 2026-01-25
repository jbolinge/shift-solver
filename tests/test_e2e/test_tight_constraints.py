"""E2E tests for tight constraint situations.

scheduler-42: Tests near-feasibility boundary conditions, including barely
feasible scenarios, infeasible detection, and FeasibilityChecker accuracy.
"""

from datetime import date, time, timedelta

import pytest

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import Availability, ShiftType, Worker
from shift_solver.solver import ShiftSolver
from shift_solver.validation import FeasibilityChecker

from .conftest import create_period_dates, solve_and_verify


@pytest.mark.e2e
class TestBarelyFeasible:
    """Tests for scenarios at the feasibility boundary."""

    def test_exactly_enough_workers_for_coverage(self, worker_factory) -> None:
        """Exactly enough workers to meet coverage requirements."""
        # 3 shifts requiring 2 workers each = 6 total needed
        # Provide exactly 6 workers
        workers = [worker_factory() for _ in range(6)]

        shift_types = [
            ShiftType(
                id="shift_a",
                name="Shift A",
                category="day",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="shift_b",
                name="Shift B",
                category="day",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="shift_c",
                name="Shift C",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success
        # Each worker must work exactly one shift
        period = result.schedule.periods[0]
        total_assignments = sum(len(shifts) for shifts in period.assignments.values())
        assert total_assignments == 6

    def test_barely_feasible_with_single_spare(self, worker_factory) -> None:
        """One extra worker beyond minimum required."""
        # Need 4 workers total, provide 5
        workers = [worker_factory() for _ in range(5)]

        shift_types = [
            ShiftType(
                id="shift_a",
                name="Shift A",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="shift_b",
                name="Shift B",
                category="night",
                start_time=time(17, 0),
                end_time=time(1, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success


@pytest.mark.e2e
class TestNearInfeasibleWithSlack:
    """Tests for scenarios just above infeasibility threshold."""

    def test_single_worker_slack_with_restrictions(self, worker_factory) -> None:
        """Single spare worker after accounting for restrictions."""
        # Need 2 workers for night, but 2 are restricted
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(),  # Can work night
            worker_factory(),  # Can work night
            worker_factory(),  # Can work night - the slack
        ]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success

    def test_single_worker_slack_with_availability(
        self, worker_factory, periods_4
    ) -> None:
        """Single spare worker after unavailability."""
        workers = [worker_factory() for _ in range(5)]
        period_start, period_end = periods_4[0]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
        ]

        # 1 worker unavailable, leaving 4 for 3 required = 1 slack
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


@pytest.mark.e2e
class TestHighRestrictionCount:
    """Tests for scenarios with many worker restrictions."""

    def test_fifty_percent_restricted_from_night(self, worker_factory) -> None:
        """Half of workers restricted from night shifts."""
        workers = []
        for i in range(10):
            if i < 5:
                workers.append(
                    worker_factory(restricted_shifts=frozenset(["night"]))
                )
            else:
                workers.append(worker_factory())

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=2)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success

    def test_thirty_percent_restricted_from_weekend(self, worker_factory) -> None:
        """30% of workers restricted from weekend shifts."""
        workers = []
        for i in range(10):
            if i < 3:
                workers.append(
                    worker_factory(restricted_shifts=frozenset(["weekend"]))
                )
            else:
                workers.append(worker_factory())

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="weekend",
                name="Weekend Shift",
                category="weekend",
                start_time=time(8, 0),
                end_time=time(16, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=2)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success

    def test_combined_night_and_weekend_restrictions(self, worker_factory) -> None:
        """Mixed restrictions across night and weekend shifts."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(restricted_shifts=frozenset(["weekend"])),
            worker_factory(restricted_shifts=frozenset(["night", "weekend"])),
            worker_factory(),
            worker_factory(),
            worker_factory(),
            worker_factory(),
            worker_factory(),
        ]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
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

        periods = create_period_dates(num_periods=2)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success


@pytest.mark.e2e
class TestConflictingHardConstraints:
    """Tests for scenarios leading to INFEASIBLE status."""

    def test_insufficient_workers_infeasible(self, worker_factory) -> None:
        """Not enough workers to meet coverage - must be infeasible."""
        workers = [worker_factory() for _ in range(2)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=5,  # Need 5, only have 2
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

    def test_all_workers_restricted_infeasible(self, worker_factory) -> None:
        """All workers restricted from required shift."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["critical"])),
            worker_factory(restricted_shifts=frozenset(["critical"])),
            worker_factory(restricted_shifts=frozenset(["critical"])),
        ]

        shift_types = [
            ShiftType(
                id="critical",
                name="Critical Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
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

    def test_all_workers_unavailable_infeasible(
        self, worker_factory, periods_4
    ) -> None:
        """All workers unavailable for a period."""
        workers = [worker_factory() for _ in range(3)]
        period_start, period_end = periods_4[1]

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

        # All workers unavailable for period 1
        availabilities = [
            Availability(
                worker_id=w.id,
                start_date=period_start,
                end_date=period_end,
                availability_type="unavailable",
            )
            for w in workers
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            availabilities=availabilities,
            expect_feasible=False,
        )

        assert not result.success


@pytest.mark.e2e
class TestFeasibilityBoundaryDetection:
    """Tests for detecting exact feasibility boundaries."""

    def test_binary_search_feasibility_threshold(self, worker_factory) -> None:
        """Find exact threshold where problem becomes infeasible."""
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

        # Test with increasing workers until feasible
        feasible_at = None
        for num_workers in range(1, 8):
            workers = [worker_factory() for _ in range(num_workers)]
            solver = ShiftSolver(
                workers=workers,
                shift_types=shift_types,
                period_dates=periods,
                schedule_id="BOUNDARY-TEST",
            )
            result = solver.solve(time_limit_seconds=30)

            if result.success:
                feasible_at = num_workers
                break

        # Should become feasible at exactly 5 workers
        assert feasible_at == 5

    def test_restriction_threshold_detection(self, worker_factory) -> None:
        """Find threshold where restrictions make problem infeasible."""
        periods = create_period_dates(num_periods=1)

        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        # With 5 workers, need at least 2 unrestricted for night
        for num_restricted in range(6):
            workers = []
            for i in range(5):
                if i < num_restricted:
                    workers.append(
                        worker_factory(restricted_shifts=frozenset(["night"]))
                    )
                else:
                    workers.append(worker_factory())

            solver = ShiftSolver(
                workers=workers,
                shift_types=shift_types,
                period_dates=periods,
                schedule_id="RESTRICTION-BOUNDARY",
            )
            result = solver.solve(time_limit_seconds=30)

            if not result.success:
                # Should fail when 4+ are restricted (leaving only 1 for night)
                assert num_restricted >= 4
                break


@pytest.mark.e2e
class TestFeasibilityCheckerAccuracy:
    """Tests verifying FeasibilityChecker vs actual solver results."""

    def test_checker_agrees_with_solver_feasible(self, worker_factory) -> None:
        """FeasibilityChecker says feasible, solver should succeed."""
        workers = [worker_factory() for _ in range(8)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
        ]

        periods = create_period_dates(num_periods=2)

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )
        feasibility = checker.check()

        assert feasibility.is_feasible

        # Solver should also succeed
        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )
        assert result.success

    def test_checker_agrees_with_solver_infeasible(self, worker_factory) -> None:
        """FeasibilityChecker says infeasible, solver should fail."""
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

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )
        feasibility = checker.check()

        assert not feasibility.is_feasible
        assert len(feasibility.issues) > 0

        # Solver should also fail
        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            expect_feasible=False,
        )
        assert not result.success

    def test_checker_detects_restriction_infeasibility(self, worker_factory) -> None:
        """FeasibilityChecker detects restriction-based infeasibility."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["critical"])),
            worker_factory(restricted_shifts=frozenset(["critical"])),
        ]

        shift_types = [
            ShiftType(
                id="critical",
                name="Critical Shift",
                category="day",
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
        assert any(
            issue["type"] == "restriction" for issue in feasibility.issues
        )

    def test_checker_detects_combined_infeasibility(
        self, worker_factory, periods_4
    ) -> None:
        """FeasibilityChecker detects combined restriction + availability issues."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(),  # Only one can work night
        ]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=2,  # Need 2 but only 1 can work
                is_undesirable=True,
            ),
        ]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
        )
        feasibility = checker.check()

        # Should detect restriction makes night shift unfillable
        assert not feasibility.is_feasible
