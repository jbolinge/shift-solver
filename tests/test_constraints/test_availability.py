"""Tests for availability constraint."""

from datetime import date, time, timedelta

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.availability import AvailabilityConstraint
from shift_solver.models import Worker, ShiftType, Availability
from shift_solver.solver import VariableBuilder


class TestAvailabilityConstraint:
    """Tests for AvailabilityConstraint."""

    @pytest.fixture
    def model(self) -> cp_model.CpModel:
        """Create a fresh CP model."""
        return cp_model.CpModel()

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

    def test_unavailable_prevents_all_assignments(
        self,
        model: cp_model.CpModel,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Unavailable worker cannot be assigned to any shift in that period."""
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # W001 unavailable in period 1
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                availability_type="unavailable",
            ),
        ]

        constraint = AvailabilityConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # W001 should not be assigned in period 1
        for st in shift_types:
            assert solver.Value(variables.get_assignment_var("W001", 1, st.id)) == 0

    def test_unavailable_allows_other_periods(
        self,
        model: cp_model.CpModel,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Unavailable worker can still work in other periods."""
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # W001 unavailable in period 1 only
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                availability_type="unavailable",
            ),
        ]

        constraint = AvailabilityConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        # Force W001 to work in period 0 (should be allowed)
        model.add(variables.get_assignment_var("W001", 0, "day") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        assert solver.Value(variables.get_assignment_var("W001", 0, "day")) == 1

    def test_unavailable_shift_specific(
        self,
        model: cp_model.CpModel,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Shift-specific unavailability only blocks that shift type."""
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # W001 unavailable for night shifts only in period 1
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                availability_type="unavailable",
                shift_type_id="night",
            ),
        ]

        constraint = AvailabilityConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        # Force W001 to work day shift in period 1 (should be allowed)
        model.add(variables.get_assignment_var("W001", 1, "day") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        # Day shift allowed
        assert solver.Value(variables.get_assignment_var("W001", 1, "day")) == 1
        # Night shift blocked
        assert solver.Value(variables.get_assignment_var("W001", 1, "night")) == 0

    def test_multiple_unavailable_periods(
        self,
        model: cp_model.CpModel,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Worker can be unavailable in multiple periods."""
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # W001 unavailable in periods 0 and 2
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                availability_type="unavailable",
            ),
            Availability(
                worker_id="W001",
                start_date=period_dates[2][0],
                end_date=period_dates[2][1],
                availability_type="unavailable",
            ),
        ]

        constraint = AvailabilityConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Check W001 blocked in periods 0 and 2
        for period in [0, 2]:
            for st in shift_types:
                assert solver.Value(variables.get_assignment_var("W001", period, st.id)) == 0

    def test_availability_infeasible_when_no_workers(
        self,
        model: cp_model.CpModel,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Infeasible when all workers unavailable but shift needs coverage."""
        workers = [Worker(id="W001", name="Only Worker")]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        # Only worker unavailable
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                availability_type="unavailable",
            ),
        ]

        # Add coverage requiring 1 worker
        from shift_solver.constraints.coverage import CoverageConstraint

        coverage = CoverageConstraint(model, variables)
        coverage.apply(workers=workers, shift_types=shift_types[:1], num_periods=1)

        # Add availability constraint
        constraint = AvailabilityConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types[:1],
            num_periods=1,
            availabilities=availabilities,
            period_dates=[period_dates[0]],
        )

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.INFEASIBLE

    def test_availability_disabled(
        self,
        model: cp_model.CpModel,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Disabled availability allows all assignments."""
        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                availability_type="unavailable",
            ),
        ]

        config = ConstraintConfig(enabled=False)
        constraint = AvailabilityConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            availabilities=availabilities,
            period_dates=[period_dates[0]],
        )

        # Force W001 to work (should be allowed since disabled)
        model.add(variables.get_assignment_var("W001", 0, "day") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]


class TestAvailabilityConstraintEdgeCases:
    """Edge case tests for AvailabilityConstraint."""

    def test_no_availabilities(self) -> None:
        """Works when no availability records exist."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Alice")]
        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="any",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = AvailabilityConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            availabilities=[],
            period_dates=[(date(2026, 1, 5), date(2026, 1, 11))],
        )

        assert constraint.constraint_count == 0

    def test_availability_spanning_multiple_periods(self) -> None:
        """Availability can span multiple scheduling periods."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Alice"), Worker(id="W002", name="Bob")]
        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="any",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        base = date(2026, 1, 5)
        period_dates = [
            (base + timedelta(weeks=i), base + timedelta(weeks=i, days=6))
            for i in range(4)
        ]

        # Unavailability spans periods 1 and 2
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[2][1],
                availability_type="unavailable",
            ),
        ]

        constraint = AvailabilityConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # W001 blocked in periods 1 and 2
        assert solver.Value(variables.get_assignment_var("W001", 1, "shift")) == 0
        assert solver.Value(variables.get_assignment_var("W001", 2, "shift")) == 0

        # But allowed in periods 0 and 3
        # (May or may not be assigned depending on solver choice)

    def test_availability_for_nonexistent_worker(self) -> None:
        """Availability for non-existent worker is ignored."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Alice")]
        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="any",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        # Availability for worker that doesn't exist
        availabilities = [
            Availability(
                worker_id="NONEXISTENT",
                start_date=date(2026, 1, 5),
                end_date=date(2026, 1, 11),
                availability_type="unavailable",
            ),
        ]

        constraint = AvailabilityConstraint(model, variables)
        # Should not raise
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            availabilities=availabilities,
            period_dates=[(date(2026, 1, 5), date(2026, 1, 11))],
        )

        assert constraint.constraint_count == 0
