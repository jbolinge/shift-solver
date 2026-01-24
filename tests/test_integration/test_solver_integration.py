"""Integration tests for the ShiftSolver with multiple constraints."""

import pytest

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import Availability, SchedulingRequest, ShiftType, Worker
from shift_solver.solver import ShiftSolver
from shift_solver.validation import ScheduleValidator
from factories import ScenarioBuilder, create_period_dates


@pytest.mark.integration
class TestSolverWithAllHardConstraints:
    """Test solver with all hard constraints enabled together."""

    def test_solve_with_coverage_restriction_availability(
        self,
        sample_workers_with_restrictions: list[Worker],
        sample_shift_types: list[ShiftType],
        sample_period_dates: list[tuple],
    ) -> None:
        """Test solver respects coverage, restriction, and availability constraints."""
        # Add availability constraint - W003 unavailable for first period
        availabilities = [
            Availability(
                worker_id="W003",
                start_date=sample_period_dates[0][0],
                end_date=sample_period_dates[0][1],
                availability_type="unavailable",
            )
        ]

        solver = ShiftSolver(
            workers=sample_workers_with_restrictions,
            shift_types=sample_shift_types,
            period_dates=sample_period_dates,
            schedule_id="HARD-001",
            availabilities=availabilities,
        )

        result = solver.solve(time_limit_seconds=60)

        assert result.success, f"Solver failed with status: {result.status_name}"
        assert result.schedule is not None

        schedule = result.schedule

        # Verify coverage - each period should have required workers per shift
        for period in schedule.periods:
            for shift_type in sample_shift_types:
                assigned_count = sum(
                    1
                    for shifts in period.assignments.values()
                    for s in shifts
                    if s.shift_type_id == shift_type.id
                )
                assert assigned_count >= shift_type.workers_required, (
                    f"Coverage violation: {shift_type.id} has {assigned_count} workers, "
                    f"requires {shift_type.workers_required}"
                )

        # Verify restrictions - workers should not be on restricted shifts
        for period in schedule.periods:
            for worker_id, shifts in period.assignments.items():
                worker = next(w for w in sample_workers_with_restrictions if w.id == worker_id)
                for shift in shifts:
                    assert shift.shift_type_id not in worker.restricted_shifts, (
                        f"Restriction violation: {worker_id} assigned to {shift.shift_type_id}"
                    )

        # Verify availability - W003 should have no shifts in period 0
        period_0 = schedule.periods[0]
        w003_shifts = period_0.get_worker_shifts("W003")
        assert len(w003_shifts) == 0, "W003 should not be assigned in period 0"

    def test_solve_with_all_constraints_validates(
        self,
        complex_scenario: dict,
    ) -> None:
        """Test that solution with all constraints passes validation."""
        solver = ShiftSolver(**complex_scenario)
        result = solver.solve(time_limit_seconds=60)

        assert result.success
        assert result.schedule is not None

        # Run validation
        validator = ScheduleValidator(
            schedule=result.schedule,
            availabilities=complex_scenario["availabilities"],
            requests=complex_scenario["requests"],
        )
        validation_result = validator.validate()

        assert validation_result.is_valid, f"Violations: {validation_result.violations}"


