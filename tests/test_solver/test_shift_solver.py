"""Tests for ShiftSolver - main orchestrator for shift scheduling."""

from datetime import date, time, timedelta

import pytest

from shift_solver.models import Worker, ShiftType, Availability, Schedule
from shift_solver.solver.shift_solver import ShiftSolver, SolverResult


class TestShiftSolver:
    """Tests for ShiftSolver."""

    @pytest.fixture
    def workers(self) -> list[Worker]:
        """Create sample workers."""
        return [
            Worker(id="W001", name="Alice"),
            Worker(id="W002", name="Bob"),
            Worker(id="W003", name="Charlie"),
        ]

    @pytest.fixture
    def shift_types(self) -> list[ShiftType]:
        """Create sample shift types."""
        return [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
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

    @pytest.fixture
    def period_dates(self) -> list[tuple[date, date]]:
        """Create period date ranges (4 weekly periods)."""
        base = date(2026, 1, 5)  # Monday
        return [
            (base + timedelta(weeks=i), base + timedelta(weeks=i, days=6))
            for i in range(4)
        ]

    def test_solve_finds_solution(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """ShiftSolver finds a valid solution."""
        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-001",
        )

        result = solver.solve(time_limit_seconds=30)

        assert result.success
        assert result.schedule is not None

    def test_solve_returns_schedule(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Solution includes a valid Schedule."""
        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-001",
        )

        result = solver.solve(time_limit_seconds=30)

        assert isinstance(result.schedule, Schedule)
        assert result.schedule.schedule_id == "TEST-001"
        assert len(result.schedule.periods) == 4

    def test_solve_respects_coverage(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Solution satisfies coverage requirements."""
        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-001",
        )

        result = solver.solve(time_limit_seconds=30)

        assert result.success
        schedule = result.schedule
        assert schedule is not None

        # Each period should have required coverage
        for period in schedule.periods:
            day_count = len(period.get_shifts_by_type("day"))
            night_count = len(period.get_shifts_by_type("night"))
            assert day_count >= 1  # At least 1 day shift assigned
            assert night_count >= 1  # At least 1 night shift assigned

    def test_solve_respects_restrictions(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Solution respects worker restrictions."""
        workers = [
            Worker(id="W001", name="Alice", restricted_shifts=frozenset(["night"])),
            Worker(id="W002", name="Bob"),
            Worker(id="W003", name="Charlie"),
        ]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-001",
        )

        result = solver.solve(time_limit_seconds=30)

        assert result.success
        schedule = result.schedule
        assert schedule is not None

        # W001 should never be assigned to night shift
        for period in schedule.periods:
            w001_shifts = period.get_worker_shifts("W001")
            for shift in w001_shifts:
                assert shift.shift_type_id != "night"

    def test_solve_respects_availability(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Solution respects availability constraints."""
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                availability_type="unavailable",
            ),
        ]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
            schedule_id="TEST-001",
        )

        result = solver.solve(time_limit_seconds=30)

        assert result.success
        schedule = result.schedule
        assert schedule is not None

        # W001 should not be assigned in period 1
        w001_shifts = schedule.periods[1].get_worker_shifts("W001")
        assert len(w001_shifts) == 0

    def test_solve_returns_statistics(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Result includes solve statistics."""
        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-001",
        )

        result = solver.solve(time_limit_seconds=30)

        assert result.solve_time_seconds >= 0
        assert result.status_name is not None

    def test_solve_infeasible_returns_failure(self) -> None:
        """Infeasible problem returns success=False."""
        # Only 1 worker but need 2 for coverage
        workers = [Worker(id="W001", name="Solo")]
        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="any",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
                workers_required=2,  # Need 2 but only 1 available
            ),
        ]
        period_dates = [(date(2026, 1, 5), date(2026, 1, 11))]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-INFEASIBLE",
        )

        result = solver.solve(time_limit_seconds=10)

        assert not result.success
        assert result.schedule is None


class TestShiftSolverValidation:
    """Validation tests for ShiftSolver."""

    def test_requires_workers(self) -> None:
        """Raises ValueError for empty workers."""
        shift_types = [
            ShiftType(
                id="s",
                name="S",
                category="x",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        with pytest.raises(ValueError, match="workers"):
            ShiftSolver(
                workers=[],
                shift_types=shift_types,
                period_dates=[(date(2026, 1, 5), date(2026, 1, 11))],
                schedule_id="TEST",
            )

    def test_requires_shift_types(self) -> None:
        """Raises ValueError for empty shift types."""
        workers = [Worker(id="W001", name="A")]

        with pytest.raises(ValueError, match="shift_types"):
            ShiftSolver(
                workers=workers,
                shift_types=[],
                period_dates=[(date(2026, 1, 5), date(2026, 1, 11))],
                schedule_id="TEST",
            )

    def test_requires_period_dates(self) -> None:
        """Raises ValueError for empty period dates."""
        workers = [Worker(id="W001", name="A")]
        shift_types = [
            ShiftType(
                id="s",
                name="S",
                category="x",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        with pytest.raises(ValueError, match="period_dates"):
            ShiftSolver(
                workers=workers,
                shift_types=shift_types,
                period_dates=[],
                schedule_id="TEST",
            )


class TestShiftSolverLargerScale:
    """Tests with larger problem sizes."""

    def test_solve_10_workers_4_shifts_8_periods(self) -> None:
        """Solves problem with 10 workers, 4 shift types, 8 periods."""
        workers = [Worker(id=f"W{i:03d}", name=f"Worker {i}") for i in range(10)]
        shift_types = [
            ShiftType(
                id="morning",
                name="Morning",
                category="day",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="afternoon",
                name="Afternoon",
                category="day",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
            ShiftType(
                id="weekend",
                name="Weekend",
                category="weekend",
                start_time=time(8, 0),
                end_time=time(20, 0),
                duration_hours=12.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        base = date(2026, 1, 5)
        period_dates = [
            (base + timedelta(weeks=i), base + timedelta(weeks=i, days=6))
            for i in range(8)
        ]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="LARGE-TEST",
        )

        result = solver.solve(time_limit_seconds=60)

        assert result.success
        assert result.schedule is not None
        assert len(result.schedule.periods) == 8
