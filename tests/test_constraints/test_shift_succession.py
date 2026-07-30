"""Tests for shift succession constraint."""

import logging
from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.shift_succession import ShiftSuccessionConstraint
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
    """Create shift types: an early/day shift and a night shift."""
    return [
        ShiftType(
            id="shift_night",
            name="Night Shift",
            category="cat_night",
            start_time=time(23, 0),
            end_time=time(7, 0),
            duration_hours=8.0,
            workers_required=1,
        ),
        ShiftType(
            id="shift_early",
            name="Early Shift",
            category="cat_day",
            start_time=time(5, 0),
            end_time=time(13, 0),
            duration_hours=8.0,
            workers_required=1,
        ),
        ShiftType(
            id="shift_late",
            name="Late Shift",
            category="cat_day",
            start_time=time(13, 0),
            end_time=time(21, 0),
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


def night_then_early_rule(**overrides: object) -> dict:
    """Build a standard 'no early shift after night shift' rule dict."""
    rule = {
        "rule_id": "no_early_after_night",
        "from_type": "shift_type",
        "from_value": "shift_night",
        "to_type": "shift_type",
        "to_value": "shift_early",
        "gap_periods": 1,
    }
    rule.update(overrides)
    return rule


class TestShiftSuccessionConstraintInit:
    """Tests for ShiftSuccessionConstraint initialization."""

    def test_init_default_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Test initialization with default config uses BaseConstraint defaults."""
        model, variables = model_and_variables
        constraint = ShiftSuccessionConstraint(model, variables)

        assert constraint.constraint_id == "shift_succession"
        assert constraint.handles_hard_mode is True
        assert constraint.is_enabled
        assert constraint.is_hard
        assert constraint.weight == 100

    def test_init_soft_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Test initialization with explicit soft config."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=50)
        constraint = ShiftSuccessionConstraint(model, variables, config)

        assert not constraint.is_hard
        assert constraint.weight == 50


class TestShiftSuccessionNoOpPaths:
    """Tests for warn + no-op edge cases."""

    def test_disabled_does_nothing(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Disabled constraint adds no constraints regardless of rules."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=False, parameters={"rules": [night_then_early_rule()]}
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0

    def test_missing_rules_param_warns_and_no_ops(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """No parameters at all -> warn and no-op."""
        model, variables = model_and_variables
        constraint = ShiftSuccessionConstraint(model, variables)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0
        assert "shift_succession" in caplog.text.lower()

    def test_empty_rules_list_warns_and_no_ops(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Empty rules list -> no-op (same as missing)."""
        model, variables = model_and_variables
        config = ConstraintConfig(parameters={"rules": []})
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0

    def test_single_period_warns_and_no_ops(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """num_periods=1 cannot have any from/to transition -> warn + no-op."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(parameters={"rules": [night_then_early_rule()]})
        constraint = ShiftSuccessionConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0
        assert "shift_succession" in caplog.text.lower()

    def test_unknown_shift_type_reference_skips_rule(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A rule referencing a nonexistent shift type id is skipped with a warning."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            parameters={"rules": [night_then_early_rule(from_value="shift_unknown")]}
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0
        assert "shift_unknown" in caplog.text

    def test_unknown_category_reference_skips_rule(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A rule referencing a nonexistent category is skipped with a warning."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            parameters={
                "rules": [
                    night_then_early_rule(to_type="category", to_value="cat_unknown")
                ]
            }
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0
        assert "cat_unknown" in caplog.text

    def test_invalid_filter_type_skips_rule(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A rule with an invalid from_type/to_type is skipped with a warning."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            parameters={"rules": [night_then_early_rule(from_type="bogus")]}
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0

    def test_missing_rule_id_skips_rule(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A rule dict missing rule_id is skipped with a warning."""
        model, variables = model_and_variables
        bad_rule = night_then_early_rule()
        del bad_rule["rule_id"]
        config = ConstraintConfig(parameters={"rules": [bad_rule]})
        constraint = ShiftSuccessionConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0

    def test_non_dict_rule_skips_rule(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A malformed (non-dict) rule entry is skipped with a warning."""
        model, variables = model_and_variables
        config = ConstraintConfig(parameters={"rules": ["not-a-dict"]})
        constraint = ShiftSuccessionConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0

    def test_gap_periods_zero_skips_rule(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """gap_periods=0 is invalid (must be >= 1) -> skip with warning."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            parameters={"rules": [night_then_early_rule(gap_periods=0)]}
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0

    def test_gap_periods_exceeds_horizon_skips_rule(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """gap_periods >= num_periods -> skip with warning."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            parameters={"rules": [night_then_early_rule(gap_periods=4)]}
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0
        assert "gap_periods" in caplog.text.lower()

    def test_gap_periods_equal_to_horizon_skips_rule(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """gap_periods == num_periods is also invalid (boundary check)."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            parameters={"rules": [night_then_early_rule(gap_periods=4)]}
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0

    def test_one_valid_rule_and_one_invalid_rule_only_valid_applies(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """An invalid rule alongside a valid one only skips the invalid one."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={
                "rules": [
                    night_then_early_rule(),
                    night_then_early_rule(
                        rule_id="bad_rule", from_value="shift_unknown"
                    ),
                ]
            },
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Only the valid rule should have produced violation variables, and
        # none should reference the bad rule id.
        assert len(constraint.violation_variables) > 0
        assert all("bad_rule" not in name for name in constraint.violation_variables)


class TestShiftSuccessionHardMode:
    """Tests for per-rule hard enforcement."""

    def test_hard_rule_forbids_transition(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Hard rule makes night-then-early infeasible when forced."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"rules": [night_then_early_rule()]}
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0

        # Force worker_1: night shift in period 0, early shift in period 1.
        model.add(variables.get_assignment_var("worker_1", 0, "shift_night") == 1)
        model.add(variables.get_assignment_var("worker_1", 1, "shift_early") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE

    def test_hard_rule_allows_non_matching_transition(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Hard rule does not forbid transitions outside the rule's filters."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"rules": [night_then_early_rule()]}
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Night shift followed by late shift is not covered by the rule.
        model.add(variables.get_assignment_var("worker_1", 0, "shift_night") == 1)
        model.add(variables.get_assignment_var("worker_1", 1, "shift_late") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_hard_rule_boundary_only_one_side_assigned_is_feasible(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Only the 'from' or only the 'to' side assigned is feasible (boundary)."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"rules": [night_then_early_rule()]}
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        model.add(variables.get_assignment_var("worker_1", 0, "shift_night") == 1)
        model.add(variables.get_assignment_var("worker_1", 1, "shift_early") == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_hard_rule_creates_no_violation_variables(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Hard rules never populate violation_variables/violation_priorities."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"rules": [night_then_early_rule()]}
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0
        assert len(constraint.violation_priorities) == 0
        assert constraint.constraint_count > 0

    def test_category_to_category_hard_rule(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Category filters match any shift type in that category."""
        model, variables = model_and_variables
        rule = {
            "rule_id": "no_day_after_day",
            "from_type": "category",
            "from_value": "cat_day",
            "to_type": "category",
            "to_value": "cat_day",
            "gap_periods": 1,
        }
        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"rules": [rule]}
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # shift_early (cat_day) then shift_late (cat_day) should be forbidden
        # even though the shift type ids differ.
        model.add(variables.get_assignment_var("worker_1", 0, "shift_early") == 1)
        model.add(variables.get_assignment_var("worker_1", 1, "shift_late") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE


class TestShiftSuccessionSoftMode:
    """Tests for per-rule soft penalty counting."""

    def test_soft_rule_creates_violation_variable(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Soft rule creates violation variables with the configured priority."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={"rules": [night_then_early_rule(priority=3)]},
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) > 0
        assert all(p == 3 for p in constraint.violation_priorities.values())

    def test_soft_violation_is_one_when_transition_forced(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Forcing the from/to transition drives the violation var to 1."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True, is_hard=False, parameters={"rules": [night_then_early_rule()]}
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        model.add(variables.get_assignment_var("worker_1", 0, "shift_night") == 1)
        model.add(variables.get_assignment_var("worker_1", 1, "shift_early") == 1)

        viol_name = "succ_viol_worker_1_no_early_after_night_p0"
        assert viol_name in constraint.violation_variables

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert solver.value(constraint.violation_variables[viol_name]) == 1

    def test_soft_violation_is_zero_when_minimized_and_avoidable(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Minimizing the objective drives violations to 0 when avoidable."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"rules": [night_then_early_rule()]},
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        model.add(variables.get_assignment_var("worker_1", 0, "shift_night") == 1)

        penalty_terms = [
            viol_var * constraint.violation_priorities[name] * config.weight
            for name, viol_var in constraint.violation_variables.items()
        ]
        model.minimize(sum(penalty_terms))

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        assert (
            solver.value(variables.get_assignment_var("worker_1", 1, "shift_early"))
            == 0
        )

        viol_name = "succ_viol_worker_1_no_early_after_night_p0"
        assert solver.value(constraint.violation_variables[viol_name]) == 0

    def test_objective_counts_penalty_with_priority_and_weight(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Objective value reflects violation * priority * weight when forced."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=10,
            parameters={"rules": [night_then_early_rule(priority=4)]},
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Force the violation for worker_1 at period 0; leave worker_2 free
        # (coverage isn't modeled, so this stays feasible).
        model.add(variables.get_assignment_var("worker_1", 0, "shift_night") == 1)
        model.add(variables.get_assignment_var("worker_1", 1, "shift_early") == 1)

        penalty_terms = [
            viol_var * constraint.violation_priorities[name] * config.weight
            for name, viol_var in constraint.violation_variables.items()
        ]
        model.minimize(sum(penalty_terms))

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        viol_name = "succ_viol_worker_1_no_early_after_night_p0"
        assert solver.value(constraint.violation_variables[viol_name]) == 1
        # Only one violation is forced (worker_1/p0); objective == priority*weight.
        assert solver.objective_value == 4 * 10

    def test_soft_rule_gap_periods_two(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """gap_periods=2 checks period p against period p+2, not p+1."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        rule = night_then_early_rule(gap_periods=2)
        config = ConstraintConfig(
            enabled=True, is_hard=False, parameters={"rules": [rule]}
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Night at period 0, early at period 1 (gap=1, not covered by this
        # gap=2 rule) should NOT trigger p0's violation variable.
        model.add(variables.get_assignment_var("worker_1", 0, "shift_night") == 1)
        model.add(variables.get_assignment_var("worker_1", 1, "shift_early") == 1)
        model.add(variables.get_assignment_var("worker_1", 2, "shift_early") == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        viol_name = "succ_viol_worker_1_no_early_after_night_p0"
        assert solver.value(constraint.violation_variables[viol_name]) == 0


class TestShiftSuccessionPerRuleHardSoft:
    """Tests for per-rule is_hard override semantics."""

    def test_rule_is_hard_none_inherits_global_soft(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """rule.is_hard=None with global config is_hard=False -> soft."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={"rules": [night_then_early_rule(is_hard=None)]},
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) > 0

    def test_rule_is_hard_none_inherits_global_hard(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """rule.is_hard=None with global config is_hard=True -> hard."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=True,
            parameters={"rules": [night_then_early_rule(is_hard=None)]},
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0

    def test_rule_hard_overrides_global_soft(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """rule.is_hard=True overrides global config is_hard=False."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={"rules": [night_then_early_rule(is_hard=True)]},
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) == 0

        model.add(variables.get_assignment_var("worker_1", 0, "shift_night") == 1)
        model.add(variables.get_assignment_var("worker_1", 1, "shift_early") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE

    def test_rule_soft_overrides_global_hard(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """rule.is_hard=False overrides global config is_hard=True."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=True,
            parameters={"rules": [night_then_early_rule(is_hard=False)]},
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert len(constraint.violation_variables) > 0

        model.add(variables.get_assignment_var("worker_1", 0, "shift_night") == 1)
        model.add(variables.get_assignment_var("worker_1", 1, "shift_early") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_mixed_hard_and_soft_rules(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """One hard rule and one soft rule coexist correctly."""
        model, variables = model_and_variables
        rules = [
            night_then_early_rule(rule_id="hard_rule", is_hard=True),
            {
                "rule_id": "soft_rule",
                "from_type": "shift_type",
                "from_value": "shift_early",
                "to_type": "shift_type",
                "to_value": "shift_late",
                "gap_periods": 1,
                "is_hard": False,
                "priority": 2,
            },
        ]
        config = ConstraintConfig(
            enabled=True, is_hard=False, parameters={"rules": rules}
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Only the soft rule should have produced violation variables.
        assert len(constraint.violation_variables) > 0
        assert all("soft_rule" in name for name in constraint.violation_variables)

        # Hard rule (night -> early) must still be enforced.
        model.add(variables.get_assignment_var("worker_1", 0, "shift_night") == 1)
        model.add(variables.get_assignment_var("worker_1", 1, "shift_early") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE


class TestShiftSuccessionEdgeCases:
    """Miscellaneous edge cases."""

    def test_worker_never_matching_from_shift_produces_no_constraints_for_that_worker(
        self,
        shift_types: list[ShiftType],
    ) -> None:
        """A worker with no assignment vars for the from-filter shift is skipped."""
        model = cp_model.CpModel()
        # Single shift type only relevant to the 'to' side; 'from' side
        # (shift_night) won't exist for any worker in this restricted model.
        limited_shift_types = [st for st in shift_types if st.id != "shift_night"]
        workers = [Worker(id="worker_1", name="Worker 1")]
        builder = VariableBuilder(model, workers, limited_shift_types, num_periods=4)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={"rules": [night_then_early_rule()]},
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(
            workers=workers, shift_types=limited_shift_types, num_periods=4
        )

        # from_value 'shift_night' doesn't exist among limited_shift_types,
        # so the rule is skipped entirely (unknown shift type reference).
        assert len(constraint.violation_variables) == 0

    def test_two_periods_minimum_horizon(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """num_periods=2 is the minimum horizon that allows a gap=1 rule."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=2)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={"rules": [night_then_early_rule()]},
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=2)

        assert len(constraint.violation_variables) > 0

    def test_priority_default_is_one(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Priority defaults to 1 when omitted from the rule dict."""
        model, variables = model_and_variables
        rule = night_then_early_rule()
        assert "priority" not in rule
        config = ConstraintConfig(
            enabled=True, is_hard=False, parameters={"rules": [rule]}
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        assert all(p == 1 for p in constraint.violation_priorities.values())

    def test_gap_periods_default_is_one(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """gap_periods defaults to 1 when omitted from the rule dict."""
        model, variables = model_and_variables
        rule = {
            "rule_id": "default_gap",
            "from_type": "shift_type",
            "from_value": "shift_night",
            "to_type": "shift_type",
            "to_value": "shift_early",
        }
        assert "gap_periods" not in rule
        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"rules": [rule]}
        )
        constraint = ShiftSuccessionConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        model.add(variables.get_assignment_var("worker_1", 0, "shift_night") == 1)
        model.add(variables.get_assignment_var("worker_1", 1, "shift_early") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE
