"""Tests for min_rest constraint."""

import logging
from datetime import date, time, timedelta

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.min_rest import MinRestConstraint
from shift_solver.models import ShiftType, Worker
from shift_solver.solver.objective_builder import ObjectiveBuilder
from shift_solver.solver.types import SolverVariables
from shift_solver.solver.variable_builder import VariableBuilder


def _daily_period_dates(start: date, num_periods: int) -> list[tuple[date, date]]:
    """Build period_dates for consecutive single-day periods starting at `start`."""
    return [
        (start + timedelta(days=i), start + timedelta(days=i))
        for i in range(num_periods)
    ]


def _pin_hard(model: cp_model.CpModel, constraint: MinRestConstraint) -> None:
    """
    Replicate ShiftSolver._enforce_hard_mode: pin every non-auxiliary
    violation var to 0. MinRestConstraint does not self-enforce hard mode
    (handles_hard_mode=False) -- that's ShiftSolver's job, so unit tests
    exercising hard mode in isolation must do it themselves.
    """
    for name, var in constraint.violation_variables.items():
        if constraint.violation_variable_types.get(name) == "auxiliary":
            continue
        model.add(var == 0)


@pytest.fixture
def workers() -> list[Worker]:
    """Create test workers."""
    return [
        Worker(id="worker_1", name="Worker One"),
        Worker(id="worker_2", name="Worker Two"),
    ]


@pytest.fixture
def shift_types() -> list[ShiftType]:
    """
    Create shift types with overlapping/tight-gap and well-separated times.

    - "day": 07:00-15:00 (8h)
    - "evening": 14:00-22:00 (8h) -- overlaps "day" by 1h same-day
    - "night": 23:00-07:00 (8h, overnight wrap)
    - "morning": 06:00-14:00 (8h) -- only 6h gap from night's 07:00 end
      to a *previous* evening end etc; mainly used for adjacent-period
      boundary tests against "night"
    """
    return [
        ShiftType(
            id="day",
            name="Day Shift",
            category="cat_a",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=1,
        ),
        ShiftType(
            id="evening",
            name="Evening Shift",
            category="cat_a",
            start_time=time(14, 0),
            end_time=time(22, 0),
            duration_hours=8.0,
            workers_required=1,
        ),
        ShiftType(
            id="night",
            name="Night Shift",
            category="cat_b",
            start_time=time(23, 0),
            end_time=time(7, 0),
            duration_hours=8.0,
            workers_required=1,
        ),
        ShiftType(
            id="morning",
            name="Morning Shift",
            category="cat_b",
            start_time=time(6, 0),
            end_time=time(14, 0),
            duration_hours=8.0,
            workers_required=1,
        ),
    ]


@pytest.fixture
def model_and_variables(
    workers: list[Worker], shift_types: list[ShiftType]
) -> tuple[cp_model.CpModel, SolverVariables]:
    """Create model and variables for testing (10 periods)."""
    model = cp_model.CpModel()
    builder = VariableBuilder(model, workers, shift_types, num_periods=10)
    variables = builder.build()
    return model, variables


@pytest.fixture
def period_dates() -> list[tuple[date, date]]:
    """10 consecutive single-day periods starting Monday 2026-01-05."""
    return _daily_period_dates(date(2026, 1, 5), 10)


