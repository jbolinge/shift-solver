"""Tests for max absence constraint."""

from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.max_absence import MaxAbsenceConstraint
from shift_solver.models import ShiftType, Worker
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
    builder = VariableBuilder(model, workers, shift_types, num_periods=10)
    variables = builder.build()
    return model, variables


class TestMaxAbsenceConstraintInit:
    """Tests for MaxAbsenceConstraint initialization."""

    def test_init_default_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Test initialization with default config uses BaseConstraint defaults."""
        model, variables = model_and_variables
        constraint = MaxAbsenceConstraint(model, variables)

        assert constraint.constraint_id == "max_absence"
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
        constraint = MaxAbsenceConstraint(model, variables, config)

        assert constraint.constraint_id == "max_absence"
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
            parameters={"max_periods_absent": 6},
        )
        constraint = MaxAbsenceConstraint(model, variables, config)

        assert constraint.weight == 200
        assert constraint.config.get_param("max_periods_absent") == 6


class TestMaxAbsenceConstraintApply:
    """Tests for MaxAbsenceConstraint.apply()."""

    def test_apply_creates_violation_variables(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that apply creates violation variables for long absences."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_absent": 4},
        )
        constraint = MaxAbsenceConstraint(model, variables, config)

        constraint.apply(workers=workers, shift_types=shift_types, num_periods=10)

        # Should have violation variables
        assert len(constraint.violation_variables) > 0

    def test_apply_with_shift_type_filter(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that shift_types filter limits which shifts are checked."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_absent": 4, "shift_types": ["night"]},
        )
        constraint = MaxAbsenceConstraint(model, variables, config)

        constraint.apply(workers=workers, shift_types=shift_types, num_periods=10)

        # Should have violation variables only for night shifts
        assert len(constraint.violation_variables) > 0
        for name in constraint.violation_variables:
            if name != "total":
                assert "night" in name

    def test_apply_disabled_does_nothing(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that disabled constraint adds no constraints."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=False)
        constraint = MaxAbsenceConstraint(model, variables, config)

        constraint.apply(workers=workers, shift_types=shift_types, num_periods=10)

        assert len(constraint.violation_variables) == 0


class TestMaxAbsenceConstraintSolve:
    """Integration tests that solve with max absence constraint."""

    def test_max_absence_discourages_long_gaps(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that max absence encourages regular assignments."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=10)
        variables = builder.build()

        # Apply max absence with 4 period limit
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=1000,
            parameters={"max_periods_absent": 4},
        )
        constraint = MaxAbsenceConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=10)

        # Add coverage
        for period in range(10):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Minimize violations
        if constraint.violation_variables:
            viol_vars = [
                v for k, v in constraint.violation_variables.items() if k != "total"
            ]
            if viol_vars:
                model.minimize(sum(viol_vars) * constraint.weight)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_max_absence_allows_solution_with_violations(
        self,
        shift_types: list[ShiftType],
    ) -> None:
        """Test that constraint is soft and allows unavoidable violations."""
        # With only 1 worker and 2 shifts, gaps are unavoidable
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="W1")]
        builder = VariableBuilder(model, workers, shift_types, num_periods=10)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_absent": 2},
        )
        constraint = MaxAbsenceConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=10)

        # Add coverage - with 1 worker, they get all shifts
        for period in range(10):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        # Should find solution even with violations
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


class TestMaxAbsenceWindowEdgeCases:
    """
    Tests for max absence constraint window size edge cases (scheduler-72).

    Tests boundary conditions when window size approaches or exceeds num_periods.
    """

    def test_window_equals_num_periods(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test when window_size == num_periods (exactly 1 window)."""
        num_periods = 5
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        # max_periods_absent = 4 means window_size = 5 = num_periods
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_absent": num_periods - 1},
        )
        constraint = MaxAbsenceConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        # Should have exactly 1 window per worker per shift type
        abs_viol_vars = [k for k in constraint.violation_variables if k.startswith("abs_viol_")]
        assert len(abs_viol_vars) == len(workers) * len(shift_types)

    def test_window_exceeds_num_periods(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test when window_size > num_periods (constraint silently skipped)."""
        num_periods = 4
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        # max_periods_absent = 4 means window_size = 5 > num_periods (4)
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_absent": num_periods},  # window = num_periods + 1
        )
        constraint = MaxAbsenceConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        # No violation variables should be created when window > num_periods
        assert len(constraint.violation_variables) == 0

    def test_window_much_larger_than_num_periods(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test when window_size >> num_periods (large config, small schedule)."""
        num_periods = 2
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        # max_periods_absent = 100 means window_size = 101 >> num_periods (2)
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_absent": 100},
        )
        constraint = MaxAbsenceConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        # Should be silently skipped
        assert len(constraint.violation_variables) == 0

    def test_max_periods_absent_zero(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test when max_periods_absent = 0 (window_size = 1, each period independent)."""
        num_periods = 4
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        # max_periods_absent = 0 means window_size = 1
        # Each period is a separate window
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_absent": 0},
        )
        constraint = MaxAbsenceConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        # Should have num_periods windows per worker per shift type
        abs_viol_vars = [k for k in constraint.violation_variables if k.startswith("abs_viol_")]
        expected_count = len(workers) * len(shift_types) * num_periods
        assert len(abs_viol_vars) == expected_count

    def test_max_periods_absent_maximum_useful(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test when max_periods_absent = num_periods - 1 (maximum useful value)."""
        num_periods = 6
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        # max_periods_absent = 5 means window_size = 6 = num_periods
        # Maximum useful value - exactly 1 window
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_absent": num_periods - 1},
        )
        constraint = MaxAbsenceConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        # Should have exactly 1 window per worker per shift type
        abs_viol_vars = [k for k in constraint.violation_variables if k.startswith("abs_viol_")]
        assert len(abs_viol_vars) == len(workers) * len(shift_types)

    def test_window_size_one_more_than_periods_boundary(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test boundary: window_size = num_periods + 1 (just over the edge)."""
        num_periods = 3
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        # max_periods_absent = 3 means window_size = 4 > num_periods (3)
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_absent": num_periods},
        )
        constraint = MaxAbsenceConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        # Should be skipped since window > num_periods
        assert len(constraint.violation_variables) == 0

    def test_solve_with_boundary_window(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that solve works correctly at boundary conditions."""
        num_periods = 4
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        # window_size = 4 = num_periods (exactly at boundary)
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=1000,
            parameters={"max_periods_absent": num_periods - 1},
        )
        constraint = MaxAbsenceConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        # Add coverage
        for period in range(num_periods):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Minimize violations
        if constraint.violation_variables:
            abs_viols = [
                v for k, v in constraint.violation_variables.items()
                if k.startswith("abs_viol_")
            ]
            if abs_viols:
                model.minimize(sum(abs_viols) * config.weight)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
