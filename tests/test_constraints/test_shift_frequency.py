"""Tests for shift frequency constraint (scheduler-94)."""

from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.shift_frequency import ShiftFrequencyConstraint
from shift_solver.models import ShiftFrequencyRequirement, ShiftType, Worker
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
            id="mvsc_day",
            name="MVSC Day",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=1,
        ),
        ShiftType(
            id="mvsc_night",
            name="MVSC Night",
            category="night",
            start_time=time(23, 0),
            end_time=time(7, 0),
            duration_hours=8.0,
            workers_required=1,
        ),
        ShiftType(
            id="stf_day",
            name="STF Day",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
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


class TestShiftFrequencyConstraintInit:
    """Tests for ShiftFrequencyConstraint initialization."""

    def test_init_default_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Test initialization with default config."""
        model, variables = model_and_variables
        constraint = ShiftFrequencyConstraint(model, variables)

        assert constraint.constraint_id == "shift_frequency"
        assert constraint.is_enabled
        assert constraint.is_hard
        assert constraint.weight == 100

    def test_init_soft_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Test initialization with explicit soft config."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=500)
        constraint = ShiftFrequencyConstraint(model, variables, config)

        assert constraint.is_enabled
        assert not constraint.is_hard
        assert constraint.weight == 500


class TestShiftFrequencyConstraintApply:
    """Tests for ShiftFrequencyConstraint.apply()."""

    def test_apply_creates_violation_variables(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that apply creates violation variables for windows."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=500)
        constraint = ShiftFrequencyConstraint(model, variables, config)

        requirements = [
            ShiftFrequencyRequirement(
                worker_id="W001",
                shift_types=frozenset(["mvsc_day", "mvsc_night"]),
                max_periods_between=4,
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=8,
            shift_frequency_requirements=requirements,
        )

        # Should have violation variables for sliding windows
        # 8 periods with window=4 means 5 windows (0-3, 1-4, 2-5, 3-6, 4-7)
        assert len(constraint.violation_variables) == 5

    def test_apply_disabled_does_nothing(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that disabled constraint adds no constraints."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=False)
        constraint = ShiftFrequencyConstraint(model, variables, config)

        requirements = [
            ShiftFrequencyRequirement(
                worker_id="W001",
                shift_types=frozenset(["mvsc_day"]),
                max_periods_between=4,
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=8,
            shift_frequency_requirements=requirements,
        )

        assert len(constraint.violation_variables) == 0

    def test_apply_no_requirements(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that no requirements means no constraints."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=500)
        constraint = ShiftFrequencyConstraint(model, variables, config)

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=8,
            shift_frequency_requirements=[],
        )

        assert len(constraint.violation_variables) == 0


class TestShiftFrequencyConstraintMultipleWorkers:
    """Tests for multiple workers with different requirements."""

    def test_multiple_workers_different_requirements(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test multiple workers with different frequency requirements."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=500)
        constraint = ShiftFrequencyConstraint(model, variables, config)

        requirements = [
            ShiftFrequencyRequirement(
                worker_id="W001",
                shift_types=frozenset(["mvsc_day", "mvsc_night"]),
                max_periods_between=4,
            ),
            ShiftFrequencyRequirement(
                worker_id="W002",
                shift_types=frozenset(["stf_day"]),
                max_periods_between=2,
            ),
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=8,
            shift_frequency_requirements=requirements,
        )

        # W001: 8 periods, window=4, 5 windows
        # W002: 8 periods, window=2, 7 windows
        # Total: 12 violation variables
        assert len(constraint.violation_variables) == 12


class TestShiftFrequencyConstraintSolve:
    """Integration tests that solve with shift frequency constraint."""

    def test_soft_constraint_encourages_assignments(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that soft constraint encourages assignments in each window."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=8)
        variables = builder.build()

        config = ConstraintConfig(enabled=True, is_hard=False, weight=1000)
        constraint = ShiftFrequencyConstraint(model, variables, config)

        requirements = [
            ShiftFrequencyRequirement(
                worker_id="W001",
                shift_types=frozenset(["mvsc_day", "mvsc_night"]),
                max_periods_between=4,
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=8,
            shift_frequency_requirements=requirements,
        )

        # Add basic coverage
        for period in range(8):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Minimize violations
        if constraint.violation_variables:
            model.minimize(
                sum(constraint.violation_variables.values()) * constraint.weight
            )

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_hard_constraint_enforces_assignments(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that hard constraint enforces at least one assignment per window."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=8)
        variables = builder.build()

        config = ConstraintConfig(enabled=True, is_hard=True)
        constraint = ShiftFrequencyConstraint(model, variables, config)

        requirements = [
            ShiftFrequencyRequirement(
                worker_id="W001",
                shift_types=frozenset(["mvsc_day", "mvsc_night"]),
                max_periods_between=4,
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=8,
            shift_frequency_requirements=requirements,
        )

        # Add basic coverage
        for period in range(8):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # Verify W001 has at least one assignment to mvsc_day or mvsc_night
        # in each window
        for window_start in range(5):  # 5 windows of size 4
            window_assignments = 0
            for period in range(window_start, window_start + 4):
                for shift_id in ["mvsc_day", "mvsc_night"]:
                    var = variables.get_assignment_var("W001", period, shift_id)
                    if solver.value(var) == 1:
                        window_assignments += 1
            assert window_assignments >= 1


class TestShiftFrequencyEdgeCases:
    """Tests for edge cases in shift frequency constraint."""

    def test_unknown_worker_id_skipped(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that unknown worker_id in requirement is skipped."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=500)
        constraint = ShiftFrequencyConstraint(model, variables, config)

        requirements = [
            ShiftFrequencyRequirement(
                worker_id="UNKNOWN",
                shift_types=frozenset(["mvsc_day"]),
                max_periods_between=4,
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=8,
            shift_frequency_requirements=requirements,
        )

        # Should have no violation variables for unknown worker
        assert len(constraint.violation_variables) == 0

    def test_unknown_shift_type_filtered(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test that unknown shift types in requirement are filtered."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=500)
        constraint = ShiftFrequencyConstraint(model, variables, config)

        requirements = [
            ShiftFrequencyRequirement(
                worker_id="W001",
                shift_types=frozenset(["unknown_shift"]),
                max_periods_between=4,
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=8,
            shift_frequency_requirements=requirements,
        )

        # Should have no violation variables for unknown shift types
        assert len(constraint.violation_variables) == 0

    def test_window_larger_than_periods(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test when window size > num_periods (uses num_periods as window)."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=3)
        variables = builder.build()

        config = ConstraintConfig(enabled=True, is_hard=False, weight=500)
        constraint = ShiftFrequencyConstraint(model, variables, config)

        requirements = [
            ShiftFrequencyRequirement(
                worker_id="W001",
                shift_types=frozenset(["mvsc_day"]),
                max_periods_between=10,  # Larger than num_periods
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=3,
            shift_frequency_requirements=requirements,
        )

        # Should have 1 window covering all periods
        assert len(constraint.violation_variables) == 1

    def test_max_periods_between_equals_one(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Test when max_periods_between=1 (must work every period)."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=500)
        constraint = ShiftFrequencyConstraint(model, variables, config)

        requirements = [
            ShiftFrequencyRequirement(
                worker_id="W001",
                shift_types=frozenset(["mvsc_day", "mvsc_night"]),
                max_periods_between=1,  # Must work every period
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=8,
            shift_frequency_requirements=requirements,
        )

        # 8 periods with window=1 means 8 windows (one per period)
        assert len(constraint.violation_variables) == 8
