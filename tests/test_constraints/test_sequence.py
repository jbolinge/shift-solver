"""Tests for sequence constraint."""

import logging
from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.sequence import SequenceConstraint
from shift_solver.models import ShiftType, Worker
from shift_solver.solver.objective_builder import ObjectiveBuilder
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
    """Create shift types with different categories."""
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
        ShiftType(
            id="ambulatory",
            name="Ambulatory",
            category="ambulatory",
            start_time=time(8, 0),
            end_time=time(17, 0),
            duration_hours=9.0,
            workers_required=1,
        ),
    ]


@pytest.fixture
def model_and_variables(
    workers: list[Worker], shift_types: list[ShiftType]
) -> tuple[cp_model.CpModel, SolverVariables]:
    """Create model and variables for testing."""
    model = cp_model.CpModel()
    builder = VariableBuilder(model, workers, shift_types, num_periods=6)
    variables = builder.build()
    return model, variables


class TestSequenceConstraintInit:
    """Tests for SequenceConstraint initialization."""

    def test_init_default_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Test initialization with default config uses BaseConstraint defaults."""
        model, variables = model_and_variables
        constraint = SequenceConstraint(model, variables)

        assert constraint.constraint_id == "sequence"
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
        constraint = SequenceConstraint(model, variables, config)

        assert constraint.constraint_id == "sequence"
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
            weight=200,
            parameters={"categories": ["ambulatory"]},
        )
        constraint = SequenceConstraint(model, variables, config)

        assert constraint.weight == 200
        assert constraint.config.get_param("categories") == ["ambulatory"]


class TestSequenceConstraintApply:
    """Tests for SequenceConstraint.apply()."""

    def test_apply_creates_violation_variables(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that apply creates violation variables for consecutive assignments."""
        model, variables = model_and_variables
        constraint = SequenceConstraint(model, variables)

        constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        # Should have violation variables
        assert len(constraint.violation_variables) > 0

    def test_apply_with_category_filter(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that category filter limits which shifts are checked."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"categories": ["ambulatory"]},
        )
        constraint = SequenceConstraint(model, variables, config)

        constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        # Should have violation variables only for ambulatory
        assert len(constraint.violation_variables) > 0
        # Check that variables are only for ambulatory category
        for name in constraint.violation_variables:
            if name != "total":
                assert "ambulatory" in name

    def test_apply_disabled_does_nothing(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that disabled constraint adds no constraints."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=False)
        constraint = SequenceConstraint(model, variables, config)

        constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        assert len(constraint.violation_variables) == 0


class TestSequenceConstraintSolve:
    """Integration tests that solve with sequence constraint."""

    def test_sequence_discourages_consecutive(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that sequence constraint discourages consecutive same-category."""
        model = cp_model.CpModel()
        # Use 3 workers for more flexibility
        workers_extended = workers + [Worker(id="W003", name="Worker 3")]
        builder = VariableBuilder(model, workers_extended, shift_types, num_periods=6)
        variables = builder.build()

        # Apply sequence constraint with high weight
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=1000,
        )
        constraint = SequenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers_extended, shift_types=shift_types, num_periods=6
        )

        # Add coverage constraint
        for period in range(6):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers_extended
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Minimize violations
        if constraint.violation_variables:
            # Only sum actual violation vars, not total
            viol_vars = [
                v for k, v in constraint.violation_variables.items() if k != "total"
            ]
            if viol_vars:
                model.minimize(sum(viol_vars) * constraint.weight)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_sequence_allows_solution_with_necessary_consecutive(
        self,
        shift_types: list[ShiftType],
    ) -> None:
        """Test that constraint is soft and allows solution even if consecutive needed."""
        # With only 2 workers and 3 shift types, consecutive is unavoidable
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="W1"), Worker(id="W002", name="W2")]
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # Apply soft sequence constraint
        config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        constraint = SequenceConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Add coverage
        for period in range(4):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        # Should still find a solution even with unavoidable consecutive
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


class TestSequenceObjectiveDoubleCount:
    """Regression tests for bug A: the debug 'total' aggregate variable must
    not contribute an extra term to the objective on top of the individual
    seq_viol_* violations it sums (previously this doubled the effective
    weight of the constraint)."""

    def test_total_var_registered_as_auxiliary(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """The 'total' violation var must be typed as auxiliary."""
        model, variables = model_and_variables
        constraint = SequenceConstraint(
            model, variables, ConstraintConfig(enabled=True, is_hard=False, weight=100)
        )
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        assert "total" in constraint.violation_variables
        assert constraint.violation_variable_types.get("total") == "auxiliary"

    def test_objective_builder_excludes_total_from_terms(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """ObjectiveBuilder must skip the 'total' aggregate: the objective
        should contain exactly one term per seq_viol_* variable and nothing
        for 'total'."""
        model, variables = model_and_variables
        constraint = SequenceConstraint(
            model, variables, ConstraintConfig(enabled=True, is_hard=False, weight=100)
        )
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        builder = ObjectiveBuilder(model)
        builder.add_constraint(constraint)
        builder.build()

        term_names = {term.variable_name for term in builder.objective_terms}
        seq_viol_names = {
            k for k in constraint.violation_variables if k.startswith("seq_viol_")
        }
        assert "total" not in term_names
        assert term_names == seq_viol_names


class TestSequenceWarnsOnTooFewPeriods:
    """Regression tests for bug D: the num_periods < 2 early return must log
    a warning naming the constraint, the parameter, and the horizon instead
    of silently doing nothing."""

    def test_warns_when_num_periods_less_than_two(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        num_periods = 1
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        constraint = SequenceConstraint(
            model, variables, ConstraintConfig(enabled=True, is_hard=False, weight=100)
        )
        with caplog.at_level(logging.WARNING):
            constraint.apply(
                workers=workers, shift_types=shift_types, num_periods=num_periods
            )

        assert len(constraint.violation_variables) == 0
        assert "sequence" in caplog.text.lower()
        assert str(num_periods) in caplog.text
