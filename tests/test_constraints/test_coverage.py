"""Tests for coverage constraint."""

from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.coverage import CoverageConstraint
from shift_solver.models import Worker, ShiftType
from shift_solver.solver import VariableBuilder


class TestCoverageConstraint:
    """Tests for CoverageConstraint."""

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
            Worker(id="W004", name="Diana"),
        ]

    @pytest.fixture
    def shift_types(self) -> list[ShiftType]:
        """Create sample shift types with different worker requirements."""
        return [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=2,  # Needs 2 workers
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=1,  # Needs 1 worker
            ),
        ]

    @pytest.fixture
    def variables(
        self, model: cp_model.CpModel, workers: list[Worker], shift_types: list[ShiftType]
    ):
        """Build solver variables."""
        builder = VariableBuilder(model, workers, shift_types, num_periods=2)
        return builder.build()

    def test_coverage_constraint_applies(
        self,
        model: cp_model.CpModel,
        variables,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Coverage constraint can be applied to model."""
        constraint = CoverageConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=2)

        assert constraint.constraint_count > 0

    def test_coverage_enforces_workers_required(
        self,
        model: cp_model.CpModel,
        variables,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Coverage constraint enforces workers_required for each shift type."""
        constraint = CoverageConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=2)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        # Should find a solution
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Check each period
        for period in range(2):
            # Day shift should have exactly 2 workers
            day_count = sum(
                solver.Value(variables.get_assignment_var(w.id, period, "day"))
                for w in workers
            )
            assert day_count == 2, f"Day shift in period {period} should have 2 workers"

            # Night shift should have exactly 1 worker
            night_count = sum(
                solver.Value(variables.get_assignment_var(w.id, period, "night"))
                for w in workers
            )
            assert night_count == 1, f"Night shift in period {period} should have 1 worker"

    def test_coverage_infeasible_when_not_enough_workers(
        self, model: cp_model.CpModel
    ) -> None:
        """Coverage becomes infeasible when not enough workers."""
        # Only 1 worker but day shift needs 2
        workers = [Worker(id="W001", name="Solo")]
        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,  # Needs 2 but only 1 available
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = CoverageConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.INFEASIBLE

    def test_coverage_disabled_constraint(
        self,
        model: cp_model.CpModel,
        variables,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Disabled coverage constraint doesn't add constraints."""
        config = ConstraintConfig(enabled=False)
        constraint = CoverageConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=2)

        assert constraint.constraint_count == 0

    def test_coverage_with_single_worker_shift(self, model: cp_model.CpModel) -> None:
        """Works with shifts requiring exactly 1 worker."""
        workers = [Worker(id="W001", name="A"), Worker(id="W002", name="B")]
        shift_types = [
            ShiftType(
                id="solo",
                name="Solo",
                category="any",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=3)
        variables = builder.build()

        constraint = CoverageConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Each period should have exactly 1 worker on the shift
        for period in range(3):
            count = sum(
                solver.Value(variables.get_assignment_var(w.id, period, "solo"))
                for w in workers
            )
            assert count == 1


class TestCoverageConstraintEdgeCases:
    """Edge case tests for CoverageConstraint."""

    def test_many_workers_for_few_slots(self) -> None:
        """Works when many workers compete for few slots."""
        model = cp_model.CpModel()
        workers = [Worker(id=f"W{i:03d}", name=f"Worker{i}") for i in range(10)]
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

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = CoverageConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Exactly 2 workers should be assigned
        count = sum(
            solver.Value(variables.get_assignment_var(w.id, 0, "shift"))
            for w in workers
        )
        assert count == 2

    def test_multiple_shift_types_same_period(self) -> None:
        """Coverage works with multiple shift types in same period."""
        model = cp_model.CpModel()
        workers = [Worker(id=f"W{i:03d}", name=f"Worker{i}") for i in range(5)]
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
                id="evening",
                name="Evening",
                category="day",
                start_time=time(14, 0),
                end_time=time(22, 0),
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
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = CoverageConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Verify each shift type has correct coverage
        morning_count = sum(
            solver.Value(variables.get_assignment_var(w.id, 0, "morning"))
            for w in workers
        )
        assert morning_count == 2

        evening_count = sum(
            solver.Value(variables.get_assignment_var(w.id, 0, "evening"))
            for w in workers
        )
        assert evening_count == 1

        night_count = sum(
            solver.Value(variables.get_assignment_var(w.id, 0, "night"))
            for w in workers
        )
        assert night_count == 1