@pytest.mark.integration
class TestSolverWithSoftConstraints:
    """Test solver optimization with soft constraints."""

    def test_soft_constraints_improve_quality(self) -> None:
        """Test that enabling soft constraints improves schedule quality."""
        # Create scenario with only hard constraints
        hard_only = (
            ScenarioBuilder()
            .with_workers(8)
            .with_shift_types("standard", workers_per_shift=1)
            .with_periods(4)
            .with_constraints("hard_only")
            .with_schedule_id("HARD-ONLY")
            .build()
        )

        # Create same scenario with all constraints
        all_constraints = (
            ScenarioBuilder()
            .with_workers(8)
            .with_shift_types("standard", workers_per_shift=1)
            .with_periods(4)
            .with_constraints("all")
            .with_schedule_id("ALL-CONSTRAINTS")
            .build()
        )

        # Solve both
        hard_solver = ShiftSolver(**hard_only)
        hard_result = hard_solver.solve(time_limit_seconds=30)

        all_solver = ShiftSolver(**all_constraints)
        all_result = all_solver.solve(time_limit_seconds=30)

        assert hard_result.success
        assert all_result.success

        # Both should produce valid schedules
        assert hard_result.schedule is not None
        assert all_result.schedule is not None

    def test_fairness_reduces_shift_spread(self) -> None:
        """Test that fairness constraint reduces variation in undesirable shift counts."""
        # Scenario with undesirable night shifts
        scenario = (
            ScenarioBuilder()
            .with_workers(6)
            .with_shift_types("standard", workers_per_shift=1)
            .with_periods(6)
            .with_constraints(
                "hard_only",
                fairness=ConstraintConfig(enabled=True, is_hard=False, weight=1000),
            )
            .with_schedule_id("FAIRNESS-TEST")
            .build()
        )

        solver = ShiftSolver(**scenario)
        result = solver.solve(time_limit_seconds=60)

        assert result.success
        assert result.schedule is not None

        # Count undesirable shifts per worker
        undesirable_counts: dict[str, int] = {}
        for period in result.schedule.periods:
            for worker_id, shifts in period.assignments.items():
                if worker_id not in undesirable_counts:
                    undesirable_counts[worker_id] = 0
                for shift in shifts:
                    shift_type = next(
                        st for st in scenario["shift_types"] if st.id == shift.shift_type_id
                    )
                    if shift_type.is_undesirable:
                        undesirable_counts[worker_id] += 1

        if undesirable_counts:
            counts = list(undesirable_counts.values())
            spread = max(counts) - min(counts)
            # With fairness, spread should be relatively small
            assert spread <= 3, f"Spread too high: {spread} (counts: {counts})"


@pytest.mark.integration
class TestConstraintConflicts:
    """Test solver behavior with conflicting constraints."""

    def test_conflicting_constraints_finds_balance(self) -> None:
        """Test solver finds balance when constraints conflict."""
        # Worker wants day shift, but availability says unavailable some days
        scenario = (
            ScenarioBuilder()
            .with_workers(5)
            .with_shift_types("standard", workers_per_shift=1)
            .with_periods(4)
            .with_request("W001", "day", "positive", period=0)
            .with_unavailability("W001", period=0)  # Conflicts with request
            .with_constraints("all")
            .with_schedule_id("CONFLICT-TEST")
            .build()
        )

        solver = ShiftSolver(**scenario)
        result = solver.solve(time_limit_seconds=30)

        # Should still find a solution (availability is hard, request is soft)
        assert result.success
        assert result.schedule is not None

        # W001 should not be scheduled in period 0 (hard constraint wins)
        period_0 = result.schedule.periods[0]
        w001_shifts = period_0.get_worker_shifts("W001")
        assert len(w001_shifts) == 0


@pytest.mark.integration
class TestMinimalFeasibleProblems:
    """Test solver with minimal and edge-case problems."""

    def test_minimal_feasible_problem(self) -> None:
        """Test solver with smallest possible feasible problem."""
        scenario = (
            ScenarioBuilder()
            .with_workers(1)
            .with_shift_types([
                ShiftType(
                    id="single",
                    name="Single Shift",
                    category="day",
                    start_time=__import__("datetime").time(9, 0),
                    end_time=__import__("datetime").time(17, 0),
                    duration_hours=8.0,
                    workers_required=1,
                )
            ])
            .with_periods(1)
            .with_schedule_id("MINIMAL")
            .build()
        )

        solver = ShiftSolver(**scenario)
        result = solver.solve(time_limit_seconds=30)

        assert result.success
        assert result.schedule is not None
        assert len(result.schedule.periods) == 1

    def test_barely_feasible_exact_coverage_match(self) -> None:
        """Test scenario where workers exactly match coverage requirements."""
        # 3 workers, 3 shifts each requiring 1 worker = exactly balanced
        from datetime import time

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
                category="day",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="shift_c",
                name="Shift C",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        scenario = (
            ScenarioBuilder()
            .with_workers(3)
            .with_shift_types(shift_types)
            .with_periods(1)
            .with_constraints("minimal")
            .with_schedule_id("BARELY-FEASIBLE")
            .build()
        )

        solver = ShiftSolver(**scenario)
        result = solver.solve(time_limit_seconds=30)

        assert result.success
        assert result.schedule is not None


