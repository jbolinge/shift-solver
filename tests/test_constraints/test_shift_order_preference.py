"""Tests for shift order preference constraint."""

from datetime import date, time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.shift_order_preference import (
    ShiftOrderPreferenceConstraint,
)
from shift_solver.models import Availability, ShiftOrderPreference, ShiftType, Worker
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
    """Create shift types with distinct categories."""
    return [
        ShiftType(
            id="day_shift",
            name="Day Shift",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=1,
        ),
        ShiftType(
            id="night_shift",
            name="Night Shift",
            category="night",
            start_time=time(23, 0),
            end_time=time(7, 0),
            duration_hours=8.0,
            workers_required=1,
        ),
        ShiftType(
            id="weekend_shift",
            name="Weekend Shift",
            category="weekend",
            start_time=time(7, 0),
            end_time=time(19, 0),
            duration_hours=12.0,
            workers_required=1,
        ),
    ]


@pytest.fixture
def period_dates() -> list[tuple[date, date]]:
    """Create 4 weekly periods."""
    base = date(2026, 1, 5)
    from datetime import timedelta

    return [
        (base + timedelta(weeks=i), base + timedelta(weeks=i, days=6))
        for i in range(4)
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


class TestShiftOrderPreferenceInit:
    """Tests for ShiftOrderPreferenceConstraint initialization."""

    def test_default_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Test initialization with default config."""
        model, variables = model_and_variables
        constraint = ShiftOrderPreferenceConstraint(model, variables)

        assert constraint.constraint_id == "shift_order_preference"
        assert constraint.is_enabled
        assert constraint.is_hard
        assert constraint.weight == 100

    def test_soft_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Test initialization with explicit soft config."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=200)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        assert constraint.is_enabled
        assert not constraint.is_hard
        assert constraint.weight == 200


class TestShiftOrderPreferenceApply:
    """Tests for ShiftOrderPreferenceConstraint.apply()."""

    def test_disabled_does_nothing(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Disabled constraint adds nothing."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=False)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            period_dates=period_dates,
            availabilities=[],
            shift_order_preferences=[
                ShiftOrderPreference(
                    rule_id="test",
                    trigger_type="shift_type",
                    trigger_value="day_shift",
                    direction="after",
                    preferred_type="shift_type",
                    preferred_value="night_shift",
                )
            ],
        )

        assert len(constraint.violation_variables) == 0

    def test_no_rules_does_nothing(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """No rules means no violation variables."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=200)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            period_dates=period_dates,
            availabilities=[],
            shift_order_preferences=[],
        )

        assert len(constraint.violation_variables) == 0

    def test_few_periods_does_nothing(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """With fewer than 2 periods, no pairs to check."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()
        config = ConstraintConfig(enabled=True, is_hard=False, weight=200)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            period_dates=[(date(2026, 1, 5), date(2026, 1, 11))],
            availabilities=[],
            shift_order_preferences=[
                ShiftOrderPreference(
                    rule_id="test",
                    trigger_type="shift_type",
                    trigger_value="day_shift",
                    direction="after",
                    preferred_type="shift_type",
                    preferred_value="night_shift",
                )
            ],
        )

        assert len(constraint.violation_variables) == 0

    def test_shift_type_trigger_after_creates_violations(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """shift_type trigger with direction=after creates violation variables."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=200)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        preferences = [
            ShiftOrderPreference(
                rule_id="day_then_night",
                trigger_type="shift_type",
                trigger_value="day_shift",
                direction="after",
                preferred_type="shift_type",
                preferred_value="night_shift",
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            period_dates=period_dates,
            availabilities=[],
            shift_order_preferences=preferences,
        )

        # 3 workers x 3 adjacent pairs (0-1, 1-2, 2-3) = 9 violations
        assert len(constraint.violation_variables) == 9

    def test_category_trigger_after_creates_violations(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """category trigger creates violation variables."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=200)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        preferences = [
            ShiftOrderPreference(
                rule_id="weekend_then_night",
                trigger_type="category",
                trigger_value="weekend",
                direction="after",
                preferred_type="category",
                preferred_value="night",
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            period_dates=period_dates,
            availabilities=[],
            shift_order_preferences=preferences,
        )

        # 3 workers x 3 pairs = 9 violations
        assert len(constraint.violation_variables) == 9

    def test_direction_before_creates_violations(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """direction=before creates violations for (preferred=N, trigger=N+1) pairs."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=200)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        preferences = [
            ShiftOrderPreference(
                rule_id="night_before_weekend",
                trigger_type="shift_type",
                trigger_value="weekend_shift",
                direction="before",
                preferred_type="shift_type",
                preferred_value="night_shift",
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            period_dates=period_dates,
            availabilities=[],
            shift_order_preferences=preferences,
        )

        # 3 workers x 3 pairs = 9 violations
        assert len(constraint.violation_variables) == 9

    def test_unavailability_trigger_creates_violations(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """unavailability trigger creates violations only for unavailable periods."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=200)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        # W001 unavailable in period 2
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[2][0],
                end_date=period_dates[2][1],
                availability_type="unavailable",
            ),
        ]

        preferences = [
            ShiftOrderPreference(
                rule_id="night_before_vacation",
                trigger_type="unavailability",
                trigger_value=None,
                direction="before",
                preferred_type="shift_type",
                preferred_value="night_shift",
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            period_dates=period_dates,
            availabilities=availabilities,
            shift_order_preferences=preferences,
        )

        # Only W001 is unavailable in period 2
        # direction=before: preferred at N when trigger at N+1
        # So when period 2 is unavailable, prefer night_shift at period 1
        # Only 1 violation variable for W001
        assert len(constraint.violation_variables) == 1
        # Verify variable name
        assert any(
            "W001" in name and "night_before_vacation" in name
            for name in constraint.violation_variables
        )

    def test_unavailability_trigger_after(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """unavailability trigger with direction=after creates violations."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=200)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        # W001 unavailable in period 1
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                availability_type="unavailable",
            ),
        ]

        preferences = [
            ShiftOrderPreference(
                rule_id="easy_after_vacation",
                trigger_type="unavailability",
                trigger_value=None,
                direction="after",
                preferred_type="shift_type",
                preferred_value="day_shift",
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            period_dates=period_dates,
            availabilities=availabilities,
            shift_order_preferences=preferences,
        )

        # direction=after: trigger at N, preferred at N+1
        # W001 unavailable at period 1 -> prefer day_shift at period 2
        assert len(constraint.violation_variables) == 1


class TestShiftOrderPreferenceSolve:
    """Integration tests that solve with shift order preference constraint."""

    def test_soft_constraint_encourages_preferred_shift(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Soft constraint should encourage preferred shift after trigger."""
        model = cp_model.CpModel()
        num_periods = 4
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        config = ConstraintConfig(enabled=True, is_hard=False, weight=1000)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        preferences = [
            ShiftOrderPreference(
                rule_id="day_then_night",
                trigger_type="shift_type",
                trigger_value="day_shift",
                direction="after",
                preferred_type="shift_type",
                preferred_value="night_shift",
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
            availabilities=[],
            shift_order_preferences=preferences,
        )

        # Add basic coverage
        for period in range(num_periods):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Force W001 to work day_shift in period 0
        model.add(variables.get_assignment_var("W001", 0, "day_shift") == 1)

        # Minimize violations
        if constraint.violation_variables:
            model.minimize(
                sum(constraint.violation_variables.values()) * constraint.weight
            )

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # W001 should be assigned night_shift in period 1 to satisfy preference
        night_val = solver.value(
            variables.get_assignment_var("W001", 1, "night_shift")
        )
        assert night_val == 1

    def test_unavailability_trigger_solve(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Solve with unavailability trigger encouraging preferred shift."""
        model = cp_model.CpModel()
        num_periods = 4
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        config = ConstraintConfig(enabled=True, is_hard=False, weight=1000)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        # W001 unavailable in period 2
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[2][0],
                end_date=period_dates[2][1],
                availability_type="unavailable",
            ),
        ]

        preferences = [
            ShiftOrderPreference(
                rule_id="night_before_vacation",
                trigger_type="unavailability",
                trigger_value=None,
                direction="before",
                preferred_type="shift_type",
                preferred_value="night_shift",
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
            availabilities=availabilities,
            shift_order_preferences=preferences,
        )

        # Add basic coverage
        for period in range(num_periods):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Block W001 from all shifts in period 2 (unavailable)
        for st in shift_types:
            model.add(variables.get_assignment_var("W001", 2, st.id) == 0)

        # Minimize violations
        if constraint.violation_variables:
            model.minimize(
                sum(constraint.violation_variables.values()) * constraint.weight
            )

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # W001 should work night_shift in period 1 (before vacation in period 2)
        night_val = solver.value(
            variables.get_assignment_var("W001", 1, "night_shift")
        )
        assert night_val == 1

    def test_category_to_category_solve(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Solve with category trigger and category preferred."""
        model = cp_model.CpModel()
        num_periods = 4
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        config = ConstraintConfig(enabled=True, is_hard=False, weight=1000)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        preferences = [
            ShiftOrderPreference(
                rule_id="weekend_then_night",
                trigger_type="category",
                trigger_value="weekend",
                direction="after",
                preferred_type="category",
                preferred_value="night",
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            period_dates=period_dates,
            availabilities=[],
            shift_order_preferences=preferences,
        )

        # Add basic coverage
        for period in range(num_periods):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Force W001 to work weekend_shift in period 0
        model.add(variables.get_assignment_var("W001", 0, "weekend_shift") == 1)

        # Minimize violations
        if constraint.violation_variables:
            model.minimize(
                sum(constraint.violation_variables.values()) * constraint.weight
            )

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # W001 should be assigned night_shift in period 1
        night_val = solver.value(
            variables.get_assignment_var("W001", 1, "night_shift")
        )
        assert night_val == 1


class TestShiftOrderPreferenceEdgeCases:
    """Tests for edge cases in shift order preference constraint."""

    def test_unknown_shift_type_trigger_skipped(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Unknown shift type trigger produces no violations."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=200)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        preferences = [
            ShiftOrderPreference(
                rule_id="test",
                trigger_type="shift_type",
                trigger_value="nonexistent_shift",
                direction="after",
                preferred_type="shift_type",
                preferred_value="night_shift",
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            period_dates=period_dates,
            availabilities=[],
            shift_order_preferences=preferences,
        )

        assert len(constraint.violation_variables) == 0

    def test_unknown_category_trigger_skipped(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Unknown category trigger produces no violations."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=200)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        preferences = [
            ShiftOrderPreference(
                rule_id="test",
                trigger_type="category",
                trigger_value="nonexistent_cat",
                direction="after",
                preferred_type="shift_type",
                preferred_value="night_shift",
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            period_dates=period_dates,
            availabilities=[],
            shift_order_preferences=preferences,
        )

        assert len(constraint.violation_variables) == 0

    def test_unknown_preferred_shift_type_skipped(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Unknown preferred shift type produces no violations."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=200)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        preferences = [
            ShiftOrderPreference(
                rule_id="test",
                trigger_type="shift_type",
                trigger_value="day_shift",
                direction="after",
                preferred_type="shift_type",
                preferred_value="nonexistent_shift",
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            period_dates=period_dates,
            availabilities=[],
            shift_order_preferences=preferences,
        )

        assert len(constraint.violation_variables) == 0

    def test_unknown_preferred_category_skipped(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Unknown preferred category produces no violations."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=200)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        preferences = [
            ShiftOrderPreference(
                rule_id="test",
                trigger_type="shift_type",
                trigger_value="day_shift",
                direction="after",
                preferred_type="category",
                preferred_value="nonexistent_cat",
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            period_dates=period_dates,
            availabilities=[],
            shift_order_preferences=preferences,
        )

        assert len(constraint.violation_variables) == 0

    def test_restricted_worker_skipped_for_preferred(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Worker restricted from preferred shift has no violations for that pair."""
        workers = [
            Worker(
                id="W001",
                name="Worker 1",
                restricted_shifts=frozenset(["night_shift"]),
            ),
            Worker(id="W002", name="Worker 2"),
        ]
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        config = ConstraintConfig(enabled=True, is_hard=False, weight=200)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        preferences = [
            ShiftOrderPreference(
                rule_id="day_then_night",
                trigger_type="shift_type",
                trigger_value="day_shift",
                direction="after",
                preferred_type="shift_type",
                preferred_value="night_shift",
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            period_dates=period_dates,
            availabilities=[],
            shift_order_preferences=preferences,
        )

        # W001 restricted from night_shift -> 0 violations for W001
        # W002 can work night_shift -> 3 violations for W002
        assert len(constraint.violation_variables) == 3
        assert all(
            "W002" in name for name in constraint.violation_variables
        )

    def test_worker_ids_filtering(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """worker_ids scopes rule to specific workers."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=200)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        preferences = [
            ShiftOrderPreference(
                rule_id="day_then_night",
                trigger_type="shift_type",
                trigger_value="day_shift",
                direction="after",
                preferred_type="shift_type",
                preferred_value="night_shift",
                worker_ids=frozenset(["W001"]),
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            period_dates=period_dates,
            availabilities=[],
            shift_order_preferences=preferences,
        )

        # Only W001 -> 3 violations
        assert len(constraint.violation_variables) == 3
        assert all(
            "W001" in name for name in constraint.violation_variables
        )

    def test_multiple_rules(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Multiple rules create independent violation variables."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=200)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        preferences = [
            ShiftOrderPreference(
                rule_id="rule_a",
                trigger_type="shift_type",
                trigger_value="day_shift",
                direction="after",
                preferred_type="shift_type",
                preferred_value="night_shift",
                worker_ids=frozenset(["W001"]),
            ),
            ShiftOrderPreference(
                rule_id="rule_b",
                trigger_type="shift_type",
                trigger_value="weekend_shift",
                direction="before",
                preferred_type="shift_type",
                preferred_value="night_shift",
                worker_ids=frozenset(["W002"]),
            ),
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            period_dates=period_dates,
            availabilities=[],
            shift_order_preferences=preferences,
        )

        # rule_a: W001, 3 pairs = 3
        # rule_b: W002, 3 pairs = 3
        assert len(constraint.violation_variables) == 6
        assert sum(1 for n in constraint.violation_variables if "rule_a" in n) == 3
        assert sum(1 for n in constraint.violation_variables if "rule_b" in n) == 3

    def test_priority_stored_in_violation_priorities(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Priority from rule is stored in _violation_priorities."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=200)
        constraint = ShiftOrderPreferenceConstraint(model, variables, config)

        preferences = [
            ShiftOrderPreference(
                rule_id="high_prio",
                trigger_type="shift_type",
                trigger_value="day_shift",
                direction="after",
                preferred_type="shift_type",
                preferred_value="night_shift",
                priority=3,
                worker_ids=frozenset(["W001"]),
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            period_dates=period_dates,
            availabilities=[],
            shift_order_preferences=preferences,
        )

        assert len(constraint.violation_priorities) == 3
        assert all(p == 3 for p in constraint.violation_priorities.values())
