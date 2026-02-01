"""Tests for fairness constraint."""

from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.fairness import FairnessConstraint
from shift_solver.models import ShiftType, Worker
from shift_solver.solver.types import SolverVariables
from shift_solver.solver.variable_builder import VariableBuilder


@pytest.fixture
def workers() -> list[Worker]:
    """Create test workers."""
    return [
        Worker(id="W001", name="Worker 1"),
        Worker(id="W002", name="Worker 2"),
        Worker(id="W003", name="Worker 3"),
    ]


@pytest.fixture
def shift_types() -> list[ShiftType]:
    """Create shift types including undesirable ones."""
    return [
        ShiftType(
            id="day",
            name="Day Shift",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=1,
            is_undesirable=False,
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


@pytest.fixture
def model_and_variables(
    workers: list[Worker], shift_types: list[ShiftType]
) -> tuple[cp_model.CpModel, SolverVariables]:
    """Create model and variables for testing."""
    model = cp_model.CpModel()
    builder = VariableBuilder(model, workers, shift_types, num_periods=4)
    variables = builder.build()
    return model, variables


class TestFairnessConstraintInit:
    """Tests for FairnessConstraint initialization."""

    def test_init_default_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Test initialization with default config uses BaseConstraint defaults."""
        model, variables = model_and_variables
        constraint = FairnessConstraint(model, variables)

        assert constraint.constraint_id == "fairness"
        # BaseConstraint defaults: enabled=True, is_hard=True, weight=100
        assert constraint.is_enabled
        assert constraint.is_hard
        assert constraint.weight == 100

    def test_init_soft_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Test initialization with explicit soft config."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        constraint = FairnessConstraint(model, variables, config)

        assert constraint.constraint_id == "fairness"
        assert constraint.is_enabled
        assert not constraint.is_hard
        assert constraint.weight == 100

    def test_init_with_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Test initialization with custom config."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=1000,
            parameters={"categories": ["night", "weekend"]},
        )
        constraint = FairnessConstraint(model, variables, config)

        assert constraint.weight == 1000
        assert constraint.config.get_param("categories") == ["night", "weekend"]


class TestFairnessConstraintApply:
    """Tests for FairnessConstraint.apply()."""

    def test_apply_creates_fairness_variables(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that apply creates max_undesirable and spread variables."""
        model, variables = model_and_variables
        constraint = FairnessConstraint(model, variables)

        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Should have violation variables for the spread
        assert len(constraint.violation_variables) > 0
        assert "spread" in constraint.violation_variables

    def test_apply_disabled_does_nothing(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that disabled constraint adds no constraints."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=False)
        constraint = FairnessConstraint(model, variables, config)

        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0

    def test_apply_with_category_filter(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that category filter limits which shifts are considered."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=500,
            parameters={"categories": ["night"]},
        )
        constraint = FairnessConstraint(model, variables, config)

        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Should still create spread variable
        assert "spread" in constraint.violation_variables


class TestFairnessConstraintSolve:
    """Integration tests that solve with fairness constraint."""

    def test_fairness_minimizes_spread(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that fairness constraint results in even distribution."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # Apply fairness constraint
        config = ConstraintConfig(enabled=True, is_hard=False, weight=1000)
        constraint = FairnessConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Add basic coverage constraint (1 worker per shift per period)
        for period in range(4):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Set objective to minimize spread
        if constraint.violation_variables:
            spread_var = constraint.violation_variables["spread"]
            model.minimize(spread_var * constraint.weight)

        # Solve
        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # Check undesirable distribution
        undesirable_counts = []
        for worker in workers:
            count = solver.value(variables.get_undesirable_total_var(worker.id))
            undesirable_counts.append(count)

        # With fairness, spread should be minimized
        spread = max(undesirable_counts) - min(undesirable_counts)
        assert spread <= 2  # Allow small spread due to integer constraints

    def test_without_fairness_allows_uneven_distribution(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that without fairness, distribution can be uneven."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # Only add coverage constraint, no fairness
        for period in range(4):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Solve without objective (will find any feasible solution)
        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        # Distribution may or may not be even - just checking it solves
