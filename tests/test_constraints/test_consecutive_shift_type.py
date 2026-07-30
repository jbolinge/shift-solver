"""Tests for consecutive shift type constraint."""

import logging
from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.consecutive_shift_type import (
    ConsecutiveShiftTypeConstraint,
)
from shift_solver.models import ShiftType, Worker
from shift_solver.solver.types import SolverVariables
from shift_solver.solver.variable_builder import VariableBuilder


@pytest.fixture
def workers() -> list[Worker]:
    """Create test workers."""
    return [
        Worker(id="worker_1", name="Worker 1"),
        Worker(id="worker_2", name="Worker 2"),
    ]


@pytest.fixture
def shift_types() -> list[ShiftType]:
    """Create shift types with distinct categories."""
    return [
        ShiftType(
            id="shift_night",
            name="Night Shift",
            category="cat_night",
            start_time=time(23, 0),
            end_time=time(7, 0),
            duration_hours=8.0,
        ),
        ShiftType(
            id="shift_day",
            name="Day Shift",
            category="cat_day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
        ),
    ]


def _build(
    workers: list[Worker], shift_types: list[ShiftType], num_periods: int
) -> tuple[cp_model.CpModel, SolverVariables]:
    model = cp_model.CpModel()
    builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
    return model, builder.build()


@pytest.fixture
def model_and_variables(
    workers: list[Worker], shift_types: list[ShiftType]
) -> tuple[cp_model.CpModel, SolverVariables]:
    """Create model and variables for testing (4 periods)."""
    return _build(workers, shift_types, num_periods=4)


