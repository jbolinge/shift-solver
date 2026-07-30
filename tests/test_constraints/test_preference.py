"""Tests for preference constraint."""

from datetime import date, time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.preference import PreferenceConstraint
from shift_solver.models import Availability, ShiftType, Worker
from shift_solver.solver.types import SolverVariables
from shift_solver.solver.variable_builder import VariableBuilder


@pytest.fixture
def workers() -> list[Worker]:
    """Create test workers (no preferences by default)."""
    return [
        Worker(id="worker_1", name="Worker 1"),
        Worker(id="worker_2", name="Worker 2"),
    ]


@pytest.fixture
def shift_types() -> list[ShiftType]:
    """Create shift types across two categories."""
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
def period_dates() -> list[tuple[date, date]]:
    """Create period dates (4 weeks, starting Monday 2026-01-05)."""
    return [
        (date(2026, 1, 5), date(2026, 1, 11)),
        (date(2026, 1, 12), date(2026, 1, 18)),
        (date(2026, 1, 19), date(2026, 1, 25)),
        (date(2026, 1, 26), date(2026, 2, 1)),
    ]


def build_model_and_vars(
    workers: list[Worker], shift_types: list[ShiftType], num_periods: int
) -> tuple[cp_model.CpModel, SolverVariables]:
    """Create a fresh model and solver variables."""
    model = cp_model.CpModel()
    builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
    variables = builder.build()
    return model, variables


@pytest.fixture
def model_and_variables(
    workers: list[Worker], shift_types: list[ShiftType]
) -> tuple[cp_model.CpModel, SolverVariables]:
    """Create model and variables for testing (4 periods)."""
    return build_model_and_vars(workers, shift_types, num_periods=4)


class TestPreferenceConstraintInit:
    """Tests for PreferenceConstraint initialization."""

    def test_init_default_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Default config: enabled, hard (BaseConstraint defaults)."""
        model, variables = model_and_variables
        constraint = PreferenceConstraint(model, variables)

        assert constraint.constraint_id == "preference"
        assert constraint.is_enabled
        assert constraint.is_hard
        assert constraint.weight == 100
        assert constraint.handles_hard_mode is True

    def test_init_soft_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Explicit soft config."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=50)
        constraint = PreferenceConstraint(model, variables, config)

        assert not constraint.is_hard
        assert constraint.weight == 50


class TestPreferenceConstraintDisabledAndEmpty:
    """Disabled / no-op edge cases."""

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
        constraint = PreferenceConstraint(model, variables, config)

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=[],
            period_dates=period_dates,
        )

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0

    def test_no_preferences_and_no_availabilities_is_noop(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Workers without preferred_shifts and no availabilities -> no-op."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=10)
        constraint = PreferenceConstraint(model, variables, config)

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=[],
            period_dates=period_dates,
        )

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0

    def test_empty_availabilities_param_missing_defaults_to_empty(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """availabilities key absent from context -> treated as empty list."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=10)
        constraint = PreferenceConstraint(model, variables, config)

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            period_dates=period_dates,
        )

        assert len(constraint.violation_variables) == 0


