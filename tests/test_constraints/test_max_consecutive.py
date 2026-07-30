"""Tests for max_consecutive constraint."""

import logging
from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.max_consecutive import MaxConsecutiveConstraint
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
    """Create shift types spanning two categories."""
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


def _pin_non_auxiliary_to_zero(
    model: cp_model.CpModel, constraint: MaxConsecutiveConstraint
) -> None:
    """Emulate ShiftSolver's generic hard-mode enforcement: force every
    non-auxiliary violation variable to 0."""
    for name, var in constraint.violation_variables.items():
        if constraint.violation_variable_types.get(name, "violation") != "auxiliary":
            model.add(var == 0)


def _build(
    workers: list[Worker], shift_types: list[ShiftType], num_periods: int
) -> tuple[cp_model.CpModel, SolverVariables]:
    model = cp_model.CpModel()
    builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
    variables = builder.build()
    return model, variables


class TestMaxConsecutiveInit:
    """Tests for MaxConsecutiveConstraint initialization."""

    def test_init_default_config(self) -> None:
        model, variables = _build(
            [Worker(id="worker_1", name="Worker 1")],
            [
                ShiftType(
                    id="shift_day",
                    name="Day",
                    category="cat_a",
                    start_time=time(7, 0),
                    end_time=time(15, 0),
                    duration_hours=8.0,
                    workers_required=1,
                )
            ],
            num_periods=4,
        )
        constraint = MaxConsecutiveConstraint(model, variables)

        assert constraint.constraint_id == "max_consecutive"
        assert constraint.is_enabled
        assert constraint.is_hard
        assert constraint.weight == 100
        assert constraint.handles_hard_mode is False

    def test_init_with_params(self) -> None:
        model, variables = _build(
            [Worker(id="worker_1", name="Worker 1")],
            [
                ShiftType(
                    id="shift_day",
                    name="Day",
                    category="cat_a",
                    start_time=time(7, 0),
                    end_time=time(15, 0),
                    duration_hours=8.0,
                    workers_required=1,
                )
            ],
            num_periods=4,
        )
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=250,
            parameters={"max_consecutive_periods": 3, "min_consecutive_periods": 2},
        )
        constraint = MaxConsecutiveConstraint(model, variables, config)

        assert constraint.weight == 250
        assert constraint.config.get_param("max_consecutive_periods") == 3
        assert constraint.config.get_param("min_consecutive_periods") == 2


class TestMaxConsecutiveNoOps:
    """No-op / warn paths."""

    def test_disabled_does_nothing(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=5)
        config = ConstraintConfig(
            enabled=False, parameters={"max_consecutive_periods": 2}
        )
        constraint = MaxConsecutiveConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=5)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0

    def test_neither_max_nor_min_set_warns_and_noops(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=5)
        constraint = MaxConsecutiveConstraint(model, variables)
        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=5)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0
        assert "max_consecutive" in caplog.text.lower()

    def test_shift_types_and_categories_filters_combine_with_and_semantics(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """shift_types=[day] and categories=[cat_b] never overlap (AND, not
        OR), so nothing counts as 'working' and the constraint warns+no-ops."""
        model, variables = _build(workers, shift_types, num_periods=5)
        config = ConstraintConfig(
            parameters={
                "max_consecutive_periods": 2,
                "shift_types": ["shift_day"],
                "categories": ["cat_b"],
            }
        )
        constraint = MaxConsecutiveConstraint(model, variables, config)
        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=5)

        assert len(constraint.violation_variables) == 0
        assert "max_consecutive" in caplog.text.lower()

    def test_min_consecutive_periods_one_is_degenerate_noop(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """min_consecutive_periods=1 (with no max configured) is trivially
        satisfied by any run of length >= 1, so no violation variables are
        created -- this is a harmless degenerate config, not an error."""
        model, variables = _build(workers, shift_types, num_periods=5)
        config = ConstraintConfig(parameters={"min_consecutive_periods": 1})
        constraint = MaxConsecutiveConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=5)

        assert len(constraint.violation_variables) == 0
        # "works" linking constraints are still built.
        assert constraint.constraint_count > 0

    def test_empty_workers_or_zero_periods_warns_and_noops(
        self, shift_types: list[ShiftType], caplog: pytest.LogCaptureFixture
    ) -> None:
        model, variables = _build(
            [Worker(id="worker_1", name="Worker 1")], shift_types, num_periods=3
        )
        config = ConstraintConfig(parameters={"max_consecutive_periods": 2})
        constraint = MaxConsecutiveConstraint(model, variables, config)
        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=[], shift_types=shift_types, num_periods=3)

        assert len(constraint.violation_variables) == 0
        assert "max_consecutive" in caplog.text.lower()


