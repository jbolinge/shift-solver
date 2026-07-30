"""Tests for pinned assignment constraint."""

import logging

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.pinned import PinnedAssignmentConstraint
from shift_solver.models import ShiftType, Worker
from shift_solver.solver.types import SolverVariables
from shift_solver.solver.variable_builder import VariableBuilder


@pytest.fixture
def workers() -> list[Worker]:
    """Create test workers."""
    return [
        Worker(id="worker_1", name="Worker One"),
        Worker(id="worker_2", name="Worker Two"),
    ]


@pytest.fixture
def shift_types() -> list[ShiftType]:
    """Create shift types."""
    from datetime import time

    return [
        ShiftType(
            id="shift_day",
            name="Day Shift",
            category="cat_a",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=1,
        ),
        ShiftType(
            id="shift_night",
            name="Night Shift",
            category="cat_b",
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
    """Create model and variables for testing (4 periods)."""
    model = cp_model.CpModel()
    builder = VariableBuilder(model, workers, shift_types, num_periods=4)
    variables = builder.build()
    return model, variables


class TestPinnedAssignmentConstraintInit:
    """Tests for PinnedAssignmentConstraint initialization."""

    def test_init_default_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Default config uses BaseConstraint defaults (hard, enabled)."""
        model, variables = model_and_variables
        constraint = PinnedAssignmentConstraint(model, variables)

        assert constraint.constraint_id == "pinned"
        assert constraint.is_enabled
        assert constraint.is_hard
        assert not constraint.handles_hard_mode

    def test_init_disabled(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Constraint can be disabled via config."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=False)
        constraint = PinnedAssignmentConstraint(model, variables, config)

        assert not constraint.is_enabled


class TestPinnedAssignmentConstraintApply:
    """Tests for PinnedAssignmentConstraint.apply()."""

    def test_apply_disabled_does_nothing(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Disabled constraint adds no constraints even with assignments set."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=False,
            parameters={
                "assignments": [
                    {
                        "worker_id": "worker_1",
                        "period_index": 0,
                        "shift_type_id": "shift_day",
                        "value": 1,
                    }
                ]
            },
        )
        constraint = PinnedAssignmentConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert constraint.constraint_count == 0

    def test_apply_no_assignments_param_warns_and_no_ops(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Missing assignments param logs a warning and does nothing."""
        model, variables = model_and_variables
        constraint = PinnedAssignmentConstraint(model, variables)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert constraint.constraint_count == 0
        assert "pinned" in caplog.text.lower()

    def test_apply_empty_assignments_list_no_ops(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Explicit empty assignments list does nothing."""
        model, variables = model_and_variables
        config = ConstraintConfig(parameters={"assignments": []})
        constraint = PinnedAssignmentConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert constraint.constraint_count == 0

    def test_apply_no_violation_variables_created(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Pinned assignment never creates soft violation variables."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            parameters={
                "assignments": [
                    {
                        "worker_id": "worker_1",
                        "period_index": 0,
                        "shift_type_id": "shift_day",
                        "value": 1,
                    }
                ]
            },
        )
        constraint = PinnedAssignmentConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert constraint.constraint_count == 1
        assert len(constraint.violation_variables) == 0

    @pytest.mark.parametrize(
        ("bad_record", "expected_substring"),
        [
            (
                {
                    "worker_id": "unknown_worker",
                    "period_index": 0,
                    "shift_type_id": "shift_day",
                    "value": 1,
                },
                "unknown worker_id",
            ),
            (
                {
                    "worker_id": "worker_1",
                    "period_index": 0,
                    "shift_type_id": "unknown_shift",
                    "value": 1,
                },
                "unknown",
            ),
            (
                {
                    "worker_id": "worker_1",
                    "period_index": 99,
                    "shift_type_id": "shift_day",
                    "value": 1,
                },
                "out of range",
            ),
            (
                {
                    "worker_id": "worker_1",
                    "period_index": -1,
                    "shift_type_id": "shift_day",
                    "value": 1,
                },
                "out of range",
            ),
            (
                {
                    "worker_id": "worker_1",
                    "period_index": 0,
                    "shift_type_id": "shift_day",
                    "value": 2,
                },
                "value must be 0 or 1",
            ),
            (
                "not_a_dict",
                "expected a dict",
            ),
        ],
    )
    def test_apply_skips_invalid_records_with_warning(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
        bad_record: object,
        expected_substring: str,
    ) -> None:
        """Invalid pin records are skipped (warned), not raised as errors."""
        model, variables = model_and_variables
        config = ConstraintConfig(parameters={"assignments": [bad_record]})
        constraint = PinnedAssignmentConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert constraint.constraint_count == 0
        assert expected_substring in caplog.text.lower()

    def test_apply_skips_missing_assignment_variable(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A pin referencing a valid worker/shift/period combo whose variable
        doesn't exist in a smaller/custom SolverVariables is skipped."""
        model = cp_model.CpModel()
        # Build variables for a single period only, then reference period 0
        # via a record naming a valid worker+shift but simulate a missing
        # var by using a hand-built SolverVariables missing that entry.
        variables = SolverVariables(
            assignment={}, shift_counts={}, undesirable_totals={}
        )

        config = ConstraintConfig(
            parameters={
                "assignments": [
                    {
                        "worker_id": "worker_1",
                        "period_index": 0,
                        "shift_type_id": "shift_day",
                        "value": 1,
                    }
                ]
            },
        )
        constraint = PinnedAssignmentConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert constraint.constraint_count == 0
        assert "no assignment variable" in caplog.text.lower()


class TestPinnedAssignmentConstraintSolve:
    """Integration tests that solve with the pinned constraint."""

    def test_pin_value_1_forces_assignment(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """A value=1 pin forces the worker onto that shift/period."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        config = ConstraintConfig(
            parameters={
                "assignments": [
                    {
                        "worker_id": "worker_1",
                        "period_index": 0,
                        "shift_type_id": "shift_day",
                        "value": 1,
                    }
                ]
            },
        )
        constraint = PinnedAssignmentConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert (
            solver.value(variables.get_assignment_var("worker_1", 0, "shift_day")) == 1
        )

    def test_pin_value_0_forbids_assignment(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """A value=0 pin forbids the worker from that shift/period."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        config = ConstraintConfig(
            parameters={
                "assignments": [
                    {
                        "worker_id": "worker_1",
                        "period_index": 0,
                        "shift_type_id": "shift_day",
                        "value": 0,
                    }
                ]
            },
        )
        constraint = PinnedAssignmentConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Coverage: exactly 1 worker for the day shift in period 0.
        vars_for_shift = [
            variables.get_assignment_var(w.id, 0, "shift_day") for w in workers
        ]
        model.add(sum(vars_for_shift) == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert (
            solver.value(variables.get_assignment_var("worker_1", 0, "shift_day")) == 0
        )
        assert (
            solver.value(variables.get_assignment_var("worker_2", 0, "shift_day")) == 1
        )

    def test_conflicting_pins_infeasible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Two hard pins that violate coverage together are infeasible."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        # Both workers pinned onto the same single-slot shift.
        config = ConstraintConfig(
            parameters={
                "assignments": [
                    {
                        "worker_id": "worker_1",
                        "period_index": 0,
                        "shift_type_id": "shift_day",
                        "value": 1,
                    },
                    {
                        "worker_id": "worker_2",
                        "period_index": 0,
                        "shift_type_id": "shift_day",
                        "value": 0,
                    },
                ]
            },
        )
        constraint = PinnedAssignmentConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        # Coverage requires exactly 2 workers on day shift, but worker_2 is
        # pinned to 0 and there are only 2 workers -- infeasible.
        vars_for_shift = [
            variables.get_assignment_var(w.id, 0, "shift_day") for w in workers
        ]
        model.add(sum(vars_for_shift) == 2)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status == cp_model.INFEASIBLE

    def test_multiple_pins_all_enforced(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Multiple valid pins are all enforced simultaneously."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=2)
        variables = builder.build()

        config = ConstraintConfig(
            parameters={
                "assignments": [
                    {
                        "worker_id": "worker_1",
                        "period_index": 0,
                        "shift_type_id": "shift_day",
                        "value": 1,
                    },
                    {
                        "worker_id": "worker_1",
                        "period_index": 1,
                        "shift_type_id": "shift_night",
                        "value": 0,
                    },
                    {
                        "worker_id": "worker_2",
                        "period_index": 1,
                        "shift_type_id": "shift_night",
                        "value": 1,
                    },
                ]
            },
        )
        constraint = PinnedAssignmentConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=2)

        assert constraint.constraint_count == 3

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert (
            solver.value(variables.get_assignment_var("worker_1", 0, "shift_day")) == 1
        )
        assert (
            solver.value(variables.get_assignment_var("worker_1", 1, "shift_night"))
            == 0
        )
        assert (
            solver.value(variables.get_assignment_var("worker_2", 1, "shift_night"))
            == 1
        )

    def test_add_hint_records_solution_hint(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Applying a pin also records a solver hint for that variable."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(
            parameters={
                "assignments": [
                    {
                        "worker_id": "worker_1",
                        "period_index": 0,
                        "shift_type_id": "shift_day",
                        "value": 1,
                    }
                ]
            },
        )
        constraint = PinnedAssignmentConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        pinned_var = variables.get_assignment_var("worker_1", 0, "shift_day")
        hint_proto = model.proto.solution_hint
        assert pinned_var.index in list(hint_proto.vars)
        hinted_index = list(hint_proto.vars).index(pinned_var.index)
        assert hint_proto.values[hinted_index] == 1
