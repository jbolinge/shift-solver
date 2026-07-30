"""Tests for worker pairing constraint (apart / together rules)."""

import logging
from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.worker_pairing import WorkerPairingConstraint
from shift_solver.models import ShiftType, Worker
from shift_solver.solver.types import SolverVariables
from shift_solver.solver.variable_builder import VariableBuilder


@pytest.fixture
def workers() -> list[Worker]:
    """Create test workers."""
    return [
        Worker(id="worker_1", name="Worker One"),
        Worker(id="worker_2", name="Worker Two"),
        Worker(id="worker_3", name="Worker Three"),
    ]


@pytest.fixture
def shift_types() -> list[ShiftType]:
    """Create shift types."""
    return [
        ShiftType(
            id="shift_day",
            name="Day Shift",
            category="cat_a",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=2,
        ),
        ShiftType(
            id="shift_night",
            name="Night Shift",
            category="cat_b",
            start_time=time(23, 0),
            end_time=time(7, 0),
            duration_hours=8.0,
            workers_required=2,
        ),
    ]


@pytest.fixture
def model_and_variables(
    workers: list[Worker], shift_types: list[ShiftType]
) -> tuple[cp_model.CpModel, SolverVariables]:
    """Create model and variables for testing (3 periods)."""
    model = cp_model.CpModel()
    builder = VariableBuilder(model, workers, shift_types, num_periods=3)
    variables = builder.build()
    return model, variables


def _add_coverage(
    model: cp_model.CpModel,
    variables: SolverVariables,
    workers: list[Worker],
    shift_types: list[ShiftType],
    num_periods: int,
) -> None:
    """Add exact-headcount coverage constraints for every shift/period."""
    for period in range(num_periods):
        for shift_type in shift_types:
            vars_for_shift = [
                variables.get_assignment_var(w.id, period, shift_type.id)
                for w in workers
            ]
            model.add(sum(vars_for_shift) == shift_type.workers_required)