class TestWorkerPreferredShiftsSoft:
    """Sub-rule (a): Worker.preferred_shifts, soft mode."""

    def test_creates_violation_for_non_preferred_shift_types_only(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Worker preferring shift_day gets viol vars only for shift_night."""
        workers = [
            Worker(
                id="worker_1",
                name="Worker 1",
                preferred_shifts=frozenset({"shift_day"}),
            ),
            Worker(id="worker_2", name="Worker 2"),
        ]
        model, variables = build_model_and_vars(workers, shift_types, num_periods=4)

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=10,
            parameters={"worker_preferred_weight": 7},
        )
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=[],
            period_dates=period_dates,
        )

        # worker_1: 4 periods * 1 non-preferred shift type (shift_night) = 4
        # worker_2: no preferred_shifts -> no violations at all
        expected_names = {
            f"pref_worker_viol_worker_1_shift_night_p{p}" for p in range(4)
        }
        assert set(constraint.violation_variables.keys()) == expected_names
        for name in expected_names:
            assert constraint.violation_priorities[name] == 7

    def test_violation_equals_assignment_var_when_assigned(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """viol == x: forcing the non-preferred assignment forces viol=1."""
        workers = [
            Worker(
                id="worker_1",
                name="Worker 1",
                preferred_shifts=frozenset({"shift_day"}),
            ),
        ]
        model, variables = build_model_and_vars(workers, shift_types, num_periods=1)

        config = ConstraintConfig(enabled=True, is_hard=False, weight=10)
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            availabilities=[],
            period_dates=period_dates[:1],
        )

        assignment_var = variables.get_assignment_var("worker_1", 0, "shift_night")
        model.add(assignment_var == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        viol_var = constraint.violation_variables[
            "pref_worker_viol_worker_1_shift_night_p0"
        ]
        assert solver.value(viol_var) == 1

    def test_violation_zero_when_not_assigned(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """viol == 0 when the non-preferred shift is not assigned."""
        workers = [
            Worker(
                id="worker_1",
                name="Worker 1",
                preferred_shifts=frozenset({"shift_day"}),
            ),
        ]
        model, variables = build_model_and_vars(workers, shift_types, num_periods=1)

        config = ConstraintConfig(enabled=True, is_hard=False, weight=10)
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            availabilities=[],
            period_dates=period_dates[:1],
        )

        assignment_var = variables.get_assignment_var("worker_1", 0, "shift_night")
        model.add(assignment_var == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        viol_var = constraint.violation_variables[
            "pref_worker_viol_worker_1_shift_night_p0"
        ]
        assert solver.value(viol_var) == 0

    def test_solver_prefers_preferred_shift_when_weighted(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """With coverage forcing exactly one shift and a high penalty, the
        solver should route the worker toward their preferred shift type
        when feasible."""
        workers = [
            Worker(
                id="worker_1",
                name="Worker 1",
                preferred_shifts=frozenset({"shift_day"}),
            ),
            Worker(id="worker_2", name="Worker 2"),
        ]
        model, variables = build_model_and_vars(workers, shift_types, num_periods=1)

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=1000,
            parameters={"worker_preferred_weight": 1},
        )
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            availabilities=[],
            period_dates=period_dates[:1],
        )

        for shift_type in shift_types:
            vars_for_shift = [
                variables.get_assignment_var(w.id, 0, shift_type.id) for w in workers
            ]
            model.add(sum(vars_for_shift) == 1)

        # Each worker works at most one shift this period, and worker_1 must
        # work exactly one -- otherwise the solver could trivially avoid the
        # violation by leaving worker_1 unassigned entirely, which would
        # defeat the point of this test.
        for worker in workers:
            per_worker_vars = [
                variables.get_assignment_var(worker.id, 0, st.id) for st in shift_types
            ]
            model.add(sum(per_worker_vars) <= 1)
        worker_1_vars = [
            variables.get_assignment_var("worker_1", 0, st.id) for st in shift_types
        ]
        model.add(sum(worker_1_vars) == 1)

        penalty_terms = [
            viol_var * constraint.violation_priorities[name] * config.weight
            for name, viol_var in constraint.violation_variables.items()
        ]
        model.minimize(sum(penalty_terms))

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        assert (
            solver.value(variables.get_assignment_var("worker_1", 0, "shift_day")) == 1
        )
        assert (
            solver.value(variables.get_assignment_var("worker_1", 0, "shift_night"))
            == 0
        )


class TestWorkerPreferredShiftsHard:
    """Sub-rule (a) under config.is_hard=True."""

    def test_hard_mode_forbids_non_preferred_assignment(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Hard mode: non-preferred assignment is infeasible when forced."""
        workers = [
            Worker(
                id="worker_1",
                name="Worker 1",
                preferred_shifts=frozenset({"shift_day"}),
            ),
        ]
        model, variables = build_model_and_vars(workers, shift_types, num_periods=1)

        config = ConstraintConfig(enabled=True, is_hard=True, weight=100)
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            availabilities=[],
            period_dates=period_dates[:1],
        )

        # No violation variables should be registered (hard mode).
        assert len(constraint.violation_variables) == 0

        # Forcing the non-preferred assignment must be infeasible.
        model.add(variables.get_assignment_var("worker_1", 0, "shift_night") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE

    def test_hard_mode_allows_preferred_assignment(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Hard mode: preferred assignment remains feasible."""
        workers = [
            Worker(
                id="worker_1",
                name="Worker 1",
                preferred_shifts=frozenset({"shift_day"}),
            ),
        ]
        model, variables = build_model_and_vars(workers, shift_types, num_periods=1)

        config = ConstraintConfig(enabled=True, is_hard=True, weight=100)
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            availabilities=[],
            period_dates=period_dates[:1],
        )

        model.add(variables.get_assignment_var("worker_1", 0, "shift_day") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert (
            solver.value(variables.get_assignment_var("worker_1", 0, "shift_day")) == 1
        )


class TestAvailabilityPreferredSoft:
    """Sub-rule (b): 'preferred' availability windows, soft mode."""

    def test_creates_one_violation_per_record(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """One violation var registered per 'preferred' availability record."""
        model, variables = build_model_and_vars(workers, shift_types, num_periods=4)

        availabilities = [
            Availability(
                worker_id="worker_1",
                start_date=date(2026, 1, 12),
                end_date=date(2026, 1, 18),
                availability_type="preferred",
            )
        ]

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=5,
            parameters={"availability_preferred_weight": 5},
        )
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        assert len(constraint.violation_variables) == 1
        name = "pref_avail_viol_worker_1_r0"
        assert name in constraint.violation_variables
        assert constraint.violation_priorities[name] == 5

    def test_violation_one_when_worker_not_assigned_in_window(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """viol=1 iff the worker has zero assignments across the window."""
        model, variables = build_model_and_vars(workers, shift_types, num_periods=4)

        availabilities = [
            Availability(
                worker_id="worker_1",
                start_date=date(2026, 1, 12),
                end_date=date(2026, 1, 18),
                availability_type="preferred",
            )
        ]

        config = ConstraintConfig(enabled=True, is_hard=False, weight=5)
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        # Force no assignment for worker_1 in period 1 (the only overlapping period)
        for shift_type in shift_types:
            model.add(variables.get_assignment_var("worker_1", 1, shift_type.id) == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        viol_var = constraint.violation_variables["pref_avail_viol_worker_1_r0"]
        assert solver.value(viol_var) == 1

    def test_violation_zero_when_worker_assigned_in_window(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """viol=0 when the worker is assigned at least once in the window."""
        model, variables = build_model_and_vars(workers, shift_types, num_periods=4)

        availabilities = [
            Availability(
                worker_id="worker_1",
                start_date=date(2026, 1, 12),
                end_date=date(2026, 1, 18),
                availability_type="preferred",
                shift_type_id="shift_day",
            )
        ]

        config = ConstraintConfig(enabled=True, is_hard=False, weight=5)
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        model.add(variables.get_assignment_var("worker_1", 1, "shift_day") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        viol_var = constraint.violation_variables["pref_avail_viol_worker_1_r0"]
        assert solver.value(viol_var) == 0

    def test_shift_type_id_restricts_candidate_vars(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """When shift_type_id is set, only that shift type counts toward
        satisfying the preference -- being assigned a different shift type
        in the window still counts as a violation."""
        model, variables = build_model_and_vars(workers, shift_types, num_periods=4)

        availabilities = [
            Availability(
                worker_id="worker_1",
                start_date=date(2026, 1, 12),
                end_date=date(2026, 1, 18),
                availability_type="preferred",
                shift_type_id="shift_day",
            )
        ]

        config = ConstraintConfig(enabled=True, is_hard=False, weight=5)
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        # Assign worker_1 to shift_night (not shift_day) in the overlapping period.
        model.add(variables.get_assignment_var("worker_1", 1, "shift_night") == 1)
        model.add(variables.get_assignment_var("worker_1", 1, "shift_day") == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        viol_var = constraint.violation_variables["pref_avail_viol_worker_1_r0"]
        assert solver.value(viol_var) == 1


class TestAvailabilityPreferredHard:
    """Sub-rule (b) under config.is_hard=True."""

    def test_hard_mode_pins_violation_to_zero(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Hard mode forces the preferred window to actually be worked."""
        model, variables = build_model_and_vars(workers, shift_types, num_periods=4)

        availabilities = [
            Availability(
                worker_id="worker_1",
                start_date=date(2026, 1, 12),
                end_date=date(2026, 1, 18),
                availability_type="preferred",
            )
        ]

        config = ConstraintConfig(enabled=True, is_hard=True, weight=5)
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        assert len(constraint.violation_variables) == 0

        # Forcing zero assignment for worker_1 in period 1 must be infeasible.
        for shift_type in shift_types:
            model.add(variables.get_assignment_var("worker_1", 1, shift_type.id) == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE


class TestAvailabilityRequired:
    """Sub-rule (c): 'required' availability windows."""

    def test_required_is_hard_even_when_config_is_soft(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """'required' is always enforced hard, regardless of config.is_hard."""
        model, variables = build_model_and_vars(workers, shift_types, num_periods=4)

        availabilities = [
            Availability(
                worker_id="worker_1",
                start_date=date(2026, 1, 12),
                end_date=date(2026, 1, 18),
                availability_type="required",
            )
        ]

        config = ConstraintConfig(enabled=True, is_hard=False, weight=5)
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        # No violation variables for 'required' records.
        assert len(constraint.violation_variables) == 0

        for shift_type in shift_types:
            model.add(variables.get_assignment_var("worker_1", 1, shift_type.id) == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status == cp_model.INFEASIBLE

    def test_required_satisfied_is_feasible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Assigning at least one candidate shift in the window is feasible."""
        model, variables = build_model_and_vars(workers, shift_types, num_periods=4)

        availabilities = [
            Availability(
                worker_id="worker_1",
                start_date=date(2026, 1, 12),
                end_date=date(2026, 1, 18),
                availability_type="required",
                shift_type_id="shift_day",
            )
        ]

        config = ConstraintConfig(enabled=True, is_hard=False, weight=5)
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        model.add(variables.get_assignment_var("worker_1", 1, "shift_day") == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_honor_required_availability_false_disables_required_rule(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """honor_required_availability=False makes 'required' records inert."""
        model, variables = build_model_and_vars(workers, shift_types, num_periods=4)

        availabilities = [
            Availability(
                worker_id="worker_1",
                start_date=date(2026, 1, 12),
                end_date=date(2026, 1, 18),
                availability_type="required",
            )
        ]

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=5,
            parameters={"honor_required_availability": False},
        )
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        assert constraint.constraint_count == 0

        for shift_type in shift_types:
            model.add(variables.get_assignment_var("worker_1", 1, shift_type.id) == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_required_window_overlaps_zero_periods_warns_and_skips(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """A 'required' record entirely outside the horizon is skipped, not
        infeasible."""
        model, variables = build_model_and_vars(workers, shift_types, num_periods=4)

        availabilities = [
            Availability(
                worker_id="worker_1",
                start_date=date(2027, 1, 1),
                end_date=date(2027, 1, 7),
                availability_type="required",
            )
        ]

        config = ConstraintConfig(enabled=True, is_hard=False, weight=5)
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        assert constraint.constraint_count == 0

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_unknown_shift_type_id_warns_and_skips(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Unknown shift_type_id on a record is skipped rather than raising."""
        model, variables = build_model_and_vars(workers, shift_types, num_periods=4)

        availabilities = [
            Availability(
                worker_id="worker_1",
                start_date=date(2026, 1, 12),
                end_date=date(2026, 1, 18),
                availability_type="required",
                shift_type_id="does_not_exist",
            )
        ]

        config = ConstraintConfig(enabled=True, is_hard=False, weight=5)
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        assert constraint.constraint_count == 0

    def test_unknown_worker_id_warns_and_skips(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Unknown worker_id on a record is skipped rather than raising."""
        model, variables = build_model_and_vars(workers, shift_types, num_periods=4)

        availabilities = [
            Availability(
                worker_id="does_not_exist",
                start_date=date(2026, 1, 12),
                end_date=date(2026, 1, 18),
                availability_type="preferred",
            )
        ]

        config = ConstraintConfig(enabled=True, is_hard=False, weight=5)
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        assert constraint.constraint_count == 0
        assert len(constraint.violation_variables) == 0

    def test_unavailable_type_is_ignored(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """availability_type='unavailable' is not this constraint's concern."""
        model, variables = build_model_and_vars(workers, shift_types, num_periods=4)

        availabilities = [
            Availability(
                worker_id="worker_1",
                start_date=date(2026, 1, 12),
                end_date=date(2026, 1, 18),
                availability_type="unavailable",
            )
        ]

        config = ConstraintConfig(enabled=True, is_hard=False, weight=5)
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        assert constraint.constraint_count == 0
        assert len(constraint.violation_variables) == 0


class TestParameterDefaultsAndNoneHandling:
    """Missing/None parameters fall back to documented defaults."""

    def test_missing_parameters_dict_uses_defaults(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """parameters=None -> worker_preferred_weight defaults to 1."""
        workers = [
            Worker(
                id="worker_1",
                name="Worker 1",
                preferred_shifts=frozenset({"shift_day"}),
            ),
        ]
        model, variables = build_model_and_vars(workers, shift_types, num_periods=1)

        config = ConstraintConfig(enabled=True, is_hard=False, weight=10)
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            availabilities=[],
            period_dates=period_dates[:1],
        )

        name = "pref_worker_viol_worker_1_shift_night_p0"
        assert constraint.violation_priorities[name] == 1

    def test_explicit_none_parameter_treated_as_absent(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """An explicit None value for a param falls back to its default."""
        workers = [
            Worker(
                id="worker_1",
                name="Worker 1",
                preferred_shifts=frozenset({"shift_day"}),
            ),
        ]
        model, variables = build_model_and_vars(workers, shift_types, num_periods=1)

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=10,
            parameters={
                "worker_preferred_weight": None,
                "honor_required_availability": None,
            },
        )
        constraint = PreferenceConstraint(model, variables, config)

        availabilities = [
            Availability(
                worker_id="worker_1",
                start_date=date(2026, 1, 5),
                end_date=date(2026, 1, 11),
                availability_type="required",
            )
        ]
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            availabilities=availabilities,
            period_dates=period_dates[:1],
        )

        name = "pref_worker_viol_worker_1_shift_night_p0"
        assert constraint.violation_priorities[name] == 1
        # honor_required_availability defaulted back to True -> hard constraint added
        assert constraint.constraint_count > 0


class TestViolationVariableTypesNotDoubleCounted:
    """No auxiliary/total vars leak into violation_variable_types by mistake."""

    def test_no_unexpected_auxiliary_markers(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """This constraint doesn't build derived 'total' sums, so
        violation_variable_types should stay empty."""
        model, variables = build_model_and_vars(workers, shift_types, num_periods=4)
        availabilities = [
            Availability(
                worker_id="worker_1",
                start_date=date(2026, 1, 12),
                end_date=date(2026, 1, 18),
                availability_type="preferred",
            )
        ]

        config = ConstraintConfig(enabled=True, is_hard=False, weight=5)
        constraint = PreferenceConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        assert constraint.violation_variable_types == {}
