"""Tests for weekend constraint."""

import logging
from datetime import date, time, timedelta

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.weekend import WeekendConstraint
from shift_solver.models import ShiftType, Worker
from shift_solver.solver.types import SolverVariables
from shift_solver.solver.variable_builder import VariableBuilder


def _period_dates(start: date, num_periods: int) -> list[tuple[date, date]]:
    """Build one-day period_dates starting at `start` for `num_periods` days."""
    return [
        (start + timedelta(days=i), start + timedelta(days=i))
        for i in range(num_periods)
    ]


@pytest.fixture
def workers() -> list[Worker]:
    return [
        Worker(id="worker_1", name="Worker 1"),
        Worker(id="worker_2", name="Worker 2"),
    ]


@pytest.fixture
def shift_types() -> list[ShiftType]:
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


def _build_model(
    workers: list[Worker], shift_types: list[ShiftType], num_periods: int
) -> tuple[cp_model.CpModel, SolverVariables]:
    model = cp_model.CpModel()
    builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
    variables = builder.build()
    return model, variables


def _pin_hard(model: cp_model.CpModel, constraint: WeekendConstraint) -> None:
    """
    Replicate ShiftSolver._enforce_hard_mode: pin every non-auxiliary
    violation var to 0. WeekendConstraint does not self-enforce hard mode
    (handles_hard_mode=False) -- that's ShiftSolver's job, so unit tests
    exercising hard mode in isolation must do it themselves.
    """
    for name, var in constraint.violation_variables.items():
        if constraint.violation_variable_types.get(name) == "auxiliary":
            continue
        model.add(var == 0)


# Monday 2026-01-05 as the horizon start (a fixed, non-random date).
MONDAY = date(2026, 1, 5)


