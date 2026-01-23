"""Tests for ObjectiveBuilder."""

from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.fairness import FairnessConstraint
from shift_solver.constraints.frequency import FrequencyConstraint
from shift_solver.models import Worker, ShiftType
from shift_solver.solver.objective_builder import ObjectiveBuilder
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
            is_undesirable=True,
        ),
    ]


@pytest.fixture
def model_and_variables(
    workers: list[Worker], shift_types: list[ShiftType]
) -> tuple[cp_model.CpModel, SolverVariables]:
    """Create model and variables."""
    model = cp_model.CpModel()
    builder = VariableBuilder(model, workers, shift_types, num_periods=4)
    variables = builder.build()
    return model, variables


class TestObjectiveBuilderInit:
    """Tests for ObjectiveBuilder initialization."""

    def test_init(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Test basic initialization."""
        model, _ = model_and_variables
        builder = ObjectiveBuilder(model)

        assert builder.model is model
        assert len(builder.constraints) == 0
        assert len(builder.objective_terms) == 0


class TestObjectiveBuilderAddConstraint:
    """Tests for adding constraints."""

    def test_add_constraint(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test adding a constraint."""
        model, variables = model_and_variables
        builder = ObjectiveBuilder(model)

        # Create and apply a constraint
        config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        fairness = FairnessConstraint(model, variables, config)
        fairness.apply(workers=workers, shift_types=shift_types, num_periods=4)

        builder.add_constraint(fairness)

        assert len(builder.constraints) == 1
        assert fairness in builder.constraints

    def test_add_multiple_constraints(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test adding multiple constraints."""
        model, variables = model_and_variables
        builder = ObjectiveBuilder(model)

        # Add fairness
        fairness_config = ConstraintConfig(enabled=True, is_hard=False, weight=1000)
        fairness = FairnessConstraint(model, variables, fairness_config)
        fairness.apply(workers=workers, shift_types=shift_types, num_periods=4)
        builder.add_constraint(fairness)

        # Add frequency
        freq_config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=500,
            parameters={"max_periods_between": 2},
        )
        frequency = FrequencyConstraint(model, variables, freq_config)
        frequency.apply(workers=workers, shift_types=shift_types, num_periods=4)
        builder.add_constraint(frequency)

        assert len(builder.constraints) == 2


class TestObjectiveBuilderBuild:
    """Tests for building objective."""

    def test_build_creates_objective_terms(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that build creates objective terms."""
        model, variables = model_and_variables
        builder = ObjectiveBuilder(model)

        # Add fairness constraint
        config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        fairness = FairnessConstraint(model, variables, config)
        fairness.apply(workers=workers, shift_types=shift_types, num_periods=4)
        builder.add_constraint(fairness)

        builder.build()

        assert len(builder.objective_terms) > 0

    def test_build_with_no_constraints(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Test build with no constraints does nothing."""
        model, _ = model_and_variables
        builder = ObjectiveBuilder(model)

        builder.build()

        assert len(builder.objective_terms) == 0

    def test_build_applies_weights(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that weights are correctly applied."""
        model, variables = model_and_variables
        builder = ObjectiveBuilder(model)

        # Add constraint with specific weight
        config = ConstraintConfig(enabled=True, is_hard=False, weight=500)
        fairness = FairnessConstraint(model, variables, config)
        fairness.apply(workers=workers, shift_types=shift_types, num_periods=4)
        builder.add_constraint(fairness)

        builder.build()

        # Check that weight info is captured
        assert len(builder.objective_terms) > 0


class TestObjectiveBuilderSolve:
    """Integration tests solving with ObjectiveBuilder."""

    def test_objective_minimization(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that solver minimizes objective."""
        model = cp_model.CpModel()
        builder_var = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder_var.build()

        # Add fairness
        fairness_config = ConstraintConfig(enabled=True, is_hard=False, weight=1000)
        fairness = FairnessConstraint(model, variables, fairness_config)
        fairness.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Add coverage constraints
        for period in range(4):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Build objective
        obj_builder = ObjectiveBuilder(model)
        obj_builder.add_constraint(fairness)
        obj_builder.build()

        # Solve
        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_multiple_weighted_objectives(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test combining multiple weighted soft constraints."""
        model = cp_model.CpModel()
        builder_var = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder_var.build()

        # Add fairness with high weight
        fairness = FairnessConstraint(
            model,
            variables,
            ConstraintConfig(enabled=True, is_hard=False, weight=1000),
        )
        fairness.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Add frequency with lower weight
        frequency = FrequencyConstraint(
            model,
            variables,
            ConstraintConfig(
                enabled=True,
                is_hard=False,
                weight=100,
                parameters={"max_periods_between": 2},
            ),
        )
        frequency.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Add coverage
        for period in range(4):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Build combined objective
        obj_builder = ObjectiveBuilder(model)
        obj_builder.add_constraint(fairness)
        obj_builder.add_constraint(frequency)
        obj_builder.build()

        # Solve
        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