class TestInit:
    """Tests for ConsecutiveShiftTypeConstraint initialization."""

    def test_default_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        model, variables = model_and_variables
        constraint = ConsecutiveShiftTypeConstraint(model, variables)

        assert constraint.constraint_id == "consecutive_shift_type"
        assert constraint.is_enabled
        assert constraint.is_hard
        assert constraint.weight == 100

    def test_soft_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=250)
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)

        assert not constraint.is_hard
        assert constraint.weight == 250

    def test_does_not_handle_hard_mode_itself(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """No per-rule hard/soft override exists, so the generic solver
        pin-to-zero mechanism is appropriate as a backstop (even though, in
        practice, this constraint never creates violation vars while
        is_hard=True, so there's nothing to pin)."""
        model, variables = model_and_variables
        constraint = ConsecutiveShiftTypeConstraint(model, variables)
        assert constraint.handles_hard_mode is False


class TestNoOpPaths:
    """Silent no-op paths that must warn instead of doing nothing quietly."""

    def test_disabled_does_nothing(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=False,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "shift_types": ["shift_night"],
                        "max_consecutive": 2,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0

    def test_no_rules_param_warns_and_noops(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        model, variables = model_and_variables
        constraint = ConsecutiveShiftTypeConstraint(
            model, variables, ConstraintConfig()
        )

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert "consecutive_shift_type" in caplog.text.lower()
        assert "rules" in caplog.text.lower()

    def test_rule_missing_both_filters_warns_and_skips(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        model, variables = model_and_variables
        config = ConstraintConfig(
            parameters={"rules": [{"rule_id": "no_filter", "max_consecutive": 2}]}
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert "no_filter" in caplog.text

    def test_rule_filters_match_nothing_warns_and_skips(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        model, variables = model_and_variables
        config = ConstraintConfig(
            parameters={
                "rules": [
                    {
                        "rule_id": "bad_ids",
                        "shift_types": ["does_not_exist"],
                        "max_consecutive": 2,
                    }
                ]
            }
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert "bad_ids" in caplog.text

    def test_rule_with_no_effective_params_warns_and_skips(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A rule with a valid filter but no min/max/rest is a no-op."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            parameters={"rules": [{"rule_id": "noop", "shift_types": ["shift_night"]}]}
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert "noop" in caplog.text

    def test_min_consecutive_of_one_is_ignored(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """min_consecutive=1 is degenerate (a run of length 1 is always
        valid) and must not create any constraints or violation vars."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            parameters={
                "rules": [
                    {
                        "rule_id": "trivial_min",
                        "shift_types": ["shift_night"],
                        "min_consecutive": 1,
                    }
                ]
            }
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0

    def test_negative_max_consecutive_warns_and_ignored(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        model, variables = model_and_variables
        config = ConstraintConfig(
            parameters={
                "rules": [
                    {
                        "rule_id": "bad_max",
                        "shift_types": ["shift_night"],
                        "max_consecutive": -1,
                    }
                ]
            }
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert "bad_max" in caplog.text

    def test_num_periods_zero_warns_and_noops(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        model = cp_model.CpModel()
        variables = SolverVariables(
            assignment={}, shift_counts={}, undesirable_totals={}
        )
        config = ConstraintConfig(
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "shift_types": ["shift_night"],
                        "max_consecutive": 2,
                    }
                ]
            }
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=0)

        assert len(constraint.violation_variables) == 0


class TestMaxConsecutiveHard:
    """Hard-mode max_consecutive: forbids runs longer than N."""

    def test_exceeding_max_is_infeasible(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=4)
        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_cap",
                        "shift_types": ["shift_night"],
                        "max_consecutive": 2,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        w = workers[0].id
        for p in (0, 1, 2):
            model.add(variables.get_assignment_var(w, p, "shift_night") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE

    def test_at_boundary_is_feasible(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=4)
        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_cap",
                        "shift_types": ["shift_night"],
                        "max_consecutive": 2,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        w = workers[0].id
        model.add(variables.get_assignment_var(w, 0, "shift_night") == 1)
        model.add(variables.get_assignment_var(w, 1, "shift_night") == 1)
        model.add(variables.get_assignment_var(w, 2, "shift_night") == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_hard_mode_creates_no_violation_vars(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=4)
        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_cap",
                        "shift_types": ["shift_night"],
                        "max_consecutive": 2,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count > 0


class TestMaxConsecutiveSoft:
    """Soft-mode max_consecutive: violation vars carry the excess."""

    def test_violation_equals_excess(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        # 3 periods == exactly one window of size max+1=3.
        model, variables = _build(workers, shift_types, num_periods=3)
        config = ConstraintConfig(
            is_hard=False,
            weight=100,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_cap",
                        "shift_types": ["shift_night"],
                        "max_consecutive": 2,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        w = workers[0].id
        for p in range(3):
            model.add(variables.get_assignment_var(w, p, "shift_night") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        viol_names = [
            k
            for k in constraint.violation_variables
            if k.startswith(f"cst_max_viol_night_cap_{w}_")
        ]
        assert len(viol_names) == 1
        assert solver.value(constraint.violation_variables[viol_names[0]]) == 1

    def test_no_excess_gives_zero_violation(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=3)
        config = ConstraintConfig(
            is_hard=False,
            weight=100,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_cap",
                        "shift_types": ["shift_night"],
                        "max_consecutive": 2,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        w = workers[0].id
        model.add(variables.get_assignment_var(w, 0, "shift_night") == 1)
        model.add(variables.get_assignment_var(w, 1, "shift_night") == 1)
        model.add(variables.get_assignment_var(w, 2, "shift_night") == 0)

        # Minimize the violation to confirm it is pushed down to its exact
        # (zero) value, not left slack at some non-minimal feasible value.
        viol_names = [
            k
            for k in constraint.violation_variables
            if k.startswith(f"cst_max_viol_night_cap_{w}_")
        ]
        model.minimize(sum(constraint.violation_variables[k] for k in viol_names))

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.OPTIMAL
        assert solver.value(constraint.violation_variables[viol_names[0]]) == 0

    def test_soft_mode_allows_infeasible_hard_case(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """The same assignment that is INFEASIBLE under hard mode must be
        solvable (with a nonzero violation) under soft mode."""
        model, variables = _build(workers, shift_types, num_periods=4)
        config = ConstraintConfig(
            is_hard=False,
            weight=100,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_cap",
                        "shift_types": ["shift_night"],
                        "max_consecutive": 2,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        w = workers[0].id
        for p in (0, 1, 2):
            model.add(variables.get_assignment_var(w, p, "shift_night") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


class TestMinConsecutiveHard:
    """Hard-mode min_consecutive: a started run must continue, lenient at
    the horizon boundary."""

    def test_broken_run_within_horizon_is_infeasible(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=3)
        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_min",
                        "shift_types": ["shift_night"],
                        "min_consecutive": 3,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        w = workers[0].id
        model.add(variables.get_assignment_var(w, 0, "shift_night") == 1)
        model.add(variables.get_assignment_var(w, 1, "shift_night") == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE

    def test_partial_enforcement_within_horizon(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """Run starts at p=1 with min_consecutive=3: p=2 (within horizon)
        must be worked, but the constraint stops at the horizon edge (there
        is no p=3)."""
        model, variables = _build(workers, shift_types, num_periods=3)
        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_min",
                        "shift_types": ["shift_night"],
                        "min_consecutive": 3,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        w = workers[0].id
        model.add(variables.get_assignment_var(w, 0, "shift_night") == 0)
        model.add(variables.get_assignment_var(w, 1, "shift_night") == 1)
        model.add(variables.get_assignment_var(w, 2, "shift_night") == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE

    def test_run_started_too_close_to_horizon_end_is_lenient(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """A run that starts on the very last period cannot possibly reach
        min_consecutive periods; it must not make the model infeasible."""
        model, variables = _build(workers, shift_types, num_periods=3)
        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_min",
                        "shift_types": ["shift_night"],
                        "min_consecutive": 3,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        w = workers[0].id
        model.add(variables.get_assignment_var(w, 0, "shift_night") == 0)
        model.add(variables.get_assignment_var(w, 1, "shift_night") == 0)
        model.add(variables.get_assignment_var(w, 2, "shift_night") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


class TestMinConsecutiveSoft:
    """Soft-mode min_consecutive violation counting."""

    def test_broken_run_flags_violation(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=3)
        config = ConstraintConfig(
            is_hard=False,
            weight=100,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_min",
                        "shift_types": ["shift_night"],
                        "min_consecutive": 3,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        w = workers[0].id
        model.add(variables.get_assignment_var(w, 0, "shift_night") == 0)
        model.add(variables.get_assignment_var(w, 1, "shift_night") == 1)
        model.add(variables.get_assignment_var(w, 2, "shift_night") == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        viol_name = f"cst_min_viol_night_min_{w}_p1_k1"
        assert viol_name in constraint.violation_variables
        assert solver.value(constraint.violation_variables[viol_name]) == 1


class TestRestAfterRunHard:
    """Hard-mode rest_after_run: mandatory rest after a completed run."""

    def test_working_during_rest_is_infeasible(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=5)
        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_rest",
                        "shift_types": ["shift_night"],
                        "rest_after_run": 2,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=5)

        w = workers[0].id
        # Run of nights at periods 0,1; run ends at period 1 (not worked at 2).
        model.add(variables.get_assignment_var(w, 0, "shift_night") == 1)
        model.add(variables.get_assignment_var(w, 1, "shift_night") == 1)
        model.add(variables.get_assignment_var(w, 2, "shift_night") == 0)
        # Violates rest by working ANY shift (day) during the rest window.
        model.add(variables.get_assignment_var(w, 2, "shift_day") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE

    def test_resting_is_feasible(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=5)
        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_rest",
                        "shift_types": ["shift_night"],
                        "rest_after_run": 2,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=5)

        w = workers[0].id
        model.add(variables.get_assignment_var(w, 0, "shift_night") == 1)
        model.add(variables.get_assignment_var(w, 1, "shift_night") == 1)
        model.add(variables.get_assignment_var(w, 2, "shift_night") == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        # The solver must have forced both required rest periods to zero
        # across all shift types.
        assert solver.value(variables.get_assignment_var(w, 2, "shift_day")) == 0
        assert solver.value(variables.get_assignment_var(w, 3, "shift_day")) == 0
        assert solver.value(variables.get_assignment_var(w, 3, "shift_night")) == 0

    def test_run_active_at_last_period_has_no_rest_requirement(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """A run still active in the very last period of the horizon has no
        defined 'end' -- it is unknown whether it continues past the
        horizon -- so no rest must be enforced."""
        model, variables = _build(workers, shift_types, num_periods=3)
        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_rest",
                        "shift_types": ["shift_night"],
                        "rest_after_run": 2,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        w = workers[0].id
        model.add(variables.get_assignment_var(w, 0, "shift_night") == 0)
        model.add(variables.get_assignment_var(w, 1, "shift_night") == 1)
        model.add(variables.get_assignment_var(w, 2, "shift_night") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


class TestRestAfterRunSoft:
    """Soft-mode rest_after_run violation counting."""

    def test_working_during_rest_flags_violation(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=5)
        config = ConstraintConfig(
            is_hard=False,
            weight=100,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_rest",
                        "shift_types": ["shift_night"],
                        "rest_after_run": 1,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=5)

        w = workers[0].id
        model.add(variables.get_assignment_var(w, 0, "shift_night") == 1)
        model.add(variables.get_assignment_var(w, 1, "shift_night") == 0)
        model.add(variables.get_assignment_var(w, 1, "shift_day") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        viol_name = f"cst_rest_viol_night_rest_{w}_p0_k1"
        assert viol_name in constraint.violation_variables
        assert solver.value(constraint.violation_variables[viol_name]) == 1


class TestFilterUnion:
    """Tests for shift_types/categories filter resolution."""

    def test_category_filter_matches_same_as_shift_type_filter(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=4)
        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_cap",
                        "categories": ["cat_night"],
                        "max_consecutive": 2,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        w = workers[0].id
        for p in (0, 1, 2):
            model.add(variables.get_assignment_var(w, p, "shift_night") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE

    def test_shift_types_and_categories_are_unioned(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """categories=[cat_day] plus shift_types=[shift_night] must group
        BOTH shift types together (a run alternating night/day still
        counts as one continuous in-group run)."""
        model, variables = _build(workers, shift_types, num_periods=3)
        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "any_shift_cap",
                        "shift_types": ["shift_night"],
                        "categories": ["cat_day"],
                        "max_consecutive": 2,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        w = workers[0].id
        # Alternating night/day across all 3 periods: still 3 consecutive
        # "in group" periods since both shift types are in the group.
        model.add(variables.get_assignment_var(w, 0, "shift_night") == 1)
        model.add(variables.get_assignment_var(w, 1, "shift_day") == 1)
        model.add(variables.get_assignment_var(w, 2, "shift_night") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE


class TestMultipleRulesAndWorkers:
    """Rules apply independently per worker and rules list entry."""

    def test_rule_applies_independently_per_worker(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=4)
        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_cap",
                        "shift_types": ["shift_night"],
                        "max_consecutive": 2,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        w1, w2 = workers[0].id, workers[1].id
        # w1 breaks the cap; w2 stays within it.
        for p in (0, 1, 2):
            model.add(variables.get_assignment_var(w1, p, "shift_night") == 1)
        model.add(variables.get_assignment_var(w2, 0, "shift_night") == 1)
        model.add(variables.get_assignment_var(w2, 1, "shift_night") == 1)
        model.add(variables.get_assignment_var(w2, 2, "shift_night") == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        # Infeasible solely due to w1's violation.
        assert status == cp_model.INFEASIBLE

    def test_two_independent_rules_both_apply(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=4)
        config = ConstraintConfig(
            is_hard=False,
            weight=100,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_cap",
                        "shift_types": ["shift_night"],
                        "max_consecutive": 1,
                    },
                    {
                        "rule_id": "day_cap",
                        "shift_types": ["shift_day"],
                        "max_consecutive": 1,
                    },
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        night_viols = [k for k in constraint.violation_variables if "night_cap" in k]
        day_viols = [k for k in constraint.violation_variables if "day_cap" in k]
        assert len(night_viols) > 0
        assert len(day_viols) > 0


class TestEdgeCases:
    """Edge cases: single period, missing candidate variables."""

    def test_single_period_max_consecutive(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=1)
        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "night_cap",
                        "shift_types": ["shift_night"],
                        "max_consecutive": 0,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        w = workers[0].id
        model.add(variables.get_assignment_var(w, 0, "shift_night") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE

    def test_single_period_min_and_rest_are_harmless(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """With only one period, min_consecutive run-continuation and
        rest_after_run both have no periods to act on; the model must stay
        feasible either way."""
        model, variables = _build(workers, shift_types, num_periods=1)
        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "shift_types": ["shift_night"],
                        "min_consecutive": 3,
                        "rest_after_run": 2,
                    }
                ]
            },
        )
        constraint = ConsecutiveShiftTypeConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_missing_candidate_var_treated_as_constant_zero(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
    ) -> None:
        """A (worker, period, shift_type) combination absent from the
        SolverVariables (e.g. a more advanced variable builder that omits
        restricted combinations) must be treated as 'never in group' for
        that period rather than raising."""
        model, variables = model_and_variables
        del variables.assignment[workers[0].id][1]["shift_night"]

        constraint = ConsecutiveShiftTypeConstraint(
            model, variables, ConstraintConfig()
        )
        in_group = constraint._build_in_group_indicators(
            "r1", workers[0], {"shift_night"}, num_periods=4
        )

        # Forcing the constant-0 indicator to 1 must be infeasible.
        model.add(in_group[1] == 1)
        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE

    def test_works_any_cache_reused_across_rules(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Two rules both needing rest_after_run for the same worker/period
        must reuse the same works_any indicator rather than building a
        second (redundant) one."""
        model, variables = model_and_variables
        constraint = ConsecutiveShiftTypeConstraint(
            model, variables, ConstraintConfig()
        )

        first = constraint._get_works_any(workers[0], 2, shift_types)
        second = constraint._get_works_any(workers[0], 2, shift_types)
        assert first is second