class TestMinRestConstraintInit:
    """Tests for MinRestConstraint initialization."""

    def test_init_default_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Default config uses BaseConstraint defaults."""
        model, variables = model_and_variables
        constraint = MinRestConstraint(model, variables)

        assert constraint.constraint_id == "min_rest"
        assert constraint.is_enabled
        assert constraint.is_hard
        assert constraint.weight == 100
        assert constraint.handles_hard_mode is False

    def test_init_soft_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Custom soft config."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=500,
            parameters={"min_rest_hours": 12.0},
        )
        constraint = MinRestConstraint(model, variables, config)

        assert not constraint.is_hard
        assert constraint.weight == 500
        assert constraint.config.get_param("min_rest_hours") == 12.0


class TestMinRestMissingContext:
    """Tests for edge cases / silent no-op paths."""

    def test_missing_period_dates_warns_and_skips(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """No period_dates in context -> warn, no violation variables."""
        model, variables = model_and_variables
        constraint = MinRestConstraint(model, variables)

        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=10)

        assert len(constraint.violation_variables) == 0
        assert "min_rest" in caplog.text.lower()
        assert "period_dates" in caplog.text.lower()

    def test_empty_period_dates_warns_and_skips(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Empty period_dates list -> treated the same as missing."""
        model, variables = model_and_variables
        constraint = MinRestConstraint(model, variables)

        with caplog.at_level(logging.WARNING):
            constraint.apply(
                workers=workers,
                shift_types=shift_types,
                num_periods=10,
                period_dates=[],
            )

        assert len(constraint.violation_variables) == 0

    def test_disabled_does_nothing(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Disabled constraint adds no constraints."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=False)
        constraint = MinRestConstraint(model, variables, config)

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=10,
            period_dates=period_dates,
        )

        assert len(constraint.violation_variables) == 0

    def test_shift_types_filter_to_empty_warns_and_skips(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """shift_types filter matching nothing -> warn, no-op."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={"shift_types": ["does_not_exist"]},
        )
        constraint = MinRestConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(
                workers=workers,
                shift_types=shift_types,
                num_periods=10,
                period_dates=period_dates,
            )

        assert len(constraint.violation_variables) == 0
        assert "min_rest" in caplog.text.lower()

    def test_no_conflicting_pairs_warns(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A single shift type filter produces no same-period pairs at all
        and a threshold small enough that no adjacent-period pair (gap 16h
        for day->day next day) violates either -> warns, no-op."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={"min_rest_hours": 1.0, "shift_types": ["day"]},
        )
        constraint = MinRestConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(
                workers=workers,
                shift_types=shift_types,
                num_periods=10,
                period_dates=period_dates,
            )

        assert len(constraint.violation_variables) == 0
        assert "min_rest" in caplog.text.lower()


class TestMinRestSamePeriodPairs:
    """Tests for the same single-day-period pairwise rest check."""

    def test_overlapping_shifts_same_day_create_violation(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """day (07-15) and evening (14-22) overlap by 1h on the same day.

        With this filter there are also 9 adjacent-period violations
        (evening ending 22:00 then day starting 07:00 the next day is
        only a 9h gap, < the 11h threshold) -- 10 same-period pairs (one
        per single-day period) + 9 adjacent-period pairs (p=0..8) per
        worker = 19 total per worker.
        """
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={
                "min_rest_hours": 11.0,
                "shift_types": ["day", "evening"],
            },
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=10,
            period_dates=period_dates,
        )

        rest_viols = [
            k for k in constraint.violation_variables if k.startswith("rest_viol_")
        ]
        assert len(rest_viols) == len(workers) * 19
        # Spot-check both categories explicitly.
        assert "rest_viol_worker_1_p0_day_p0_evening" in rest_viols
        assert "rest_viol_worker_1_p0_evening_p1_day" in rest_viols

    def test_overlap_forces_violation_true_when_both_assigned(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Solving with both overlapping shifts forced to 1 must force viol=1."""
        model = cp_model.CpModel()
        w = [workers[0]]
        builder = VariableBuilder(model, w, shift_types, num_periods=10)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={
                "min_rest_hours": 11.0,
                "shift_types": ["day", "evening"],
            },
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=w,
            shift_types=shift_types,
            num_periods=10,
            period_dates=period_dates,
        )

        model.add(variables.get_assignment_var("worker_1", 0, "day") == 1)
        model.add(variables.get_assignment_var("worker_1", 0, "evening") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        viol = constraint.violation_variables["rest_viol_worker_1_p0_day_p0_evening"]
        assert solver.value(viol) == 1

    def test_no_violation_when_only_one_assigned(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Only one of the pair assigned -> violation naturally minimized to 0."""
        model = cp_model.CpModel()
        w = [workers[0]]
        builder = VariableBuilder(model, w, shift_types, num_periods=10)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={
                "min_rest_hours": 11.0,
                "shift_types": ["day", "evening"],
            },
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=w,
            shift_types=shift_types,
            num_periods=10,
            period_dates=period_dates,
        )

        model.add(variables.get_assignment_var("worker_1", 0, "day") == 1)
        model.add(variables.get_assignment_var("worker_1", 0, "evening") == 0)

        # Minimize violations so the solver actually drives viol to 0.
        viol_vars = [
            v for k, v in constraint.violation_variables.items() if k != "total"
        ]
        model.minimize(sum(viol_vars))

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        viol = constraint.violation_variables["rest_viol_worker_1_p0_day_p0_evening"]
        assert solver.value(viol) == 0

    def test_no_violation_for_well_separated_same_day_shifts(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """morning (06-14) and night (23-07) same day: gap from 14:00 to
        23:00 is 9h (< 11h default) -- so this IS a violation; use a large
        min_rest_hours=0 to prove no pair is created for the *reverse*
        (well separated) direction check on a same-day non-overlapping
        pair with ample gap. Use day (07-15) vs a synthetic large-gap
        threshold to confirm no rest_viol is registered when gap exceeds
        threshold.
        """
        model, variables = model_and_variables
        # day 07-15, and we filter to only "day" (single shift type) so no
        # same-period pair even exists (need >= 2 distinct shift types).
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={"min_rest_hours": 1.0, "shift_types": ["day"]},
        )
        constraint = MinRestConstraint(model, variables, config)

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=10,
            period_dates=period_dates,
        )

        # Only one shift type selected -> no same-period pairs possible.
        rest_viols = [
            k for k in constraint.violation_variables if k.startswith("rest_viol_")
        ]
        assert len(rest_viols) == 0

    def test_multi_day_period_skips_same_period_check(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """A multi-day period must not generate same-period pairs."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        multi_day_dates = [(date(2026, 1, 5), date(2026, 1, 9))]  # Mon-Fri

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={
                "min_rest_hours": 11.0,
                "shift_types": ["day", "evening"],
            },
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            period_dates=multi_day_dates,
        )

        # No adjacent period exists (num_periods=1) and the sole period is
        # multi-day, so no same-period check applies either -> nothing.
        rest_viols = [
            k for k in constraint.violation_variables if k.startswith("rest_viol_")
        ]
        assert len(rest_viols) == 0


class TestMinRestAdjacentPeriods:
    """Tests for the adjacent-period boundary rest check."""

    def test_overnight_shift_into_early_morning_creates_violation(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """night (23:00-07:00, wraps) ending day2 07:00, then morning
        (06:00-14:00) starting day2 06:00 on the very next period ->
        overlap (negative gap) -> violation."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={
                "min_rest_hours": 11.0,
                "shift_types": ["night", "morning"],
            },
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=10,
            period_dates=period_dates,
        )

        # (night in p0, morning in p1) ordered pair must exist.
        key = "rest_viol_worker_1_p0_night_p1_morning"
        assert key in constraint.violation_variables

    def test_reverse_order_pair_not_a_violation(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """(morning in p0, night in p1): morning ends day1 14:00, night
        starts day2 23:00 -> gap = 33h, no violation expected, so no
        rest_viol_ variable pair should exist for this specific ordering.
        """
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={
                "min_rest_hours": 11.0,
                "shift_types": ["night", "morning"],
            },
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=10,
            period_dates=period_dates,
        )

        key = "rest_viol_worker_1_p0_morning_p1_night"
        assert key not in constraint.violation_variables

    def test_solve_forces_pair_forbidden_in_hard_mode(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Hard mode (via manual pinning, replicating ShiftSolver): the
        conflicting adjacent pair cannot both be 1."""
        model = cp_model.CpModel()
        w = [workers[0]]
        builder = VariableBuilder(model, w, shift_types, num_periods=10)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True,
            is_hard=True,
            parameters={
                "min_rest_hours": 11.0,
                "shift_types": ["night", "morning"],
            },
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=w,
            shift_types=shift_types,
            num_periods=10,
            period_dates=period_dates,
        )
        _pin_hard(model, constraint)

        # Force both halves of the conflicting pair to 1 -> infeasible.
        model.add(variables.get_assignment_var("worker_1", 0, "night") == 1)
        model.add(variables.get_assignment_var("worker_1", 1, "morning") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE

    def test_hard_mode_allows_non_conflicting_pair(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Hard mode does not forbid a non-conflicting adjacent pair."""
        model = cp_model.CpModel()
        w = [workers[0]]
        builder = VariableBuilder(model, w, shift_types, num_periods=10)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True,
            is_hard=True,
            parameters={
                "min_rest_hours": 11.0,
                "shift_types": ["night", "morning"],
            },
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=w,
            shift_types=shift_types,
            num_periods=10,
            period_dates=period_dates,
        )
        _pin_hard(model, constraint)

        # morning in p0, night in p1: not a conflicting pair (33h gap).
        model.add(variables.get_assignment_var("worker_1", 0, "morning") == 1)
        model.add(variables.get_assignment_var("worker_1", 1, "night") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_non_adjacent_periods_not_checked(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Even if periods p and p+2 have a tiny calendar gap between them
        (e.g. same day, unusual layout), only ADJACENT (p, p+1) pairs are
        checked -- p and p+2 are never paired regardless of dates."""
        model = cp_model.CpModel()
        w = [workers[0]]
        builder = VariableBuilder(model, w, shift_types, num_periods=3)
        variables = builder.build()

        # Period 0 and period 2 share the SAME calendar day (contrived),
        # which would clearly conflict if checked, but they are 2 apart.
        same_day = date(2026, 1, 5)
        weird_dates = [
            (same_day, same_day),
            (same_day + timedelta(days=1), same_day + timedelta(days=1)),
            (same_day, same_day),
        ]

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={
                "min_rest_hours": 11.0,
                "shift_types": ["night", "morning"],
            },
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=w, shift_types=shift_types, num_periods=3, period_dates=weird_dates
        )

        # No pair spans period 0 and period 2 directly.
        for key in constraint.violation_variables:
            if key == "total":
                continue
            # Every key must reference only adjacent period pairs (p0-p1
            # same-period, or p0-p1 / p1-p2 adjacent) -- never p0 and p2
            # in the same key.
            assert not ("p0_" in key and "p2_" in key)

    def test_calendar_gap_exceeding_threshold_skips_pair(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Adjacent periods (by index) whose actual calendar dates are far
        apart (e.g. a multi-day gap between weekly periods) must not be
        flagged even for a threshold that WOULD flag the same shift
        repeating on consecutive calendar days.

        Uses a single shift type ("day", 8h) so no same-period pair is
        possible (needs >= 2 distinct types), isolating the adjacent-period
        calendar-gap computation. Repeating "day" on consecutive calendar
        days leaves a 16h gap, so min_rest_hours=17.0 would flag that if
        the periods were adjacent by 1 day -- proving the implementation
        computes the real gap from period_dates rather than assuming
        periods are always 1 day apart.
        """
        model = cp_model.CpModel()
        w = [workers[0]]
        builder = VariableBuilder(model, w, shift_types, num_periods=2)
        variables = builder.build()

        # period 0 ends Jan 5, period 1 starts Jan 10 (~5 days later) --
        # far more than 17h regardless of shift times.
        far_apart_dates = [
            (date(2026, 1, 5), date(2026, 1, 5)),
            (date(2026, 1, 10), date(2026, 1, 10)),
        ]

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={
                "min_rest_hours": 17.0,
                "shift_types": ["day"],
            },
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=w,
            shift_types=shift_types,
            num_periods=2,
            period_dates=far_apart_dates,
        )

        rest_viols = [
            k for k in constraint.violation_variables if k.startswith("rest_viol_")
        ]
        assert len(rest_viols) == 0

    def test_adjacent_one_day_gap_would_flag_same_pair(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Sanity counterpart to the previous test: with the SAME filter
        and threshold, periods that really are 1 calendar day apart DO
        flag the repeating "day" pair (16h gap < 17h threshold) -- proves
        the far-apart test above isn't vacuously passing because the pair
        never conflicts at all."""
        model = cp_model.CpModel()
        w = [workers[0]]
        builder = VariableBuilder(model, w, shift_types, num_periods=2)
        variables = builder.build()

        adjacent_dates = [
            (date(2026, 1, 5), date(2026, 1, 5)),
            (date(2026, 1, 6), date(2026, 1, 6)),
        ]

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={
                "min_rest_hours": 17.0,
                "shift_types": ["day"],
            },
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=w,
            shift_types=shift_types,
            num_periods=2,
            period_dates=adjacent_dates,
        )

        assert "rest_viol_worker_1_p0_day_p1_day" in constraint.violation_variables

    def test_multi_day_period_boundary_still_checked(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Multi-day periods still get the adjacent-period boundary check
        (last day of p vs first day of p+1)."""
        model = cp_model.CpModel()
        w = [workers[0]]
        builder = VariableBuilder(model, w, shift_types, num_periods=2)
        variables = builder.build()

        # Period 0: Mon-Fri (Jan 5-9), period 1: starts Sat Jan 10 (next day).
        multi_day_dates = [
            (date(2026, 1, 5), date(2026, 1, 9)),
            (date(2026, 1, 10), date(2026, 1, 10)),
        ]

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={
                "min_rest_hours": 11.0,
                "shift_types": ["night", "morning"],
            },
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=w,
            shift_types=shift_types,
            num_periods=2,
            period_dates=multi_day_dates,
        )

        # night in p0 (anchored on Jan 9, last day) ending Jan 10 07:00,
        # morning in p1 (anchored on Jan 10, first day) starting 06:00 ->
        # overlap -> violation expected.
        key = "rest_viol_worker_1_p0_night_p1_morning"
        assert key in constraint.violation_variables


class TestMinRestPerWorkerOverrides:
    """Tests for the per_worker_overrides parameter."""

    def test_override_lowers_threshold_for_specific_worker(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """worker_1 gets a low override (no conflict), worker_2 uses the
        higher default (conflict) for the same-day (night, morning) pair,
        which has a 9h gap (morning 06-14 ends well before night starts
        23:00 the same day)."""
        model, variables = model_and_variables

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={
                "min_rest_hours": 11.0,
                "shift_types": ["night", "morning"],
                "per_worker_overrides": {"worker_1": 8.0},
            },
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=10,
            period_dates=period_dates,
        )

        w1_key = "rest_viol_worker_1_p0_night_p0_morning"
        w2_key = "rest_viol_worker_2_p0_night_p0_morning"

        assert w1_key not in constraint.violation_variables  # 9h >= 8h override
        assert w2_key in constraint.violation_variables  # 9h < 11h default

    def test_override_raises_threshold_for_specific_worker(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """worker_1 gets a strict override (10h) that flags the same-day
        (night, morning) 9h-gap pair, which the 8h default would allow
        for worker_2."""
        model, variables = model_and_variables

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={
                "min_rest_hours": 8.0,
                "shift_types": ["night", "morning"],
                "per_worker_overrides": {"worker_1": 10.0},
            },
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=10,
            period_dates=period_dates,
        )

        w1_key = "rest_viol_worker_1_p0_night_p0_morning"
        w2_key = "rest_viol_worker_2_p0_night_p0_morning"

        # gap = 9h: worker_1 override(10h) flags it, worker_2 default(8h) doesn't.
        assert w1_key in constraint.violation_variables
        assert w2_key not in constraint.violation_variables


class TestMinRestObjectiveDoubleCount:
    """The 'total' aggregate must not double-count in the objective."""

    def test_total_registered_as_auxiliary(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={"min_rest_hours": 11.0, "shift_types": ["day", "evening"]},
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=10,
            period_dates=period_dates,
        )

        assert "total" in constraint.violation_variables
        assert constraint.violation_variable_types.get("total") == "auxiliary"

    def test_objective_builder_excludes_total(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"min_rest_hours": 11.0, "shift_types": ["day", "evening"]},
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=10,
            period_dates=period_dates,
        )

        builder = ObjectiveBuilder(model)
        builder.add_constraint(constraint)
        builder.build()

        term_names = {term.variable_name for term in builder.objective_terms}
        rest_viol_names = {
            k for k in constraint.violation_variables if k.startswith("rest_viol_")
        }
        assert "total" not in term_names
        assert term_names == rest_viol_names

    def test_hard_mode_skipped_by_objective_builder(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """When is_hard=True and handles_hard_mode=False, ObjectiveBuilder
        skips the constraint entirely (its pinned-to-0 vars cost nothing
        anyway, so this just confirms no terms leak through)."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=True,
            weight=100,
            parameters={"min_rest_hours": 11.0, "shift_types": ["day", "evening"]},
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=10,
            period_dates=period_dates,
        )

        builder = ObjectiveBuilder(model)
        builder.add_constraint(constraint)
        builder.build()

        assert builder.objective_terms == []


class TestMinRestSinglePeriod:
    """Edge case: a single scheduling period."""

    def test_single_period_only_same_period_pairs_possible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        period_dates_single = [(date(2026, 1, 5), date(2026, 1, 5))]

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={
                "min_rest_hours": 11.0,
                "shift_types": ["day", "evening"],
            },
        )
        constraint = MinRestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            period_dates=period_dates_single,
        )

        # 1 same-period pair (day, evening) per worker, no adjacent pairs.
        rest_viols = [
            k for k in constraint.violation_variables if k.startswith("rest_viol_")
        ]
        assert len(rest_viols) == len(workers)