class TestWeekendConstraintInit:
    def test_init_default_config(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build_model(workers, shift_types, num_periods=7)
        constraint = WeekendConstraint(model, variables)

        assert constraint.constraint_id == "weekend"
        assert constraint.is_enabled
        assert constraint.is_hard
        assert constraint.weight == 100

    def test_init_with_config(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build_model(workers, shift_types, num_periods=7)
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=250,
            parameters={"require_complete": True},
        )
        constraint = WeekendConstraint(model, variables, config)

        assert constraint.weight == 250
        assert constraint.config.get_param("require_complete") is True


class TestWeekendConstraintNoOpPaths:
    """Edge cases that must warn and add nothing."""

    def test_disabled_does_nothing(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build_model(workers, shift_types, num_periods=7)
        config = ConstraintConfig(enabled=False)
        constraint = WeekendConstraint(model, variables, config)

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=7,
            period_dates=_period_dates(MONDAY, 7),
        )

        assert len(constraint.violation_variables) == 0

    def test_missing_period_dates_warns_and_no_ops(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        model, variables = _build_model(workers, shift_types, num_periods=7)
        config = ConstraintConfig(
            enabled=True, is_hard=False, parameters={"require_complete": True}
        )
        constraint = WeekendConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(
                workers=workers,
                shift_types=shift_types,
                num_periods=7,
                period_dates=[],
            )

        assert len(constraint.violation_variables) == 0
        assert "weekend" in caplog.text.lower()

    def test_multi_day_periods_warn_and_no_op(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        model, variables = _build_model(workers, shift_types, num_periods=2)
        config = ConstraintConfig(
            enabled=True, is_hard=False, parameters={"require_complete": True}
        )
        constraint = WeekendConstraint(model, variables, config)

        # Multi-day (week-long) periods: no per-day resolution available.
        period_dates = [
            (MONDAY, MONDAY + timedelta(days=6)),
            (MONDAY + timedelta(days=7), MONDAY + timedelta(days=13)),
        ]

        with caplog.at_level(logging.WARNING):
            constraint.apply(
                workers=workers,
                shift_types=shift_types,
                num_periods=2,
                period_dates=period_dates,
            )

        assert len(constraint.violation_variables) == 0
        assert "multi-day" in caplog.text.lower()

    def test_no_rules_enabled_warns_and_no_ops(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        model, variables = _build_model(workers, shift_types, num_periods=7)
        # No parameters set at all -> all four rules default off.
        constraint = WeekendConstraint(
            model, variables, ConstraintConfig(enabled=True, is_hard=False)
        )

        with caplog.at_level(logging.WARNING):
            constraint.apply(
                workers=workers,
                shift_types=shift_types,
                num_periods=7,
                period_dates=_period_dates(MONDAY, 7),
            )

        assert len(constraint.violation_variables) == 0
        assert "no rule enabled" in caplog.text.lower()

    def test_empty_weekend_days_warns_and_no_ops(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        model, variables = _build_model(workers, shift_types, num_periods=7)
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={"weekend_days": [], "require_complete": True},
        )
        constraint = WeekendConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(
                workers=workers,
                shift_types=shift_types,
                num_periods=7,
                period_dates=_period_dates(MONDAY, 7),
            )

        assert len(constraint.violation_variables) == 0

    def test_no_weekend_days_in_horizon_warns_and_no_ops(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A horizon confined to weekdays only produces zero weekend groups."""
        model, variables = _build_model(workers, shift_types, num_periods=5)
        config = ConstraintConfig(
            enabled=True, is_hard=False, parameters={"require_complete": True}
        )
        constraint = WeekendConstraint(model, variables, config)

        # Monday..Friday: no Sat/Sun in this horizon.
        with caplog.at_level(logging.WARNING):
            constraint.apply(
                workers=workers,
                shift_types=shift_types,
                num_periods=5,
                period_dates=_period_dates(MONDAY, 5),
            )

        assert len(constraint.violation_variables) == 0
        assert "no weekend-day periods" in caplog.text.lower()


class TestWeekendGrouping:
    """Grouping behavior, including horizon truncation."""

    def test_single_period_horizon_lone_saturday_is_group_of_one(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """A horizon ending on a lone Saturday forms a weekend group of 1."""
        # 2026-01-05 is a Monday; Saturday of that week is 2026-01-10.
        saturday = MONDAY + timedelta(days=5)
        num_periods = 1
        model, variables = _build_model(workers, shift_types, num_periods)
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_working_weekends": 0},
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=_period_dates(saturday, num_periods),
        )

        # One weekend group (size 1) per worker -> one excess var each.
        excess_names = [
            n for n in constraint.violation_variables if "max_total_excess" in n
        ]
        assert len(excess_names) == len(workers)


class TestRequireComplete:
    def test_hard_mode_forces_complete_weekend(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """
        With require_complete hard-enforced and only one worker allowed to
        work Saturday, that same worker must also work Sunday.
        """
        num_periods = 7  # Mon..Sun
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)
        saturday_period = 5
        sunday_period = 6

        # Force worker_1 to work Saturday, worker_2 forbidden from Saturday
        # and forbidden from Sunday too, so the only way to satisfy
        # require_complete is worker_1 also working Sunday.
        model.add(
            variables.get_assignment_var("worker_1", saturday_period, "shift_day") == 1
        )
        for st in shift_types:
            model.add(
                variables.get_assignment_var("worker_2", saturday_period, st.id) == 0
            )
            model.add(
                variables.get_assignment_var("worker_2", sunday_period, st.id) == 0
            )

        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"require_complete": True}
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
        )
        _pin_hard(model, constraint)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        sunday_vars = [
            variables.get_assignment_var("worker_1", sunday_period, st.id)
            for st in shift_types
        ]
        assert sum(solver.value(v) for v in sunday_vars) >= 1

    def test_hard_mode_infeasible_when_partial_weekend_forced(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """
        Forcing worker_1 to work Saturday but forbidding them (and everyone
        else) from working Sunday makes a hard require_complete infeasible.
        """
        num_periods = 7
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)
        saturday_period = 5
        sunday_period = 6

        model.add(
            variables.get_assignment_var("worker_1", saturday_period, "shift_day") == 1
        )
        for worker in workers:
            for st in shift_types:
                model.add(
                    variables.get_assignment_var(worker.id, sunday_period, st.id) == 0
                )

        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"require_complete": True}
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
        )
        _pin_hard(model, constraint)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status == cp_model.INFEASIBLE

    def test_soft_mode_penalizes_partial_weekend(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        num_periods = 7
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)
        saturday_period = 5
        sunday_period = 6

        # worker_1 works Saturday only; forbidden from Sunday entirely.
        model.add(
            variables.get_assignment_var("worker_1", saturday_period, "shift_day") == 1
        )
        for st in shift_types:
            model.add(
                variables.get_assignment_var("worker_1", sunday_period, st.id) == 0
            )

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"require_complete": True},
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
        )

        viol_vars = list(constraint.violation_variables.values())
        model.minimize(sum(viol_vars))

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        complete_viol = constraint.violation_variables[
            f"wknd_complete_viol_worker_1_g0_{saturday_period}_{sunday_period}"
        ]
        assert solver.value(complete_viol) == 1

    def test_soft_mode_zero_penalty_when_weekend_already_complete(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        num_periods = 7
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)
        saturday_period = 5
        sunday_period = 6

        model.add(
            variables.get_assignment_var("worker_1", saturday_period, "shift_day") == 1
        )
        model.add(
            variables.get_assignment_var("worker_1", sunday_period, "shift_day") == 1
        )

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"require_complete": True},
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
        )

        viol_vars = list(constraint.violation_variables.values())
        model.minimize(sum(viol_vars))

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        complete_viol = constraint.violation_variables[
            f"wknd_complete_viol_worker_1_g0_{saturday_period}_{sunday_period}"
        ]
        assert solver.value(complete_viol) == 0


class TestIdenticalShiftType:
    def test_hard_mode_forces_same_shift_type(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """
        With identical_shift_type hard-enforced, forcing worker_1 to work
        Saturday day-shift and Sunday night-shift is infeasible.
        """
        num_periods = 7
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)
        saturday_period = 5
        sunday_period = 6

        model.add(
            variables.get_assignment_var("worker_1", saturday_period, "shift_day") == 1
        )
        model.add(
            variables.get_assignment_var("worker_1", sunday_period, "shift_night") == 1
        )
        # Without an exclusivity constraint, nothing stops the solver from
        # dodging the identical-shift-type requirement by also assigning
        # worker_1 the *other* shift type on the other day (e.g. shift_day
        # on Sunday too). Pin those escape-hatch assignments to 0 so the
        # test actually exercises "different shift types on the two days".
        model.add(
            variables.get_assignment_var("worker_1", saturday_period, "shift_night")
            == 0
        )
        model.add(
            variables.get_assignment_var("worker_1", sunday_period, "shift_day") == 0
        )

        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"identical_shift_type": True}
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
        )
        _pin_hard(model, constraint)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status == cp_model.INFEASIBLE

    def test_hard_mode_allows_same_shift_type(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        num_periods = 7
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)
        saturday_period = 5
        sunday_period = 6

        model.add(
            variables.get_assignment_var("worker_1", saturday_period, "shift_day") == 1
        )
        model.add(
            variables.get_assignment_var("worker_1", sunday_period, "shift_day") == 1
        )

        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"identical_shift_type": True}
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
        )
        _pin_hard(model, constraint)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_hard_mode_does_not_force_working_both_days(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """
        identical_shift_type must not, by itself, force a worker who only
        works Saturday to also work Sunday (that's require_complete's job).
        """
        num_periods = 7
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)
        saturday_period = 5
        sunday_period = 6

        model.add(
            variables.get_assignment_var("worker_1", saturday_period, "shift_day") == 1
        )
        for st in shift_types:
            model.add(
                variables.get_assignment_var("worker_1", sunday_period, st.id) == 0
            )

        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"identical_shift_type": True}
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
        )
        _pin_hard(model, constraint)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_soft_mode_counts_mismatch(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        num_periods = 7
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)
        saturday_period = 5
        sunday_period = 6

        model.add(
            variables.get_assignment_var("worker_1", saturday_period, "shift_day") == 1
        )
        model.add(
            variables.get_assignment_var("worker_1", sunday_period, "shift_night") == 1
        )
        # Close the same escape hatch as in the hard-mode test above so the
        # objective can't dodge the mismatch by also assigning the other
        # shift type on the other day.
        model.add(
            variables.get_assignment_var("worker_1", saturday_period, "shift_night")
            == 0
        )
        model.add(
            variables.get_assignment_var("worker_1", sunday_period, "shift_day") == 0
        )

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"identical_shift_type": True},
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
        )

        viol_vars = list(constraint.violation_variables.values())
        model.minimize(sum(viol_vars))

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        total_violation = sum(solver.value(v) for v in viol_vars)
        # shift_day mismatches (1 vs 0) and shift_night mismatches (0 vs 1):
        # 2 violation variables should fire.
        assert total_violation == 2


class TestMaxWorkingWeekends:
    def test_hard_mode_infeasible_when_exceeding_limit(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """Two full weekends but max_working_weekends=1 is infeasible."""
        num_periods = 14  # two full weeks starting Monday
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)

        # Force worker_1 to work both Saturdays (periods 5 and 12).
        model.add(variables.get_assignment_var("worker_1", 5, "shift_day") == 1)
        model.add(variables.get_assignment_var("worker_1", 12, "shift_day") == 1)

        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"max_working_weekends": 1}
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
        )
        _pin_hard(model, constraint)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status == cp_model.INFEASIBLE

    def test_hard_mode_feasible_within_limit(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        num_periods = 14
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)

        model.add(variables.get_assignment_var("worker_1", 5, "shift_day") == 1)
        for st in shift_types:
            model.add(variables.get_assignment_var("worker_1", 12, st.id) == 0)
            model.add(variables.get_assignment_var("worker_1", 13, st.id) == 0)

        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"max_working_weekends": 1}
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
        )
        _pin_hard(model, constraint)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_soft_mode_penalizes_excess_weekends(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        num_periods = 14
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)

        model.add(variables.get_assignment_var("worker_1", 5, "shift_day") == 1)
        model.add(variables.get_assignment_var("worker_1", 12, "shift_day") == 1)

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_working_weekends": 1},
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
        )

        excess_var = constraint.violation_variables["wknd_max_total_excess_worker_1"]
        model.minimize(excess_var)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert solver.value(excess_var) == 1

    def test_negative_max_working_weekends_warns_and_ignores(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        num_periods = 14
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_working_weekends": -1},
        )
        constraint = WeekendConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(
                workers=workers,
                shift_types=shift_types,
                num_periods=num_periods,
                period_dates=period_dates,
            )

        assert not any(
            "max_total_excess" in name for name in constraint.violation_variables
        )
        assert "negative" in caplog.text.lower()


class TestMaxConsecutiveWeekends:
    def test_hard_mode_infeasible_when_exceeding_limit(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """
        Three consecutive full weekends but max_consecutive_weekends=1
        should be infeasible when worker_1 is forced to work all three
        Saturdays.
        """
        num_periods = 21  # three full weeks starting Monday
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)

        for saturday_period in (5, 12, 19):
            model.add(
                variables.get_assignment_var("worker_1", saturday_period, "shift_day")
                == 1
            )

        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"max_consecutive_weekends": 1}
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
        )
        _pin_hard(model, constraint)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status == cp_model.INFEASIBLE

    def test_hard_mode_feasible_with_gap(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """Working weekend 1 and 3 but not weekend 2 respects max_consecutive=1."""
        num_periods = 21
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)

        model.add(variables.get_assignment_var("worker_1", 5, "shift_day") == 1)
        model.add(variables.get_assignment_var("worker_1", 19, "shift_day") == 1)
        for period in (12, 13):
            for st in shift_types:
                model.add(variables.get_assignment_var("worker_1", period, st.id) == 0)

        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"max_consecutive_weekends": 1}
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
        )
        _pin_hard(model, constraint)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_soft_mode_penalizes_run_of_two(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        num_periods = 14
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)

        model.add(variables.get_assignment_var("worker_1", 5, "shift_day") == 1)
        model.add(variables.get_assignment_var("worker_1", 12, "shift_day") == 1)

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_consecutive_weekends": 1},
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
        )

        viol_vars = list(constraint.violation_variables.values())
        model.minimize(sum(viol_vars))

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert sum(solver.value(v) for v in viol_vars) == 1

    def test_too_few_weekend_groups_trivially_satisfied(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """Only one weekend group in the horizon: max_consecutive_weekends=3
        has nothing to constrain (window clamps smaller than max+1)."""
        num_periods = 7
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)

        model.add(variables.get_assignment_var("worker_1", 5, "shift_day") == 1)
        model.add(variables.get_assignment_var("worker_1", 6, "shift_day") == 1)

        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"max_consecutive_weekends": 3}
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
        )

        assert not any(
            "consec_excess" in name for name in constraint.violation_variables
        )

    def test_negative_max_consecutive_weekends_warns_and_ignores(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        num_periods = 14
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_consecutive_weekends": -1},
        )
        constraint = WeekendConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(
                workers=workers,
                shift_types=shift_types,
                num_periods=num_periods,
                period_dates=period_dates,
            )

        assert not any(
            "consec_excess" in name for name in constraint.violation_variables
        )
        assert "negative" in caplog.text.lower()


class TestCustomWeekendDays:
    def test_custom_weekend_days_groups_friday_saturday(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """weekend_days=[4, 5] (Fri, Sat) groups Friday+Saturday as one weekend."""
        num_periods = 7  # Mon..Sun
        model, variables = _build_model(workers, shift_types, num_periods)
        period_dates = _period_dates(MONDAY, num_periods)
        friday_period = 4
        saturday_period = 5

        model.add(
            variables.get_assignment_var("worker_1", friday_period, "shift_day") == 1
        )
        for st in shift_types:
            model.add(
                variables.get_assignment_var("worker_1", saturday_period, st.id) == 0
            )

        config = ConstraintConfig(
            enabled=True,
            is_hard=True,
            parameters={"weekend_days": [4, 5], "require_complete": True},
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
        )
        _pin_hard(model, constraint)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        # worker_1 works Friday but is forbidden from Saturday: with
        # weekend_days=[4,5] that's an incomplete Fri+Sat weekend -> infeasible.
        assert status == cp_model.INFEASIBLE

    def test_invalid_weekend_day_values_are_dropped(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        model, variables = _build_model(workers, shift_types, num_periods=7)
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            parameters={"weekend_days": [5, 6, 9], "require_complete": True},
        )
        constraint = WeekendConstraint(model, variables, config)

        with caplog.at_level(logging.WARNING):
            constraint.apply(
                workers=workers,
                shift_types=shift_types,
                num_periods=7,
                period_dates=_period_dates(MONDAY, 7),
            )

        # Should behave like the default [5, 6] (invalid 9 dropped), so
        # violation vars should still be created (not a full no-op).
        assert len(constraint.violation_variables) > 0
        assert "invalid weekday" in caplog.text.lower()


class TestWeekendObjectiveDoubleCount:
    """No aggregate 'total' debug var is created for this constraint (unlike
    sequence/frequency/max_absence), so there is nothing that could double-
    count -- this is asserted directly rather than assumed."""

    def test_no_auxiliary_total_variable(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        model, variables = _build_model(workers, shift_types, num_periods=7)
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"require_complete": True, "max_working_weekends": 1},
        )
        constraint = WeekendConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=7,
            period_dates=_period_dates(MONDAY, 7),
        )

        assert "total" not in constraint.violation_variables
        assert constraint.violation_variable_types == {}
