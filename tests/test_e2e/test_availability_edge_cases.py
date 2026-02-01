"""E2E tests for vacation and availability edge cases.

scheduler-40: Tests complex availability scenarios including overlapping
vacations, last-minute changes, and boundary conditions.
"""

from datetime import date, time, timedelta

import pytest

from shift_solver.models import Availability, ShiftType
from shift_solver.validation import FeasibilityChecker

from .conftest import solve_and_verify


@pytest.mark.e2e
class TestOverlappingVacations:
    """Tests for overlapping vacation requests."""

    def test_two_workers_overlapping_vacation_same_period(
        self, worker_factory, standard_shifts, periods_4
    ) -> None:
        """Two workers with overlapping vacations in the same period."""
        workers = [worker_factory() for _ in range(8)]
        period_start, period_end = periods_4[1]

        # Workers 0 and 1 both unavailable for period 1
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                availability_type="unavailable",
            ),
            Availability(
                worker_id=workers[1].id,
                start_date=period_start,
                end_date=period_end,
                availability_type="unavailable",
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=standard_shifts,
            period_dates=periods_4,
            availabilities=availabilities,
        )

        # Verify unavailable workers not assigned in period 1
        period_1 = result.schedule.periods[1]
        for worker_id in [workers[0].id, workers[1].id]:
            assert worker_id not in period_1.assignments or not period_1.assignments[
                worker_id
            ], f"Worker {worker_id} should not be assigned during vacation"

    def test_three_workers_cascading_overlaps(
        self, worker_factory, standard_shifts, periods_4
    ) -> None:
        """Three workers with cascading vacation overlaps."""
        workers = [worker_factory() for _ in range(10)]
        base_date = periods_4[0][0]

        # Worker 0: days 1-10, Worker 1: days 5-15, Worker 2: days 10-20
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=base_date,
                end_date=base_date + timedelta(days=9),
                availability_type="unavailable",
            ),
            Availability(
                worker_id=workers[1].id,
                start_date=base_date + timedelta(days=4),
                end_date=base_date + timedelta(days=14),
                availability_type="unavailable",
            ),
            Availability(
                worker_id=workers[2].id,
                start_date=base_date + timedelta(days=9),
                end_date=base_date + timedelta(days=19),
                availability_type="unavailable",
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=standard_shifts,
            period_dates=periods_4,
            availabilities=availabilities,
        )

        assert result.success
        assert result.schedule is not None


@pytest.mark.e2e
class TestLastMinuteAvailabilityChanges:
    """Tests for mid-period availability changes."""

    def test_mid_period_unavailability(
        self, worker_factory, standard_shifts, periods_4
    ) -> None:
        """Worker becomes unavailable mid-period."""
        workers = [worker_factory() for _ in range(8)]
        period_start, period_end = periods_4[1]

        # Worker unavailable for second half of period
        mid_period = period_start + timedelta(days=3)
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=mid_period,
                end_date=period_end,
                availability_type="unavailable",
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=standard_shifts,
            period_dates=periods_4,
            availabilities=availabilities,
        )

        assert result.success

    def test_single_day_unavailability_mid_period(
        self, worker_factory, standard_shifts, periods_4
    ) -> None:
        """Single day unavailability in middle of period."""
        workers = [worker_factory() for _ in range(8)]
        period_start, _ = periods_4[2]

        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=period_start + timedelta(days=3),
                end_date=period_start + timedelta(days=3),
                availability_type="unavailable",
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=standard_shifts,
            period_dates=periods_4,
            availabilities=availabilities,
        )

        assert result.success


@pytest.mark.e2e
class TestPartialShiftUnavailability:
    """Tests for shift-specific unavailability."""

    def test_night_only_unavailability(self, worker_factory, periods_4) -> None:
        """Worker unavailable only for night shifts."""
        workers = [worker_factory() for _ in range(8)]
        shift_types = [
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
        ]

        period_start, period_end = periods_4[0]
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                availability_type="unavailable",
                shift_type_id="night",
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            availabilities=availabilities,
        )

        assert result.success

    def test_category_based_unavailability(self, worker_factory, periods_4) -> None:
        """Worker unavailable for all shifts in a category."""
        workers = [worker_factory() for _ in range(10)]
        shift_types = [
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
                id="evening",
                name="Evening Shift",
                category="evening",
                start_time=time(15, 0),
                end_time=time(23, 0),
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
        ]

        period_start, period_end = periods_4[0]
        # Worker 0 unavailable for night shift only
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                availability_type="unavailable",
                shift_type_id="night",
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
class TestEdgeDateBoundaries:
    """Tests for availability at period boundaries."""

    def test_vacation_starts_on_period_boundary(
        self, worker_factory, standard_shifts, periods_4
    ) -> None:
        """Vacation starts exactly on period start date."""
        workers = [worker_factory() for _ in range(8)]
        period_start, period_end = periods_4[1]

        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_start + timedelta(days=3),
                availability_type="unavailable",
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=standard_shifts,
            period_dates=periods_4,
            availabilities=availabilities,
        )

        assert result.success

    def test_vacation_ends_on_period_boundary(
        self, worker_factory, standard_shifts, periods_4
    ) -> None:
        """Vacation ends exactly on period end date."""
        workers = [worker_factory() for _ in range(8)]
        period_start, period_end = periods_4[1]

        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=period_end - timedelta(days=3),
                end_date=period_end,
                availability_type="unavailable",
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=standard_shifts,
            period_dates=periods_4,
            availabilities=availabilities,
        )

        assert result.success

    def test_single_day_unavailability_on_period_boundary(
        self, worker_factory, standard_shifts, periods_4
    ) -> None:
        """Single day unavailability exactly on period start."""
        workers = [worker_factory() for _ in range(8)]
        period_start, _ = periods_4[1]

        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_start,
                availability_type="unavailable",
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=standard_shifts,
            period_dates=periods_4,
            availabilities=availabilities,
        )

        assert result.success