class TestMaxConsecutiveMaxRun:
    """Tests for the max_consecutive_periods (cap) half."""

    def test_hard_mode_infeasible_when_run_too_long(
        self, shift_types: list[ShiftType]
    ) -> None:
        """3 consecutive working periods with max_consecutive_periods=2 must
        be infeasible once the violation is pinned to 0 (hard mode)."""
        num_periods = 5
        workers = [Worker(id="worker_1", name="Worker 1")]
        model, variables = _build(workers, shift_types, num_periods=num_periods)

        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "max_consecutive_periods": 2,
                "shift_types": ["shift_day"],
            },
        )
        constraint = MaxConsecutiveConstraint(model, variables, config)
        constraint.apply(
            workers=workers, shift_types=shift_types, num_periods=num_periods
        )
        _pin_non_auxiliary_to_zero(model, constraint)

        day = "shift_day"
        for p, val in enumerate([1, 1, 1, 0, 0]):
            model.add(variables.get_assignment_var("worker_1", p, day) == val)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE

    def test_hard_mode_feasible_at_exactly_the_cap(
        self, shift_types: list[ShiftType]
    ) -> None:
        """Runs of exactly max_consecutive_periods must remain feasible."""
        num_periods = 5
        workers = [Worker(id="worker_1", name="Worker 1")]
        model, variables = _build(workers, shift_types, num_periods=num_periods)

        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "max_consecutive_periods": 2,
                "shift_types": ["shift_day"],
            },
        )
        constraint = MaxConsecutiveConstraint(model, variables, config)
        constraint.apply(
            workers=workers, shift_types=shift_types, num_periods=num_periods
        )
        _pin_non_auxiliary_to_zero(model, constraint)

        day = "shift_day"
        # Two runs of length 2, separated by a day off.
        for p, val in enumerate([1, 1, 0, 1, 1]):
            model.add(variables.get_assignment_var("worker_1", p, day) == val)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        for name, var in constraint.violation_variables.items():
            if constraint.violation_variable_types.get(name) != "auxiliary":
                assert solver.value(var) == 0, name

    def test_soft_mode_allows_violation_and_counts_excess(
        self, shift_types: list[ShiftType]
    ) -> None:
        """Soft mode allows a run longer than the cap, and the excess
        violation variable is driven to its tight (minimal correct) value."""
        num_periods = 3
        workers = [Worker(id="worker_1", name="Worker 1")]
        model, variables = _build(workers, shift_types, num_periods=num_periods)

        config = ConstraintConfig(
            is_hard=False,
            weight=100,
            parameters={
                "max_consecutive_periods": 2,
                "shift_types": ["shift_day"],
            },
        )
        constraint = MaxConsecutiveConstraint(model, variables, config)
        constraint.apply(
            workers=workers, shift_types=shift_types, num_periods=num_periods
        )

        day = "shift_day"
        for p in range(num_periods):
            model.add(variables.get_assignment_var("worker_1", p, day) == 1)

        excess_vars = [
            v
            for k, v in constraint.violation_variables.items()
            if k.startswith("maxcon_excess_")
        ]
        model.minimize(sum(excess_vars))

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.OPTIMAL
        # Single window covering all 3 periods: sum=3, cap=2 => excess==1.
        assert sum(solver.value(v) for v in excess_vars) == 1

    def test_total_max_is_auxiliary(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=6)
        config = ConstraintConfig(parameters={"max_consecutive_periods": 2})
        constraint = MaxConsecutiveConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        assert "total_max" in constraint.violation_variables
        assert constraint.violation_variable_types["total_max"] == "auxiliary"
        assert "total_min" not in constraint.violation_variables

    def test_window_larger_than_horizon_is_safe_noop(
        self, shift_types: list[ShiftType]
    ) -> None:
        """max_consecutive_periods + 1 > num_periods clamps to one
        full-horizon window; since max_consecutive_periods >= num_periods in
        that case, the clamp is never restrictive."""
        num_periods = 3
        workers = [Worker(id="worker_1", name="Worker 1")]
        model, variables = _build(workers, shift_types, num_periods=num_periods)

        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "max_consecutive_periods": 10,
                "shift_types": ["shift_day"],
            },
        )
        constraint = MaxConsecutiveConstraint(model, variables, config)
        constraint.apply(
            workers=workers, shift_types=shift_types, num_periods=num_periods
        )
        _pin_non_auxiliary_to_zero(model, constraint)

        day = "shift_day"
        for p in range(num_periods):
            model.add(variables.get_assignment_var("worker_1", p, day) == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


class TestMaxConsecutiveMinRun:
    """Tests for the min_consecutive_periods (floor) half."""

    def test_hard_mode_infeasible_when_run_broken_early(
        self, shift_types: list[ShiftType]
    ) -> None:
        """A run that starts but stops before reaching min_consecutive_periods,
        well before the horizon end, must be infeasible when pinned."""
        num_periods = 5
        workers = [Worker(id="worker_1", name="Worker 1")]
        model, variables = _build(workers, shift_types, num_periods=num_periods)

        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "min_consecutive_periods": 3,
                "shift_types": ["shift_day"],
            },
        )
        constraint = MaxConsecutiveConstraint(model, variables, config)
        constraint.apply(
            workers=workers, shift_types=shift_types, num_periods=num_periods
        )
        _pin_non_auxiliary_to_zero(model, constraint)

        day = "shift_day"
        # Run starts at period 0, breaks at period 2 (length 2 < min 3),
        # with 2 more periods still inside the horizon.
        for p, val in enumerate([1, 1, 0, 0, 0]):
            model.add(variables.get_assignment_var("worker_1", p, day) == val)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE

    def test_hard_mode_feasible_when_run_reaches_minimum(
        self, shift_types: list[ShiftType]
    ) -> None:
        num_periods = 5
        workers = [Worker(id="worker_1", name="Worker 1")]
        model, variables = _build(workers, shift_types, num_periods=num_periods)

        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "min_consecutive_periods": 3,
                "shift_types": ["shift_day"],
            },
        )
        constraint = MaxConsecutiveConstraint(model, variables, config)
        constraint.apply(
            workers=workers, shift_types=shift_types, num_periods=num_periods
        )
        _pin_non_auxiliary_to_zero(model, constraint)

        day = "shift_day"
        for p, val in enumerate([1, 1, 1, 0, 0]):
            model.add(variables.get_assignment_var("worker_1", p, day) == val)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_boundary_policy_exempts_run_truncated_by_horizon_end(
        self, shift_types: list[ShiftType]
    ) -> None:
        """A run starting so close to the end of the horizon that it cannot
        possibly reach min_consecutive_periods is exempt (lenient boundary
        policy), even when pinned to hard mode."""
        num_periods = 5
        workers = [Worker(id="worker_1", name="Worker 1")]
        model, variables = _build(workers, shift_types, num_periods=num_periods)

        config = ConstraintConfig(
            is_hard=True,
            parameters={
                "min_consecutive_periods": 3,
                "shift_types": ["shift_day"],
            },
        )
        constraint = MaxConsecutiveConstraint(model, variables, config)
        constraint.apply(
            workers=workers, shift_types=shift_types, num_periods=num_periods
        )
        _pin_non_auxiliary_to_zero(model, constraint)

        day = "shift_day"
        # Isolated single-period run at the very last period only.
        for p, val in enumerate([0, 0, 0, 0, 1]):
            model.add(variables.get_assignment_var("worker_1", p, day) == val)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_soft_mode_violation_forced_true_when_run_breaks(
        self, shift_types: list[ShiftType]
    ) -> None:
        num_periods = 5
        workers = [Worker(id="worker_1", name="Worker 1")]
        model, variables = _build(workers, shift_types, num_periods=num_periods)

        config = ConstraintConfig(
            is_hard=False,
            weight=100,
            parameters={
                "min_consecutive_periods": 3,
                "shift_types": ["shift_day"],
            },
        )
        constraint = MaxConsecutiveConstraint(model, variables, config)
        constraint.apply(
            workers=workers, shift_types=shift_types, num_periods=num_periods
        )

        day = "shift_day"
        for p, val in enumerate([1, 1, 0, 0, 0]):
            model.add(variables.get_assignment_var("worker_1", p, day) == val)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # start[0]=1 (run begins at p0); k=2 -> works[2] must be 1 or the
        # p0_k2 violation is forced true (works[2]==0 here).
        viol = constraint.violation_variables["maxcon_minrun_viol_worker_1_p0_k2"]
        assert solver.value(viol) == 1

    def test_total_min_is_auxiliary(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=6)
        config = ConstraintConfig(parameters={"min_consecutive_periods": 3})
        constraint = MaxConsecutiveConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        assert "total_min" in constraint.violation_variables
        assert constraint.violation_variable_types["total_min"] == "auxiliary"
        assert "total_max" not in constraint.violation_variables


