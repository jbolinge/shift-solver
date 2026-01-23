"""Tests for worker restriction constraint."""

from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.restriction import RestrictionConstraint
from shift_solver.models import Worker, ShiftType
from shift_solver.solver import VariableBuilder


class TestRestrictionConstraint:
    """Tests for RestrictionConstraint."""

    @pytest.fixture
    def model(self) -> cp_model.CpModel:
        """Create a fresh CP model."""
        return cp_model.CpModel()

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

    def test_restriction_prevents_assignment(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """Worker cannot be assigned to restricted shift type."""
        workers = [
            Worker(id="W001", name="Alice", restricted_shifts=frozenset(["night"])),
            Worker(id="W002", name="Bob"),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = RestrictionConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # W001 should never be assigned to night shift
        assert solver.Value(variables.get_assignment_var("W001", 0, "night")) == 0

    def test_restriction_allows_unrestricted_shifts(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """Worker can be assigned to non-restricted shift types."""
        workers = [
            Worker(id="W001", name="Alice", restricted_shifts=frozenset(["night"])),
            Worker(id="W002", name="Bob"),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = RestrictionConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        # Force W001 to work day shift
        model.add(variables.get_assignment_var("W001", 0, "day") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        assert solver.Value(variables.get_assignment_var("W001", 0, "day")) == 1

    def test_restriction_infeasible_when_only_restricted_option(
        self, model: cp_model.CpModel
    ) -> None:
        """Infeasible when worker is only option but restricted."""
        workers = [
            Worker(id="W001", name="Alice", restricted_shifts=frozenset(["night"])),
        ]
        shift_types = [
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=1,  # Need 1 but W001 can't work it
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        # Add coverage constraint requiring 1 worker
        from shift_solver.constraints.coverage import CoverageConstraint

        coverage = CoverageConstraint(model, variables)
        coverage.apply(workers=workers, shift_types=shift_types, num_periods=1)

        # Add restriction constraint
        restriction = RestrictionConstraint(model, variables)
        restriction.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.INFEASIBLE

    def test_restriction_multiple_restricted_shifts(
        self, model: cp_model.CpModel
    ) -> None:
        """Worker can have multiple restricted shifts."""
        workers = [
            Worker(
                id="W001",
                name="Alice",
                restricted_shifts=frozenset(["night", "weekend"]),
            ),
            Worker(id="W002", name="Bob"),
            Worker(id="W003", name="Charlie"),
        ]
        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="weekend",
                name="Weekend",
                category="weekend",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = RestrictionConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # W001 should not be assigned to night or weekend
        assert solver.Value(variables.get_assignment_var("W001", 0, "night")) == 0
        assert solver.Value(variables.get_assignment_var("W001", 0, "weekend")) == 0

    def test_restriction_disabled(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """Disabled restriction allows all assignments."""
        workers = [
            Worker(id="W001", name="Alice", restricted_shifts=frozenset(["night"])),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(enabled=False)
        constraint = RestrictionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        # Force W001 to night (should be allowed since constraint disabled)
        model.add(variables.get_assignment_var("W001", 0, "night") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        assert solver.Value(variables.get_assignment_var("W001", 0, "night")) == 1

    def test_restriction_adds_correct_count(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """Constraint count matches number of restrictions applied."""
        workers = [
            Worker(id="W001", name="Alice", restricted_shifts=frozenset(["night"])),
            Worker(
                id="W002", name="Bob", restricted_shifts=frozenset(["day", "night"])
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=2)
        variables = builder.build()

        constraint = RestrictionConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=2)

        # W001: 1 restricted shift * 2 periods = 2
        # W002: 2 restricted shifts * 2 periods = 4
        # Total: 6
        assert constraint.constraint_count == 6


class TestRestrictionConstraintEdgeCases:
    """Edge case tests for RestrictionConstraint."""

    def test_no_restrictions(self) -> None:
        """Works when no workers have restrictions."""
        model = cp_model.CpModel()
        workers = [
            Worker(id="W001", name="Alice"),
            Worker(id="W002", name="Bob"),
        ]
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

        constraint = RestrictionConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        # No constraints should be added
        assert constraint.constraint_count == 0

    def test_restriction_nonexistent_shift_type(self) -> None:
        """Restriction for non-existent shift type is ignored."""
        model = cp_model.CpModel()
        workers = [
            Worker(
                id="W001",
                name="Alice",
                restricted_shifts=frozenset(["nonexistent"]),
            ),
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
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = RestrictionConstraint(model, variables)
        # Should not raise - restriction for nonexistent shift is simply ignored
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        assert constraint.constraint_count == 0
