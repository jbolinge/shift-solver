"""Tests for worker shift limit constraint."""

from datetime import date, time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.coverage import CoverageConstraint
from shift_solver.constraints.worker_shift_limit import WorkerShiftLimitConstraint
from shift_solver.models import ShiftType, Worker
from shift_solver.solver import VariableBuilder


class TestWorkerShiftLimitConstraint:
    """Tests for WorkerShiftLimitConstraint."""

    @pytest.fixture
    def model(self) -> cp_model.CpModel:
        """Create a fresh CP model."""
        return cp_model.CpModel()

    @pytest.fixture
    def shift_types(self) -> list[ShiftType]:
        """Create sample shift types."""
        return [
            ShiftType(
                id="morning",
                name="Morning Shift",
                category="day",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="afternoon",
                name="Afternoon Shift",
                category="day",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

    def test_default_limit_blocks_double_booking(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """Default max_shifts_per_period=1 prevents a worker from holding two shifts."""
        workers = [Worker(id="W001", name="Alice")]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = WorkerShiftLimitConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        # Force the worker onto both morning and afternoon
        model.add(variables.get_assignment_var("W001", 0, "morning") == 1)
        model.add(variables.get_assignment_var("W001", 0, "afternoon") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.INFEASIBLE

    def test_default_limit_allows_single_shift(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """Default limit allows exactly one shift per worker per period."""
        workers = [Worker(id="W001", name="Alice")]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = WorkerShiftLimitConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        model.add(variables.get_assignment_var("W001", 0, "morning") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        assert solver.Value(variables.get_assignment_var("W001", 0, "morning")) == 1
        assert solver.Value(variables.get_assignment_var("W001", 0, "afternoon")) == 0
        assert solver.Value(variables.get_assignment_var("W001", 0, "night")) == 0

    def test_param_max_shifts_per_period_two(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """max_shifts_per_period=2 allows exactly two shifts but not three."""
        workers = [Worker(id="W001", name="Alice")]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"max_shifts_per_period": 2}
        )
        constraint = WorkerShiftLimitConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        # Two shifts should be feasible
        model.add(variables.get_assignment_var("W001", 0, "morning") == 1)
        model.add(variables.get_assignment_var("W001", 0, "afternoon") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Three shifts (all of them) should be infeasible
        model2 = cp_model.CpModel()
        builder2 = VariableBuilder(model2, workers, shift_types, num_periods=1)
        variables2 = builder2.build()
        constraint2 = WorkerShiftLimitConstraint(model2, variables2, config)
        constraint2.apply(workers=workers, shift_types=shift_types, num_periods=1)
        model2.add(variables2.get_assignment_var("W001", 0, "morning") == 1)
        model2.add(variables2.get_assignment_var("W001", 0, "afternoon") == 1)
        model2.add(variables2.get_assignment_var("W001", 0, "night") == 1)

        solver2 = cp_model.CpSolver()
        status2 = solver2.Solve(model2)
        assert status2 == cp_model.INFEASIBLE

    def test_limit_applies_independently_per_period(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """A worker may hold one shift in each of several periods."""
        workers = [Worker(id="W001", name="Alice")]

        builder = VariableBuilder(model, workers, shift_types, num_periods=3)
        variables = builder.build()

        constraint = WorkerShiftLimitConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        for period in range(3):
            model.add(variables.get_assignment_var("W001", period, "morning") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        for period in range(3):
            assert (
                solver.Value(variables.get_assignment_var("W001", period, "morning"))
                == 1
            )

    def test_disabled_allows_double_booking(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """Disabled constraint does not restrict multi-shift assignment."""
        workers = [Worker(id="W001", name="Alice")]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(enabled=False)
        constraint = WorkerShiftLimitConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        model.add(variables.get_assignment_var("W001", 0, "morning") == 1)
        model.add(variables.get_assignment_var("W001", 0, "afternoon") == 1)
        model.add(variables.get_assignment_var("W001", 0, "night") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        assert constraint.constraint_count == 0

    def test_constraint_count(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """One constraint is added per worker per period."""
        workers = [
            Worker(id="W001", name="Alice"),
            Worker(id="W002", name="Bob"),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        constraint = WorkerShiftLimitConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # 2 workers * 4 periods = 8 constraints
        assert constraint.constraint_count == 8

    def test_interaction_with_coverage_feasibility(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """Coverage requiring more distinct shifts than workers is infeasible."""
        # Only 1 worker but 3 shift types each need 1 worker in the same period
        workers = [Worker(id="W001", name="Solo")]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        coverage = CoverageConstraint(model, variables)
        coverage.apply(workers=workers, shift_types=shift_types, num_periods=1)

        limit = WorkerShiftLimitConstraint(model, variables)
        limit.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        # Solo worker can't cover 3 separate 1-person shifts at once
        assert status == cp_model.INFEASIBLE

    def test_interaction_with_coverage_feasible_when_enough_workers(
        self, shift_types: list[ShiftType]
    ) -> None:
        """Coverage and exclusivity are both satisfiable with enough workers."""
        model = cp_model.CpModel()
        workers = [
            Worker(id="W001", name="Alice"),
            Worker(id="W002", name="Bob"),
            Worker(id="W003", name="Charlie"),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        coverage = CoverageConstraint(model, variables)
        coverage.apply(workers=workers, shift_types=shift_types, num_periods=1)

        limit = WorkerShiftLimitConstraint(model, variables)
        limit.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        # Each of the 3 shifts should have exactly 1 worker
        for st in shift_types:
            count = sum(
                solver.Value(variables.get_assignment_var(w.id, 0, st.id))
                for w in workers
            )
            assert count == 1


class TestWorkerShiftLimitConstraintEdgeCases:
    """Edge case tests for WorkerShiftLimitConstraint."""

    def test_init_default_config(self) -> None:
        """Default config uses BaseConstraint defaults (hard, enabled)."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Alice")]
        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = WorkerShiftLimitConstraint(model, variables)

        assert constraint.constraint_id == "worker_shift_limit"
        assert constraint.is_enabled
        assert constraint.is_hard

    def test_default_param_when_not_specified(self) -> None:
        """get_param defaults to 1 when max_shifts_per_period is not set."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Alice")]
        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(enabled=True, is_hard=True, parameters={})
        constraint = WorkerShiftLimitConstraint(model, variables, config)
        assert constraint.config.get_param("max_shifts_per_period", 1) == 1

    def test_single_shift_type_never_binds(self) -> None:
        """With only one shift type, the limit is never the binding factor."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Alice")]
        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = WorkerShiftLimitConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        model.add(variables.get_assignment_var("W001", 0, "shift") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        assert solver.Value(variables.get_assignment_var("W001", 0, "shift")) == 1

    def test_zero_max_shifts_forces_no_assignment(self) -> None:
        """max_shifts_per_period=0 blocks any assignment for the worker."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Alice")]
        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True, is_hard=True, parameters={"max_shifts_per_period": 0}
        )
        constraint = WorkerShiftLimitConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        assert solver.Value(variables.get_assignment_var("W001", 0, "shift")) == 0


class TestWorkerShiftLimitDayAware:
    """Day-aware limits: shift types only compete on days they share."""

    @staticmethod
    def _shift(shift_id: str, days: list[int] | None) -> ShiftType:
        return ShiftType(
            id=shift_id,
            name=shift_id,
            category="cat_a",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            workers_required=1,
            applicable_days=days,
        )

    def test_disjoint_applicable_days_do_not_compete(self) -> None:
        """A weekday shift and a weekend shift can share one worker-period.

        Regression for the applicable_days infeasibility: coverage demands
        both shifts filled each period, worker_shift_limit (1) previously
        summed across ALL shift types making a single worker impossible even
        though the shifts never occur on the same day.
        """
        model = cp_model.CpModel()
        workers = [Worker(id="worker_1", name="Worker One")]
        shift_types = [
            self._shift("shift_weekday", [0, 1, 2, 3, 4]),
            self._shift("shift_weekend", [5, 6]),
        ]
        # One full week: Monday 2026-01-05 .. Sunday 2026-01-11.
        period_dates = [(date(2026, 1, 5), date(2026, 1, 11))]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = WorkerShiftLimitConstraint(
            model, variables, ConstraintConfig(enabled=True, is_hard=True)
        )
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            period_dates=period_dates,
        )

        # Demand both shifts be worked by the single worker.
        model.add(variables.get_assignment_var("worker_1", 0, "shift_weekday") == 1)
        model.add(variables.get_assignment_var("worker_1", 0, "shift_weekend") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

    def test_overlapping_applicable_days_still_compete(self) -> None:
        """Shifts sharing any day still exclude each other on that day."""
        model = cp_model.CpModel()
        workers = [Worker(id="worker_1", name="Worker One")]
        shift_types = [
            self._shift("shift_weekday", [0, 1, 2, 3, 4]),
            self._shift("shift_friday_sat", [4, 5]),  # shares Friday
        ]
        period_dates = [(date(2026, 1, 5), date(2026, 1, 11))]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = WorkerShiftLimitConstraint(
            model, variables, ConstraintConfig(enabled=True, is_hard=True)
        )
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            period_dates=period_dates,
        )

        model.add(variables.get_assignment_var("worker_1", 0, "shift_weekday") == 1)
        model.add(variables.get_assignment_var("worker_1", 0, "shift_friday_sat") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status == cp_model.INFEASIBLE

    def test_without_period_dates_all_types_compete(self) -> None:
        """No period_dates in context -> pre-day-aware behavior preserved."""
        model = cp_model.CpModel()
        workers = [Worker(id="worker_1", name="Worker One")]
        shift_types = [
            self._shift("shift_weekday", [0, 1, 2, 3, 4]),
            self._shift("shift_weekend", [5, 6]),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = WorkerShiftLimitConstraint(
            model, variables, ConstraintConfig(enabled=True, is_hard=True)
        )
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        model.add(variables.get_assignment_var("worker_1", 0, "shift_weekday") == 1)
        model.add(variables.get_assignment_var("worker_1", 0, "shift_weekend") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status == cp_model.INFEASIBLE
