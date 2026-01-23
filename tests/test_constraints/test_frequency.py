"""Tests for frequency constraint."""

from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.frequency import FrequencyConstraint
from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import Worker, ShiftType
from shift_solver.solver.types import SolverVariables
from shift_solver.solver.variable_builder import VariableBuilder


@pytest.fixture
def workers() -> list[Worker]:
    """Create test workers."""
    return [
        Worker(id="W001", name="Worker 1"),
        Worker(id="W002", name="Worker 2"),
    ]


@pytest.fixture
def shift_types() -> list[ShiftType]:
    """Create shift types."""
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
def model_and_variables(
    workers: list[Worker], shift_types: list[ShiftType]
) -> tuple[cp_model.CpModel, SolverVariables]:
    """Create model and variables for testing."""
    model = cp_model.CpModel()
    builder = VariableBuilder(model, workers, shift_types, num_periods=8)
    variables = builder.build()
    return model, variables


class TestFrequencyConstraintInit:
    """Tests for FrequencyConstraint initialization."""

    def test_init_default_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Test initialization with default config."""
        model, variables = model_and_variables
        constraint = FrequencyConstraint(model, variables)

        assert constraint.constraint_id == "frequency"
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
            weight=500,
            parameters={"max_periods_between": 3, "shift_types": ["night"]},
        )
        constraint = FrequencyConstraint(model, variables, config)

        assert constraint.weight == 500
        assert constraint.config.get_param("max_periods_between") == 3


class TestFrequencyConstraintApply:
    """Tests for FrequencyConstraint.apply()."""

    def test_apply_creates_violation_variables(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that apply creates violation variables for windows."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_between": 3},
        )
        constraint = FrequencyConstraint(model, variables, config)

        constraint.apply(workers=workers, shift_types=shift_types, num_periods=8)

        # Should have violation variables
        assert len(constraint.violation_variables) > 0

    def test_apply_disabled_does_nothing(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that disabled constraint adds no constraints."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=False)
        constraint = FrequencyConstraint(model, variables, config)

        constraint.apply(workers=workers, shift_types=shift_types, num_periods=8)

        assert len(constraint.violation_variables) == 0


class TestFrequencyConstraintSolve:
    """Integration tests that solve with frequency constraint."""

    def test_frequency_enforces_regular_assignments(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that frequency constraint encourages regular assignments."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=8)
        variables = builder.build()

        # Apply frequency constraint with window of 4
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=1000,
            parameters={"max_periods_between": 4},
        )
        constraint = FrequencyConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=8)

        # Add basic coverage (1 worker per shift per period)
        for period in range(8):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Minimize violations
        if constraint.violation_variables:
            total_violations = sum(constraint.violation_variables.values())
            model.minimize(total_violations * constraint.weight)

        # Solve
        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_frequency_with_specific_shift_type(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test frequency constraint limited to specific shift types."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=8)
        variables = builder.build()

        # Only apply to night shifts
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=1000,
            parameters={"max_periods_between": 4, "shift_types": ["night"]},
        )
        constraint = FrequencyConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=8)

        # Add basic coverage
        for period in range(8):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Solve
        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
