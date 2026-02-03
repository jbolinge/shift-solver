"""Integration tests for post-solve validation.

Tests that solutions from the solver satisfy all constraints and
that validation correctly reports any issues.
"""

from datetime import date, time

import pytest

from factories import create_period_dates
from shift_solver.models import (
    Availability,
    SchedulingRequest,
    ShiftType,
    Worker,
)
from shift_solver.solver import ShiftSolver
from shift_solver.validation import ScheduleValidator


@pytest.mark.integration
class TestSolverSolutionValidation:
    """Test that solver solutions pass validation."""

    def test_basic_solution_validates(self) -> None:
        """Basic solution should pass all validation checks."""
        workers = [Worker(id=f"W{i:02d}", name=f"Worker {i}") for i in range(1, 6)]
        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]
        period_dates = create_period_dates(num_periods=2)

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="VALID-TEST",
        )

        result = solver.solve(time_limit_seconds=30)
        assert result.success

        validator = ScheduleValidator(schedule=result.schedule)
        validation = validator.validate()

        assert validation.is_valid
        assert len(validation.violations) == 0

    def test_solution_with_restrictions_validates(self) -> None:
        """Solution with worker restrictions should validate."""
        workers = [
            Worker(id="W1", name="Alice"),
            Worker(id="W2", name="Bob", restricted_shifts=frozenset(["night"])),
            Worker(id="W3", name="Charlie"),
            Worker(id="W4", name="Diana", restricted_shifts=frozenset(["night"])),
        ]
        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
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
        ]
        period_dates = create_period_dates(num_periods=2)

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="RESTRICT-TEST",
        )

        result = solver.solve(time_limit_seconds=30)
        assert result.success

        validator = ScheduleValidator(schedule=result.schedule)
        validation = validator.validate()

        assert validation.is_valid

        # Verify no restricted workers on night shift
        for period in result.schedule.periods:
            for worker_id, shifts in period.assignments.items():
                worker = next(w for w in workers if w.id == worker_id)
                for shift in shifts:
                    assert shift.shift_type_id not in worker.restricted_shifts

    def test_solution_with_availability_validates(self) -> None:
        """Solution respects availability constraints."""
        workers = [Worker(id=f"W{i}", name=f"Worker {i}") for i in range(1, 5)]
        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        base_date = date(2026, 2, 2)
        period_dates = create_period_dates(start_date=base_date, num_periods=2)

        # W1 unavailable for first period
        availabilities = [
            Availability(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                availability_type="unavailable",
            ),
        ]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="AVAIL-TEST",
            availabilities=availabilities,
        )

        result = solver.solve(time_limit_seconds=30)
        assert result.success

        validator = ScheduleValidator(
            schedule=result.schedule,
            availabilities=availabilities,
        )
        validation = validator.validate()

        assert validation.is_valid

        # Verify W1 not assigned during first period
        first_period = result.schedule.periods[0]
        assert "W1" not in first_period.assignments


@pytest.mark.integration
class TestHardConstraintValidation:
    """Test hard constraint validation in solutions."""

    def test_coverage_requirement_met(self) -> None:
        """Coverage requirements should be met in solution."""
        workers = [Worker(id=f"W{i}", name=f"Worker {i}") for i in range(1, 8)]
        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,  # Need 3 workers
            ),
        ]
        period_dates = create_period_dates(num_periods=2)

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="COVERAGE-TEST",
        )

        result = solver.solve(time_limit_seconds=30)
        assert result.success

        # Verify coverage in each period
        for period in result.schedule.periods:
            day_count = 0
            for _worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    if shift.shift_type_id == "day":
                        day_count += 1

            assert day_count >= 3, f"Period {period.period_index} has insufficient coverage"