@pytest.mark.integration
class TestInfeasibleProblems:
    """Test solver behavior with infeasible problems."""

    def test_infeasible_due_to_all_workers_restricted(self) -> None:
        """Test graceful handling when no workers can work a required shift."""
        from datetime import time

        # All workers restricted from the only shift type
        workers = [
            Worker(id="W001", name="Worker 1", restricted_shifts=frozenset(["only_shift"])),
            Worker(id="W002", name="Worker 2", restricted_shifts=frozenset(["only_shift"])),
        ]

        shift_types = [
            ShiftType(
                id="only_shift",
                name="Only Shift",
                category="day",
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
            schedule_id="INFEASIBLE",
        )

        result = solver.solve(time_limit_seconds=30)

        # Should fail to find a solution
        assert not result.success

    def test_infeasible_due_to_insufficient_workers(self) -> None:
        """Test when not enough workers for coverage requirements."""
        from datetime import time

        workers = [Worker(id="W001", name="Worker 1")]

        shift_types = [
            ShiftType(
                id="needs_two",
                name="Needs Two Workers",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,  # But only 1 worker available
            ),
        ]

        period_dates = create_period_dates(num_periods=1)

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="INSUFFICIENT",
        )

        result = solver.solve(time_limit_seconds=30)

        assert not result.success

    def test_infeasible_due_to_all_unavailable(self) -> None:
        """Test when all workers are unavailable."""
        from datetime import time

        workers = [
            Worker(id="W001", name="Worker 1"),
            Worker(id="W002", name="Worker 2"),
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
        ]

        period_dates = create_period_dates(num_periods=1)

        # All workers unavailable
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                availability_type="unavailable",
            ),
            Availability(
                worker_id="W002",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                availability_type="unavailable",
            ),
        ]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="ALL-UNAVAILABLE",
            availabilities=availabilities,
        )

        result = solver.solve(time_limit_seconds=30)

        assert not result.success


@pytest.mark.integration
@pytest.mark.slow
class TestLargeScaleProblems:
    """Test solver with larger scale problems."""

    @pytest.mark.parametrize(
        "num_workers,num_shifts,num_periods",
        [
            (10, 3, 4),
            (15, 4, 8),
            (20, 3, 12),
        ],
    )
    def test_solver_scales(
        self,
        num_workers: int,
        num_shifts: int,
        num_periods: int,
    ) -> None:
        """Test solver handles various problem sizes."""
        from datetime import time

        workers = [Worker(id=f"W{i:03d}", name=f"Worker {i}") for i in range(1, num_workers + 1)]

        shift_types = [
            ShiftType(
                id=f"shift_{i}",
                name=f"Shift {i}",
                category="day" if i == 0 else "other",
                start_time=time(6 + i * 2, 0),
                end_time=time(14 + i * 2, 0),
                duration_hours=8.0,
                workers_required=max(1, num_workers // (num_shifts * 2)),
            )
            for i in range(num_shifts)
        ]

        period_dates = create_period_dates(num_periods=num_periods)

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id=f"SCALE-{num_workers}-{num_shifts}-{num_periods}",
        )

        result = solver.solve(time_limit_seconds=120)

        assert result.success, f"Failed for {num_workers}w/{num_shifts}s/{num_periods}p"
        assert result.schedule is not None
