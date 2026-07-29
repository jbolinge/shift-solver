"""Tests for frequency constraint."""

import logging
from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.frequency import FrequencyConstraint
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
        """Test initialization with default config uses BaseConstraint defaults."""
        model, variables = model_and_variables
        constraint = FrequencyConstraint(model, variables)

        assert constraint.constraint_id == "frequency"
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
        constraint = FrequencyConstraint(model, variables, config)

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

        # Minimize violations (only the real violation vars, not the
        # "total" debug aggregate)
        freq_viols = [
            v
            for k, v in constraint.violation_variables.items()
            if k.startswith("freq_viol_")
        ]
        if freq_viols:
            model.minimize(sum(freq_viols) * constraint.weight)

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


class TestFrequencyWindowEdgeCases:
    """
    Tests for frequency constraint window size edge cases (scheduler-72).

    Tests boundary conditions when window size approaches or exceeds
    num_periods. Window size equals max_periods_between exactly (no +1);
    see TestFrequencyWindowOffByOne for the regression coverage of that
    sizing itself.
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

        # max_periods_between = num_periods means window_size = num_periods
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_between": num_periods},
        )
        constraint = FrequencyConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        # One aggregated violation var per worker per window (not per
        # shift type): 2 workers * 1 window = 2 freq_viol variables.
        freq_viol_vars = [k for k in constraint.violation_variables if k.startswith("freq_viol_")]
        assert len(freq_viol_vars) == len(workers)

    def test_window_exceeds_num_periods(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test when window_size > num_periods (constraint skipped, with a warning)."""
        num_periods = 4
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        # max_periods_between = num_periods + 1 means window_size > num_periods (4)
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_between": num_periods + 1},
        )
        constraint = FrequencyConstraint(model, variables, config)
        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        # No violation variables should be created when window > num_periods
        assert len(constraint.violation_variables) == 0
        # A warning naming the constraint, the parameter value, and the
        # horizon must be emitted instead of silently doing nothing.
        assert "frequency" in caplog.text.lower()
        assert str(num_periods + 1) in caplog.text
        assert str(num_periods) in caplog.text

    def test_window_much_larger_than_num_periods(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test when window_size >> num_periods (large config, small schedule)."""
        num_periods = 2
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        # max_periods_between = 100 means window_size = 100 >> num_periods (2)
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_between": 100},
        )
        constraint = FrequencyConstraint(model, variables, config)
        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        # Should be skipped, with a warning logged
        assert len(constraint.violation_variables) == 0
        assert "frequency" in caplog.text.lower()

    def test_max_periods_between_one(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test when max_periods_between = 1 (window_size = 1, each period independent)."""
        num_periods = 4
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        # max_periods_between = 1 means window_size = 1: every single
        # period is its own window and must have an assignment.
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_between": 1},
        )
        constraint = FrequencyConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        # Should have num_periods windows per worker (aggregated across
        # shift types, not multiplied by them).
        freq_viol_vars = [k for k in constraint.violation_variables if k.startswith("freq_viol_")]
        expected_count = len(workers) * num_periods
        assert len(freq_viol_vars) == expected_count

    def test_max_periods_between_zero_is_degenerate(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """max_periods_between=0 yields empty windows (no periods to check),
        so no violation variables are created -- this is harmless, not a
        crash."""
        num_periods = 4
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_between": 0},
        )
        constraint = FrequencyConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        assert len(constraint.violation_variables) == 0

    def test_max_periods_between_maximum_useful(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test when max_periods_between = num_periods (maximum useful value)."""
        num_periods = 6
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        # max_periods_between = num_periods means window_size = num_periods
        # Maximum useful value - exactly 1 window
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_between": num_periods},
        )
        constraint = FrequencyConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        # Should have exactly 1 window per worker
        freq_viol_vars = [k for k in constraint.violation_variables if k.startswith("freq_viol_")]
        assert len(freq_viol_vars) == len(workers)

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

        # max_periods_between = num_periods + 1 means window_size > num_periods (3)
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_between": num_periods + 1},
        )
        constraint = FrequencyConstraint(model, variables, config)
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
            parameters={"max_periods_between": num_periods},
        )
        constraint = FrequencyConstraint(model, variables, config)
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
            freq_viols = [
                v for k, v in constraint.violation_variables.items()
                if k.startswith("freq_viol_")
            ]
            if freq_viols:
                model.minimize(sum(freq_viols) * config.weight)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


class TestFrequencyObjectiveDoubleCount:
    """Regression tests for bug A: the debug 'total' aggregate variable must
    not contribute an extra term to the objective on top of the individual
    freq_viol_* violations it sums (previously this doubled the effective
    weight of the constraint)."""

    def test_total_var_registered_as_auxiliary(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """The 'total' violation var must be typed as auxiliary."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_between": 3},
        )
        constraint = FrequencyConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=8)

        assert "total" in constraint.violation_variables
        assert constraint.violation_variable_types.get("total") == "auxiliary"

    def test_objective_builder_excludes_total_from_terms(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """ObjectiveBuilder must skip the 'total' aggregate: the objective
        should contain exactly one term per freq_viol_* variable and nothing
        for 'total'."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_between": 3},
        )
        constraint = FrequencyConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=8)

        builder = ObjectiveBuilder(model)
        builder.add_constraint(constraint)
        builder.build()

        term_names = {term.variable_name for term in builder.objective_terms}
        freq_viol_names = {
            k for k in constraint.violation_variables if k.startswith("freq_viol_")
        }
        assert "total" not in term_names
        assert term_names == freq_viol_names


class TestFrequencyAggregation:
    """Regression tests for bug B: a single violation variable must be
    created per (worker, window), true iff the worker has zero assignments
    across ALL filtered shift types in that window -- not one violation per
    (worker, shift_type, window) demanding every shift type be touched every
    window."""

    def test_one_violation_per_worker_window_not_per_shift_type(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        model, variables = model_and_variables
        num_periods = 8
        max_periods_between = 3
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_between": max_periods_between},
        )
        constraint = FrequencyConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        num_windows = num_periods - max_periods_between + 1
        freq_viol_vars = [k for k in constraint.violation_variables if k.startswith("freq_viol_")]
        assert len(freq_viol_vars) == len(workers) * num_windows

    def test_worker_touching_only_one_shift_type_has_no_violation(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """A worker assigned to just ONE of the filtered shift types across a
        window must not be penalized. The old per-shift-type explosion
        demanded every filtered shift type be touched every window, which is
        arithmetically unsatisfiable when a worker can only hold one shift
        per period."""
        num_periods = 4
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_between": num_periods},
        )
        constraint = FrequencyConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        # W001 works "day" every period and never "night".
        for period in range(num_periods):
            model.add(variables.get_assignment_var("W001", period, "day") == 1)
            model.add(variables.get_assignment_var("W001", period, "night") == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        w001_violations = [
            solver.value(v)
            for k, v in constraint.violation_variables.items()
            if k.startswith("freq_viol_W001_")
        ]
        assert w001_violations  # sanity: some violation vars were created
        assert all(v == 0 for v in w001_violations)


class TestFrequencyWindowOffByOne:
    """Regression tests for bug C: window_size must equal max_periods_between
    exactly (not max_periods_between + 1), matching the docstring's
    'every window of N consecutive periods' semantics."""

    def test_window_count_matches_max_periods_between_exactly(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        num_periods = 6
        max_periods_between = 3
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_between": max_periods_between, "shift_types": ["day"]},
        )
        constraint = FrequencyConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        # window_size == max_periods_between (NOT +1): 6 - 3 + 1 = 4 windows
        expected_windows = num_periods - max_periods_between + 1
        freq_viol_vars = [k for k in constraint.violation_variables if k.startswith("freq_viol_")]
        assert len(freq_viol_vars) == len(workers) * expected_windows

    def test_gap_of_exactly_max_periods_between_is_flagged(
        self,
        shift_types: list[ShiftType],
    ) -> None:
        """A gap of exactly max_periods_between consecutive periods without an
        assignment must be flagged. The old +1 formula would have let this
        exact gap pass unpenalized."""
        num_periods = 5
        max_periods_between = 3
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Worker 1")]
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_periods_between": max_periods_between},
        )
        constraint = FrequencyConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        # No assignment at all in periods 0,1,2 (a gap of exactly 3 == max_periods_between).
        for period in range(3):
            for st in shift_types:
                model.add(variables.get_assignment_var("W001", period, st.id) == 0)
        # Worker is assigned in periods 3 and 4 so later windows are covered.
        for period in (3, 4):
            model.add(variables.get_assignment_var("W001", period, "day") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # Window starting at period 0 (periods 0,1,2) must be flagged.
        window0_violation = constraint.violation_variables["freq_viol_W001_w0"]
        assert solver.value(window0_violation) == 1