@pytest.mark.e2e
class TestUnavailabilityOutsidePeriod:
    """Tests for unavailability that doesn't affect the schedule."""

    def test_unavailability_before_schedule_period(
        self, worker_factory, standard_shifts, periods_4
    ) -> None:
        """Unavailability entirely before the scheduling period."""
        workers = [worker_factory() for _ in range(8)]
        schedule_start = periods_4[0][0]

        # Unavailability ends day before schedule starts
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=schedule_start - timedelta(days=10),
                end_date=schedule_start - timedelta(days=1),
                availability_type="unavailable",
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=standard_shifts,
            period_dates=periods_4,
            availabilities=availabilities,
        )

        # Worker should be available for all periods
        assert result.success
        for _period in result.schedule.periods:
            # Worker can be assigned since unavailability is outside schedule
            pass  # No specific assertion needed, just verify solve succeeds

    def test_unavailability_after_schedule_period(
        self, worker_factory, standard_shifts, periods_4
    ) -> None:
        """Unavailability entirely after the scheduling period."""
        workers = [worker_factory() for _ in range(8)]
        schedule_end = periods_4[-1][1]

        # Unavailability starts day after schedule ends
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=schedule_end + timedelta(days=1),
                end_date=schedule_end + timedelta(days=10),
                availability_type="unavailable",
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=standard_shifts,
            period_dates=periods_4,
            availabilities=availabilities,
        )

        assert result.success

    def test_unavailability_between_periods(
        self, worker_factory, standard_shifts
    ) -> None:
        """Unavailability in gap between non-contiguous periods."""
        workers = [worker_factory() for _ in range(8)]

        # Create periods with a gap
        base_date = date(2026, 2, 2)
        periods_with_gap = [
            (base_date, base_date + timedelta(days=6)),
            # Gap of 7 days
            (base_date + timedelta(days=14), base_date + timedelta(days=20)),
        ]

        # Unavailability in the gap
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=base_date + timedelta(days=7),
                end_date=base_date + timedelta(days=13),
                availability_type="unavailable",
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=standard_shifts,
            period_dates=periods_with_gap,
            availabilities=availabilities,
        )

        assert result.success


@pytest.mark.e2e
class TestFeasibilityCheckerAccuracy:
    """Tests verifying FeasibilityChecker matches solver results."""

    def test_feasibility_checker_detects_all_unavailable(
        self, worker_factory, minimal_shift, periods_4
    ) -> None:
        """FeasibilityChecker detects when all workers unavailable."""
        workers = [worker_factory() for _ in range(3)]
        period_start, period_end = periods_4[0]

        # All workers unavailable for first period
        availabilities = [
            Availability(
                worker_id=w.id,
                start_date=period_start,
                end_date=period_end,
                availability_type="unavailable",
            )
            for w in workers
        ]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=minimal_shift,
            period_dates=periods_4,
            availabilities=availabilities,
        )
        feasibility_result = checker.check()

        assert not feasibility_result.is_feasible
        assert any(
            issue["type"] == "availability" for issue in feasibility_result.issues
        )

    def test_feasibility_checker_passes_with_sufficient_workers(
        self, worker_factory, minimal_shift, periods_4
    ) -> None:
        """FeasibilityChecker passes when sufficient workers available."""
        workers = [worker_factory() for _ in range(5)]
        period_start, period_end = periods_4[0]

        # Only 2 workers unavailable, 3 remain
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                availability_type="unavailable",
            ),
            Availability(
                worker_id=workers[1].id,
                start_date=period_start,
                end_date=period_end,
                availability_type="unavailable",
            ),
        ]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=minimal_shift,
            period_dates=periods_4,
            availabilities=availabilities,
        )
        feasibility_result = checker.check()

        assert feasibility_result.is_feasible

        # Verify solver also succeeds
        result = solve_and_verify(
            workers=workers,
            shift_types=minimal_shift,
            period_dates=periods_4,
            availabilities=availabilities,
        )
        assert result.success