class TestWorkerPairingConstraintInit:
    """Tests for WorkerPairingConstraint initialization."""

    def test_init_default_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Default config uses BaseConstraint defaults."""
        model, variables = model_and_variables
        constraint = WorkerPairingConstraint(model, variables)

        assert constraint.constraint_id == "worker_pairing"
        assert constraint.is_enabled
        assert constraint.is_hard
        assert constraint.handles_hard_mode


class TestWorkerPairingConstraintApplyValidation:
    """Tests for rule validation / skip-with-warning behavior."""

    def test_apply_disabled_does_nothing(
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
                        "type": "apart",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        assert constraint.constraint_count == 0

    def test_apply_no_rules_param_warns_and_no_ops(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        model, variables = model_and_variables
        constraint = WorkerPairingConstraint(model, variables)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        assert constraint.constraint_count == 0
        assert "worker_pairing" in caplog.text.lower()

    @pytest.mark.parametrize(
        ("rule", "expected_substring"),
        [
            ("not_a_dict", "expected a dict"),
            (
                {"type": "apart", "worker_a": "worker_1", "worker_b": "worker_2"},
                "rule_id",
            ),
            (
                {
                    "rule_id": "r1",
                    "type": "bogus",
                    "worker_a": "worker_1",
                    "worker_b": "worker_2",
                },
                "type must be one of",
            ),
            (
                {
                    "rule_id": "r1",
                    "type": "apart",
                    "worker_a": "unknown",
                    "worker_b": "worker_2",
                },
                "unknown worker_a",
            ),
            (
                {
                    "rule_id": "r1",
                    "type": "apart",
                    "worker_a": "worker_1",
                    "worker_b": "unknown",
                },
                "unknown worker_b",
            ),
            (
                {
                    "rule_id": "r1",
                    "type": "apart",
                    "worker_a": "worker_1",
                    "worker_b": "worker_1",
                },
                "are both",
            ),
            (
                {
                    "rule_id": "r1",
                    "type": "apart",
                    "worker_a": "worker_1",
                    "worker_b": "worker_2",
                    "shift_types": ["not_a_real_shift"],
                },
                "empty after validation",
            ),
        ],
    )
    def test_apply_skips_invalid_rule_with_warning(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
        rule: object,
        expected_substring: str,
    ) -> None:
        model, variables = model_and_variables
        config = ConstraintConfig(parameters={"rules": [rule]})
        constraint = WorkerPairingConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        assert constraint.constraint_count == 0
        assert expected_substring in caplog.text.lower()

    def test_apply_unknown_shift_type_dropped_but_rule_still_applies(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A mix of known+unknown shift ids drops the unknown one and keeps going."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "apart",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                        "shift_types": ["shift_day", "not_a_real_shift"],
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        assert "dropping unknown shift_types" in caplog.text.lower()
        # Still applied for shift_day across all 3 periods.
        assert constraint.constraint_count == 3


class TestApartRule:
    """Tests for type='apart' rules."""

    def test_hard_apart_creates_no_violation_vars(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        model, variables = model_and_variables
        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "apart",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        assert len(constraint.violation_variables) == 0
        # 3 periods * 2 shift types = 6 constraints
        assert constraint.constraint_count == 6

    def test_hard_apart_enforced_in_solve(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Hard apart rule: a and b never share a shift+period."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=3)
        variables = builder.build()

        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "apart",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        _add_coverage(model, variables, workers, shift_types, 3)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        for period in range(3):
            for st in shift_types:
                a = solver.value(
                    variables.get_assignment_var("worker_1", period, st.id)
                )
                b = solver.value(
                    variables.get_assignment_var("worker_2", period, st.id)
                )
                assert a + b <= 1

    def test_hard_apart_infeasible_when_forced_together(
        self,
        shift_types: list[ShiftType],
    ) -> None:
        """With only 2 workers and workers_required=2, apart is infeasible."""
        model = cp_model.CpModel()
        two_workers = [
            Worker(id="worker_1", name="Worker One"),
            Worker(id="worker_2", name="Worker Two"),
        ]
        builder = VariableBuilder(model, two_workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "apart",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                        "shift_types": ["shift_day"],
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=two_workers, shift_types=shift_types, num_periods=1)

        # Both workers required on shift_day (workers_required=2), but the
        # apart rule forbids them sharing it -- infeasible.
        vars_for_shift = [
            variables.get_assignment_var(w.id, 0, "shift_day") for w in two_workers
        ]
        model.add(sum(vars_for_shift) == 2)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE

    def test_soft_apart_violation_matches_assignment(
        self,
        shift_types: list[ShiftType],
    ) -> None:
        """Soft apart: violation var is forced to 1 when both are assigned."""
        model = cp_model.CpModel()
        two_workers = [
            Worker(id="worker_1", name="Worker One"),
            Worker(id="worker_2", name="Worker Two"),
        ]
        builder = VariableBuilder(model, two_workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(
            is_hard=False,
            weight=100,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "apart",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                        "shift_types": ["shift_day"],
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=two_workers, shift_types=shift_types, num_periods=1)

        assert len(constraint.violation_variables) == 1
        viol_var = next(iter(constraint.violation_variables.values()))

        # Force both onto shift_day -- worker_required=2 forces exactly this.
        model.add(variables.get_assignment_var("worker_1", 0, "shift_day") == 1)
        model.add(variables.get_assignment_var("worker_2", 0, "shift_day") == 1)
        model.minimize(viol_var)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert solver.value(viol_var) == 1

    def test_soft_apart_violation_zero_when_not_both_assigned(
        self,
        shift_types: list[ShiftType],
    ) -> None:
        """Soft apart: violation minimizes to 0 when workers aren't forced together."""
        model = cp_model.CpModel()
        two_workers = [
            Worker(id="worker_1", name="Worker One"),
            Worker(id="worker_2", name="Worker Two"),
        ]
        builder = VariableBuilder(model, two_workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(
            is_hard=False,
            weight=100,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "apart",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                        "shift_types": ["shift_day"],
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=two_workers, shift_types=shift_types, num_periods=1)

        viol_var = next(iter(constraint.violation_variables.values()))
        model.add(variables.get_assignment_var("worker_1", 0, "shift_day") == 0)
        model.add(variables.get_assignment_var("worker_2", 0, "shift_day") == 0)
        model.minimize(viol_var)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert solver.value(viol_var) == 0

    def test_apart_scoped_to_shift_types_only(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """When shift_types scope excludes a shift, sharing it is unconstrained."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "apart",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                        "shift_types": ["shift_day"],
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        # Force both onto shift_night -- out of scope, should be permitted.
        model.add(variables.get_assignment_var("worker_1", 0, "shift_night") == 1)
        model.add(variables.get_assignment_var("worker_2", 0, "shift_night") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


class TestTogetherRule:
    """Tests for type='together' (tutorship) rules."""

    def test_hard_together_creates_no_violation_vars(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        model, variables = model_and_variables
        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "together",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count > 0

    def test_hard_together_forces_b_when_a_works(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Hard together: worker_b must work whenever worker_a works."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "together",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        # Force worker_1 onto shift_day; worker_3 fills the other day slot;
        # worker_2 must therefore be forced onto some shift this period.
        model.add(variables.get_assignment_var("worker_1", 0, "shift_day") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        b_day = solver.value(variables.get_assignment_var("worker_2", 0, "shift_day"))
        b_night = solver.value(
            variables.get_assignment_var("worker_2", 0, "shift_night")
        )
        assert b_day + b_night >= 1

    def test_hard_together_infeasible_when_b_cannot_work(
        self,
        shift_types: list[ShiftType],
    ) -> None:
        """Infeasible if a is forced to work but b is forced off every scope shift."""
        model = cp_model.CpModel()
        two_workers = [
            Worker(id="worker_1", name="Worker One"),
            Worker(id="worker_2", name="Worker Two"),
        ]
        builder = VariableBuilder(model, two_workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "together",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                        "shift_types": ["shift_day"],
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=two_workers, shift_types=shift_types, num_periods=1)

        model.add(variables.get_assignment_var("worker_1", 0, "shift_day") == 1)
        model.add(variables.get_assignment_var("worker_2", 0, "shift_day") == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE

    def test_soft_together_violation_one_when_b_absent(
        self,
        shift_types: list[ShiftType],
    ) -> None:
        """Soft together: violation forced to 1 when a works and b does not."""
        model = cp_model.CpModel()
        two_workers = [
            Worker(id="worker_1", name="Worker One"),
            Worker(id="worker_2", name="Worker Two"),
        ]
        builder = VariableBuilder(model, two_workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(
            is_hard=False,
            weight=100,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "together",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                        "shift_types": ["shift_day"],
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=two_workers, shift_types=shift_types, num_periods=1)

        viol_var = next(iter(constraint.violation_variables.values()))
        model.add(variables.get_assignment_var("worker_1", 0, "shift_day") == 1)
        model.add(variables.get_assignment_var("worker_2", 0, "shift_day") == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert solver.value(viol_var) == 1

    def test_soft_together_violation_zero_when_both_work(
        self,
        shift_types: list[ShiftType],
    ) -> None:
        """Soft together: violation minimizes to 0 when b also works."""
        model = cp_model.CpModel()
        two_workers = [
            Worker(id="worker_1", name="Worker One"),
            Worker(id="worker_2", name="Worker Two"),
        ]
        builder = VariableBuilder(model, two_workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(
            is_hard=False,
            weight=100,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "together",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                        "shift_types": ["shift_day"],
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=two_workers, shift_types=shift_types, num_periods=1)

        viol_var = next(iter(constraint.violation_variables.values()))
        model.add(variables.get_assignment_var("worker_1", 0, "shift_day") == 1)
        model.add(variables.get_assignment_var("worker_2", 0, "shift_day") == 1)
        model.minimize(viol_var)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert solver.value(viol_var) == 0

    def test_together_a_absent_never_violates(
        self,
        shift_types: list[ShiftType],
    ) -> None:
        """When a doesn't work at all, b is unconstrained (no violation possible)."""
        model = cp_model.CpModel()
        two_workers = [
            Worker(id="worker_1", name="Worker One"),
            Worker(id="worker_2", name="Worker Two"),
        ]
        builder = VariableBuilder(model, two_workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "together",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                        "shift_types": ["shift_day"],
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=two_workers, shift_types=shift_types, num_periods=1)

        model.add(variables.get_assignment_var("worker_1", 0, "shift_day") == 0)
        model.add(variables.get_assignment_var("worker_2", 0, "shift_day") == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


class TestPerRuleHardSoft:
    """Tests for per-rule is_hard override (handles_hard_mode semantics)."""

    def test_is_hard_none_falls_back_to_global_soft(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        model, variables = model_and_variables
        config = ConstraintConfig(
            is_hard=False,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "apart",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                        "is_hard": None,
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        assert len(constraint.violation_variables) > 0

    def test_per_rule_hard_overrides_global_soft(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        model, variables = model_and_variables
        config = ConstraintConfig(
            is_hard=False,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "apart",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                        "is_hard": True,
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        assert len(constraint.violation_variables) == 0

    def test_per_rule_soft_overrides_global_hard(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        model, variables = model_and_variables
        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "apart",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                        "is_hard": False,
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        assert len(constraint.violation_variables) > 0

    def test_mixed_hard_soft_rules(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """One hard apart rule + one soft together rule in the same apply()."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(
            is_hard=False,
            weight=100,
            parameters={
                "rules": [
                    {
                        "rule_id": "hard_apart",
                        "type": "apart",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                        "shift_types": ["shift_day"],
                        "is_hard": True,
                    },
                    {
                        "rule_id": "soft_together",
                        "type": "together",
                        "worker_a": "worker_1",
                        "worker_b": "worker_3",
                        "shift_types": ["shift_day"],
                        "is_hard": False,
                    },
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        # Only the soft rule contributes a violation var.
        assert len(constraint.violation_variables) == 1

        model.add(variables.get_assignment_var("worker_1", 0, "shift_day") == 1)
        model.add(variables.get_assignment_var("worker_2", 0, "shift_day") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        # Hard apart rule between worker_1/worker_2 on shift_day is violated
        # by construction -> infeasible.
        assert status == cp_model.INFEASIBLE


class TestPriorityMetadata:
    """Tests for priority multiplier metadata storage."""

    def test_priority_stored_for_apart_violation(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        model, variables = model_and_variables
        config = ConstraintConfig(
            is_hard=False,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "apart",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                        "priority": 5,
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        assert len(constraint.violation_priorities) > 0
        assert all(p == 5 for p in constraint.violation_priorities.values())

    def test_priority_defaults_to_one(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        model, variables = model_and_variables
        config = ConstraintConfig(
            is_hard=False,
            parameters={
                "rules": [
                    {
                        "rule_id": "r1",
                        "type": "together",
                        "worker_a": "worker_1",
                        "worker_b": "worker_2",
                    }
                ]
            },
        )
        constraint = WorkerPairingConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        assert all(p == 1 for p in constraint.violation_priorities.values())