class TestMaxConsecutiveCombined:
    """Both halves active together."""

    def test_both_max_and_min_create_both_totals(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=8)
        config = ConstraintConfig(
            parameters={
                "max_consecutive_periods": 4,
                "min_consecutive_periods": 2,
            }
        )
        constraint = MaxConsecutiveConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=8)

        assert "total_max" in constraint.violation_variables
        assert "total_min" in constraint.violation_variables
        assert constraint.violation_variable_types["total_max"] == "auxiliary"
        assert constraint.violation_variable_types["total_min"] == "auxiliary"


class TestMaxConsecutiveEdgeCases:
    """Single period and other structural edge cases."""

    def test_single_period_does_not_crash(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build(workers, shift_types, num_periods=1)
        config = ConstraintConfig(
            parameters={
                "max_consecutive_periods": 1,
                "min_consecutive_periods": 3,
            }
        )
        constraint = MaxConsecutiveConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        # min_consecutive_periods=3 can never be checked with only 1 period
        # in the horizon (every k is out of range), so no minrun violations.
        minrun_vars = [
            k
            for k in constraint.violation_variables
            if k.startswith("maxcon_minrun_viol_")
        ]
        assert minrun_vars == []

    def test_categories_filter_selects_matching_shift_types(
        self, shift_types: list[ShiftType]
    ) -> None:
        """categories=[cat_a] restricts 'working' to shift_day only."""
        num_periods = 4
        workers = [Worker(id="worker_1", name="Worker 1")]
        model, variables = _build(workers, shift_types, num_periods=num_periods)

        config = ConstraintConfig(
            is_hard=True,
            parameters={"max_consecutive_periods": 1, "categories": ["cat_a"]},
        )
        constraint = MaxConsecutiveConstraint(model, variables, config)
        constraint.apply(
            workers=workers, shift_types=shift_types, num_periods=num_periods
        )
        _pin_non_auxiliary_to_zero(model, constraint)

        # Two consecutive night shifts (cat_b, not filtered) must remain
        # feasible even though max_consecutive_periods=1, since only
        # shift_day (cat_a) counts as "working".
        night = "shift_night"
        model.add(variables.get_assignment_var("worker_1", 0, night) == 1)
        model.add(variables.get_assignment_var("worker_1", 1, night) == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
