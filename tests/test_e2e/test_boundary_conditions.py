"""E2E tests for boundary conditions.

scheduler-47: Tests extreme input boundaries including single worker/period
scenarios, maximum capacity, and edge case validation.
"""

from datetime import date, time, timedelta

import pytest

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import ShiftType, Worker
from shift_solver.solver import ShiftSolver

from .conftest import create_period_dates, solve_and_verify


@pytest.mark.e2e
class TestSingleWorkerScenarios:
    """Tests for scenarios with minimal workers."""

    def test_single_worker_single_shift_single_period(self, worker_factory) -> None:
        """Absolute minimum: 1 worker, 1 shift, 1 period."""
        workers = [worker_factory()]

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

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success
        assert len(result.schedule.periods) == 1
        assert len(result.schedule.workers) == 1
        # Single worker must be assigned to the single shift
        period = result.schedule.periods[0]
        assert workers[0].id in period.assignments
        assert len(period.assignments[workers[0].id]) == 1

    def test_single_worker_multiple_shifts(self, worker_factory) -> None:
        """Single worker with multiple shift types."""
        workers = [worker_factory()]

        shift_types = [
            ShiftType(
                id="shift_a",
                name="Shift A",
                category="day",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="shift_b",
                name="Shift B",
                category="evening",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success
        # Single worker must work both shifts
        period = result.schedule.periods[0]
        assert workers[0].id in period.assignments
        assert len(period.assignments[workers[0].id]) == 2

    def test_single_worker_multiple_periods(self, worker_factory) -> None:
        """Single worker across multiple periods."""
        workers = [worker_factory()]

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

        periods = create_period_dates(num_periods=4)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success
        assert len(result.schedule.periods) == 4
        # Worker must be assigned in all periods
        for period in result.schedule.periods:
            assert workers[0].id in period.assignments


@pytest.mark.e2e
class TestSinglePeriodScheduling:
    """Tests for single period scenarios."""

    def test_single_period_multiple_workers(self, worker_factory) -> None:
        """Multiple workers, single period."""
        workers = [worker_factory() for _ in range(10)]

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

        periods = create_period_dates(num_periods=1)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success
        assert len(result.schedule.periods) == 1

        # Verify coverage met
        period = result.schedule.periods[0]
        day_count = sum(
            1
            for shifts in period.assignments.values()
            for s in shifts
            if s.shift_type_id == "day"
        )
        night_count = sum(
            1
            for shifts in period.assignments.values()
            for s in shifts
            if s.shift_type_id == "night"
        )
        assert day_count >= 3
        assert night_count >= 2

    def test_single_period_with_all_constraints(self, worker_factory) -> None:
        """Single period with all constraints enabled."""
        workers = [worker_factory() for _ in range(8)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "availability": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "frequency": ConstraintConfig(enabled=True, is_hard=False, weight=50),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
        )

        assert result.success


@pytest.mark.e2e
class TestMaximumCapacity:
    """Tests for maximum capacity scenarios."""

    def test_n_workers_n_shifts_requiring_one_each(self, worker_factory) -> None:
        """N workers, N shifts each requiring exactly 1 worker."""
        n = 5
        workers = [worker_factory() for _ in range(n)]

        shift_types = [
            ShiftType(
                id=f"shift_{i}",
                name=f"Shift {i}",
                category="day",
                start_time=time(6 + i * 2, 0),
                end_time=time(14 + i * 2, 0),
                duration_hours=8.0,
                workers_required=1,
            )
            for i in range(n)
        ]

        periods = create_period_dates(num_periods=1)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success
        # Each worker should have exactly one shift
        period = result.schedule.periods[0]
        total_assignments = sum(len(shifts) for shifts in period.assignments.values())
        assert total_assignments == n

    def test_all_workers_all_shifts_full_coverage(self, worker_factory) -> None:
        """All workers needed for all shifts (tight fit)."""
        workers = [worker_factory() for _ in range(6)]

        # 3 shifts * 2 required = 6 total slots = 6 workers
        shift_types = [
            ShiftType(
                id="shift_a",
                name="Shift A",
                category="a",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="shift_b",
                name="Shift B",
                category="b",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="shift_c",
                name="Shift C",
                category="c",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success
        period = result.schedule.periods[0]
        total = sum(len(shifts) for shifts in period.assignments.values())
        assert total == 6


@pytest.mark.e2e
class TestEmptySchedule:
    """Tests for shifts with zero workers required."""

    def test_shifts_with_zero_workers_required(self, worker_factory) -> None:
        """Shift types with workers_required=0."""
        workers = [worker_factory() for _ in range(5)]

        shift_types = [
            ShiftType(
                id="empty",
                name="Empty Shift",
                category="empty",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=0,
            ),
            ShiftType(
                id="normal",
                name="Normal Shift",
                category="day",
                start_time=time(17, 0),
                end_time=time(1, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        periods = create_period_dates(num_periods=2)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success

    def test_all_shifts_zero_required(self, worker_factory) -> None:
        """All shift types have workers_required=0."""
        workers = [worker_factory() for _ in range(3)]

        shift_types = [
            ShiftType(
                id="empty_a",
                name="Empty A",
                category="a",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=0,
            ),
            ShiftType(
                id="empty_b",
                name="Empty B",
                category="b",
                start_time=time(17, 0),
                end_time=time(1, 0),
                duration_hours=8.0,
                workers_required=0,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        # Should succeed with empty assignments
        assert result.success


@pytest.mark.e2e
class TestMaximumPeriodCount:
    """Tests for maximum period count scenarios."""

    @pytest.mark.slow
    def test_52_periods_one_year(self, worker_factory) -> None:
        """52 weekly periods (one full year)."""
        workers = [worker_factory() for _ in range(15)]

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
        ]

        periods = create_period_dates(
            start_date=date(2026, 1, 5),
            num_periods=52,
        )

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            time_limit_seconds=180,
        )

        assert result.success
        assert len(result.schedule.periods) == 52

    def test_26_periods_half_year(self, worker_factory) -> None:
        """26 weekly periods (half year)."""
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

        periods = create_period_dates(num_periods=26)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            time_limit_seconds=120,
        )

        assert result.success
        assert len(result.schedule.periods) == 26


@pytest.mark.e2e
class TestZeroWorkersEdgeCase:
    """Tests for zero workers scenarios."""

    def test_zero_workers_raises_error(self) -> None:
        """Zero workers should raise ValueError."""
        workers: list[Worker] = []

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

        with pytest.raises(ValueError, match="workers"):
            ShiftSolver(
                workers=workers,
                shift_types=shift_types,
                period_dates=periods,
                schedule_id="ZERO-WORKERS",
            )

    def test_empty_shift_types_raises_error(self, worker_factory) -> None:
        """Empty shift_types should raise ValueError."""
        workers = [worker_factory() for _ in range(3)]
        shift_types: list[ShiftType] = []

        periods = create_period_dates(num_periods=1)

        with pytest.raises(ValueError, match="shift_types"):
            ShiftSolver(
                workers=workers,
                shift_types=shift_types,
                period_dates=periods,
                schedule_id="EMPTY-SHIFTS",
            )

    def test_empty_periods_raises_error(self, worker_factory) -> None:
        """Empty period_dates should raise ValueError."""
        workers = [worker_factory() for _ in range(3)]

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

        periods: list[tuple[date, date]] = []

        with pytest.raises(ValueError, match="period_dates"):
            ShiftSolver(
                workers=workers,
                shift_types=shift_types,
                period_dates=periods,
                schedule_id="EMPTY-PERIODS",
            )


@pytest.mark.e2e
class TestExtremeRatios:
    """Tests for extreme worker/shift/period ratios."""

    def test_many_workers_few_slots(self, worker_factory) -> None:
        """Many workers competing for few slots."""
        workers = [worker_factory() for _ in range(50)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,  # Only 2 needed
            ),
        ]

        periods = create_period_dates(num_periods=1)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success

    def test_few_workers_many_shifts(self, worker_factory) -> None:
        """Few workers covering many shift types."""
        workers = [worker_factory() for _ in range(10)]

        # 10 shift types, each requiring 1 worker
        shift_types = [
            ShiftType(
                id=f"shift_{i}",
                name=f"Shift {i}",
                category="day",
                start_time=time(6 + i, 0),
                end_time=time(14 + i, 0),
                duration_hours=8.0,
                workers_required=1,
            )
            for i in range(10)
        ]

        periods = create_period_dates(num_periods=1)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success