@pytest.mark.integration
class TestSoftConstraintValidation:
    """Test soft constraint validation and statistics."""

    def test_request_tracking_in_solution(self) -> None:
        """Request fulfillment should be tracked in statistics."""
        workers = [Worker(id=f"W{i}", name=f"Worker {i}") for i in range(1, 6)]
        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
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
        ]
        base_date = date(2026, 2, 2)
        period_dates = create_period_dates(start_date=base_date, num_periods=2)

        # W1 prefers day shift
        requests = [
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="positive",
                shift_type_id="day",
            ),
        ]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="REQUEST-TEST",
            requests=requests,
        )

        result = solver.solve(time_limit_seconds=30)
        assert result.success

        validator = ScheduleValidator(
            schedule=result.schedule,
            requests=requests,
        )
        validation = validator.validate()

        assert "request_fulfillment" in validation.statistics

    def test_fairness_metrics_in_solution(self) -> None:
        """Fairness metrics should be computed for solution."""
        workers = [Worker(id=f"W{i}", name=f"Worker {i}") for i in range(1, 8)]
        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]
        period_dates = create_period_dates(num_periods=4)

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="FAIRNESS-TEST",
        )

        result = solver.solve(time_limit_seconds=30)
        assert result.success

        validator = ScheduleValidator(schedule=result.schedule)
        validation = validator.validate()

        assert "fairness" in validation.statistics
        assert "assignments_per_worker" in validation.statistics


@pytest.mark.integration
class TestSolutionExtraction:
    """Test solution extraction and schedule building."""

    def test_all_periods_have_assignments(self) -> None:
        """All periods should have assignment data."""
        workers = [Worker(id=f"W{i}", name=f"Worker {i}") for i in range(1, 5)]
        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        num_periods = 4
        period_dates = create_period_dates(num_periods=num_periods)

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="PERIODS-TEST",
        )

        result = solver.solve(time_limit_seconds=30)
        assert result.success
        assert result.schedule is not None

        # Verify all periods exist
        assert len(result.schedule.periods) == num_periods

        # Verify each period has assignments
        for i, period in enumerate(result.schedule.periods):
            assert period.period_index == i
            assert len(period.assignments) > 0

    def test_shift_instances_have_correct_data(self) -> None:
        """Shift instances should have correct worker and date info."""
        workers = [Worker(id="W1", name="Alice"), Worker(id="W2", name="Bob")]
        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        base_date = date(2026, 2, 2)
        period_dates = create_period_dates(start_date=base_date, num_periods=1)

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="SHIFT-DATA-TEST",
        )

        result = solver.solve(time_limit_seconds=30)
        assert result.success

        for period in result.schedule.periods:
            for worker_id, shifts in period.assignments.items():
                # Worker ID should be valid
                assert worker_id in ["W1", "W2"]

                for shift in shifts:
                    # Shift should have correct fields
                    assert shift.shift_type_id == "day"
                    assert shift.worker_id == worker_id
                    assert shift.period_index == period.period_index
                    # Date should be within period
                    assert period.period_start <= shift.date <= period.period_end


@pytest.mark.integration
class TestEdgeCaseValidation:
    """Test validation edge cases."""

    def test_minimal_scenario_validates(self) -> None:
        """Minimal scenario (1 worker, 1 shift, 1 period) validates."""
        workers = [Worker(id="W1", name="Solo Worker")]
        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="any",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        period_dates = create_period_dates(num_periods=1)

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="MINIMAL-TEST",
        )

        result = solver.solve(time_limit_seconds=30)
        assert result.success

        validator = ScheduleValidator(schedule=result.schedule)
        validation = validator.validate()

        assert validation.is_valid

    def test_statistics_match_actual_solution(self) -> None:
        """Computed statistics should match actual solution data."""
        workers = [Worker(id=f"W{i}", name=f"Worker {i}") for i in range(1, 5)]
        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]
        period_dates = create_period_dates(num_periods=2)

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="STATS-TEST",
        )

        result = solver.solve(time_limit_seconds=30)
        assert result.success

        validator = ScheduleValidator(schedule=result.schedule)
        validation = validator.validate()

        # Count actual assignments
        actual_total = 0
        for period in result.schedule.periods:
            for _worker_id, shifts in period.assignments.items():
                actual_total += len(shifts)

        # Compare with reported statistics
        assert validation.statistics["total_assignments"] == actual_total
