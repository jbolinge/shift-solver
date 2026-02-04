"""Tests for coverage constraint."""

from datetime import date, time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.coverage import CoverageConstraint
from shift_solver.models import ShiftType, Worker
from shift_solver.solver import VariableBuilder


class TestCoverageConstraint:
    """Tests for CoverageConstraint."""

    @pytest.fixture
    def model(self) -> cp_model.CpModel:
        """Create a fresh CP model."""
        return cp_model.CpModel()

    @pytest.fixture
    def workers(self) -> list[Worker]:
        """Create sample workers."""
        return [
            Worker(id="W001", name="Alice"),
            Worker(id="W002", name="Bob"),
            Worker(id="W003", name="Charlie"),
            Worker(id="W004", name="Diana"),
        ]

    @pytest.fixture
    def shift_types(self) -> list[ShiftType]:
        """Create sample shift types with different worker requirements."""
        return [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=2,  # Needs 2 workers
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=1,  # Needs 1 worker
            ),
        ]

    @pytest.fixture
    def variables(
        self, model: cp_model.CpModel, workers: list[Worker], shift_types: list[ShiftType]
    ):
        """Build solver variables."""
        builder = VariableBuilder(model, workers, shift_types, num_periods=2)
        return builder.build()

    def test_coverage_constraint_applies(
        self,
        model: cp_model.CpModel,
        variables,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Coverage constraint can be applied to model."""
        constraint = CoverageConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=2)

        assert constraint.constraint_count > 0

    def test_coverage_enforces_workers_required(
        self,
        model: cp_model.CpModel,
        variables,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Coverage constraint enforces workers_required for each shift type."""
        constraint = CoverageConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=2)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        # Should find a solution
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Check each period
        for period in range(2):
            # Day shift should have exactly 2 workers
            day_count = sum(
                solver.Value(variables.get_assignment_var(w.id, period, "day"))
                for w in workers
            )
            assert day_count == 2, f"Day shift in period {period} should have 2 workers"

            # Night shift should have exactly 1 worker
            night_count = sum(
                solver.Value(variables.get_assignment_var(w.id, period, "night"))
                for w in workers
            )
            assert night_count == 1, f"Night shift in period {period} should have 1 worker"

    def test_coverage_infeasible_when_not_enough_workers(
        self, model: cp_model.CpModel
    ) -> None:
        """Coverage becomes infeasible when not enough workers."""
        # Only 1 worker but day shift needs 2
        workers = [Worker(id="W001", name="Solo")]
        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,  # Needs 2 but only 1 available
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = CoverageConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.INFEASIBLE

    def test_coverage_disabled_constraint(
        self,
        model: cp_model.CpModel,
        variables,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Disabled coverage constraint doesn't add constraints."""
        config = ConstraintConfig(enabled=False)
        constraint = CoverageConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=2)

        assert constraint.constraint_count == 0

    def test_coverage_with_single_worker_shift(self, model: cp_model.CpModel) -> None:
        """Works with shifts requiring exactly 1 worker."""
        workers = [Worker(id="W001", name="A"), Worker(id="W002", name="B")]
        shift_types = [
            ShiftType(
                id="solo",
                name="Solo",
                category="any",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=3)
        variables = builder.build()

        constraint = CoverageConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Each period should have exactly 1 worker on the shift
        for period in range(3):
            count = sum(
                solver.Value(variables.get_assignment_var(w.id, period, "solo"))
                for w in workers
            )
            assert count == 1


class TestCoverageConstraintEdgeCases:
    """Edge case tests for CoverageConstraint."""

    def test_many_workers_for_few_slots(self) -> None:
        """Works when many workers compete for few slots."""
        model = cp_model.CpModel()
        workers = [Worker(id=f"W{i:03d}", name=f"Worker{i}") for i in range(10)]
        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = CoverageConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Exactly 2 workers should be assigned
        count = sum(
            solver.Value(variables.get_assignment_var(w.id, 0, "shift"))
            for w in workers
        )
        assert count == 2

    def test_multiple_shift_types_same_period(self) -> None:
        """Coverage works with multiple shift types in same period."""
        model = cp_model.CpModel()
        workers = [Worker(id=f"W{i:03d}", name=f"Worker{i}") for i in range(5)]
        shift_types = [
            ShiftType(
                id="morning",
                name="Morning",
                category="day",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="evening",
                name="Evening",
                category="day",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = CoverageConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Verify each shift type has correct coverage
        morning_count = sum(
            solver.Value(variables.get_assignment_var(w.id, 0, "morning"))
            for w in workers
        )
        assert morning_count == 2

        evening_count = sum(
            solver.Value(variables.get_assignment_var(w.id, 0, "evening"))
            for w in workers
        )
        assert evening_count == 1

        night_count = sum(
            solver.Value(variables.get_assignment_var(w.id, 0, "night"))
            for w in workers
        )
        assert night_count == 1


class TestCoverageApplicableDays:
    """Tests for coverage constraint with applicable_days support."""

    def test_weekday_only_shift_in_weekly_period(self) -> None:
        """Weekday-only shift requires workers only on applicable days."""
        model = cp_model.CpModel()
        workers = [Worker(id=f"W{i:03d}", name=f"Worker{i}") for i in range(3)]
        # Mon-Fri shift (0-4 = weekdays)
        shift_types = [
            ShiftType(
                id="weekday",
                name="Weekday Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
                applicable_days=frozenset([0, 1, 2, 3, 4]),
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        # Period: Mon Jan 5, 2026 to Sun Jan 11, 2026 (full week starting Monday)
        period_dates = [(date(2026, 1, 5), date(2026, 1, 11))]

        constraint = CoverageConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            period_dates=period_dates,
        )

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Should have 2 workers assigned (weekday shift has applicable days)
        count = sum(
            solver.Value(variables.get_assignment_var(w.id, 0, "weekday"))
            for w in workers
        )
        assert count == 2

    def test_weekend_only_shift_in_weekly_period(self) -> None:
        """Weekend-only shift requires workers only on applicable days."""
        model = cp_model.CpModel()
        workers = [Worker(id=f"W{i:03d}", name=f"Worker{i}") for i in range(2)]
        # Sat-Sun shift (5-6 = weekend)
        shift_types = [
            ShiftType(
                id="weekend",
                name="Weekend Shift",
                category="weekend",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
                applicable_days=frozenset([5, 6]),
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        # Period: Mon Jan 5, 2026 to Sun Jan 11, 2026 (full week)
        period_dates = [(date(2026, 1, 5), date(2026, 1, 11))]

        constraint = CoverageConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            period_dates=period_dates,
        )

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Should have 1 worker assigned (weekend shift)
        count = sum(
            solver.Value(variables.get_assignment_var(w.id, 0, "weekend"))
            for w in workers
        )
        assert count == 1

    def test_weekend_shift_in_weekday_only_period_zero_assignments(self) -> None:
        """Weekend shift in Mon-Fri period requires zero assignments."""
        model = cp_model.CpModel()
        workers = [Worker(id=f"W{i:03d}", name=f"Worker{i}") for i in range(2)]
        # Weekend-only shift
        shift_types = [
            ShiftType(
                id="weekend",
                name="Weekend Shift",
                category="weekend",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
                applicable_days=frozenset([5, 6]),  # Sat-Sun only
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        # Period: Mon Jan 5, 2026 to Fri Jan 9, 2026 (weekdays only)
        period_dates = [(date(2026, 1, 5), date(2026, 1, 9))]

        constraint = CoverageConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            period_dates=period_dates,
        )

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Should have 0 workers assigned (no weekend days in period)
        count = sum(
            solver.Value(variables.get_assignment_var(w.id, 0, "weekend"))
            for w in workers
        )
        assert count == 0

    def test_same_worker_weekday_and_weekend_shifts(self) -> None:
        """Same worker can have both weekday and weekend shifts (non-overlapping days)."""
        model = cp_model.CpModel()
        # Only 1 worker - must be assigned to both shifts
        workers = [Worker(id="W001", name="Solo")]
        shift_types = [
            ShiftType(
                id="weekday",
                name="Weekday Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
                applicable_days=frozenset([0, 1, 2, 3, 4]),  # Mon-Fri
            ),
            ShiftType(
                id="weekend",
                name="Weekend Shift",
                category="weekend",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
                applicable_days=frozenset([5, 6]),  # Sat-Sun
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        # Full week period
        period_dates = [(date(2026, 1, 5), date(2026, 1, 11))]

        constraint = CoverageConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            period_dates=period_dates,
        )

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Solo worker should be assigned to both shifts
        weekday_assigned = solver.Value(
            variables.get_assignment_var("W001", 0, "weekday")
        )
        weekend_assigned = solver.Value(
            variables.get_assignment_var("W001", 0, "weekend")
        )
        assert weekday_assigned == 1
        assert weekend_assigned == 1

    def test_backward_compatibility_none_applicable_days(self) -> None:
        """applicable_days=None works like before (all days applicable)."""
        model = cp_model.CpModel()
        workers = [Worker(id=f"W{i:03d}", name=f"Worker{i}") for i in range(3)]
        shift_types = [
            ShiftType(
                id="any",
                name="Any Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
                applicable_days=None,  # All days
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        # Period: Mon Jan 5, 2026 to Fri Jan 9, 2026
        period_dates = [(date(2026, 1, 5), date(2026, 1, 9))]

        constraint = CoverageConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            period_dates=period_dates,
        )

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Should still require 2 workers (None means all days)
        count = sum(
            solver.Value(variables.get_assignment_var(w.id, 0, "any"))
            for w in workers
        )
        assert count == 2

    def test_backward_compatibility_no_period_dates(self) -> None:
        """Coverage works without period_dates (original behavior)."""
        model = cp_model.CpModel()
        workers = [Worker(id=f"W{i:03d}", name=f"Worker{i}") for i in range(3)]
        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
                applicable_days=frozenset([0, 1, 2, 3, 4]),  # Weekdays
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = CoverageConstraint(model, variables)
        # No period_dates - should use original behavior
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            # period_dates not provided
        )

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Should still require 2 workers (without period_dates, applicable_days ignored)
        count = sum(
            solver.Value(variables.get_assignment_var(w.id, 0, "shift"))
            for w in workers
        )
        assert count == 2

    def test_partial_week_period_counts_applicable_days(self) -> None:
        """Wed-Fri period with weekday shift counts only 3 applicable days."""
        model = cp_model.CpModel()
        workers = [Worker(id=f"W{i:03d}", name=f"Worker{i}") for i in range(3)]
        # Weekday shift
        shift_types = [
            ShiftType(
                id="weekday",
                name="Weekday Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
                applicable_days=frozenset([0, 1, 2, 3, 4]),  # Mon-Fri
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        # Period: Wed Jan 7, 2026 to Fri Jan 9, 2026 (3 weekdays)
        period_dates = [(date(2026, 1, 7), date(2026, 1, 9))]

        constraint = CoverageConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            period_dates=period_dates,
        )

        # Test passes if it solves - we're not checking exact day count,
        # but verifying that applicable_days doesn't break the solver
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Coverage should still be enforced
        count = sum(
            solver.Value(variables.get_assignment_var(w.id, 0, "weekday"))
            for w in workers
        )
        assert count == 2

    def test_count_applicable_days_helper(self) -> None:
        """_count_applicable_days correctly counts days in period."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Test")]
        shift_types = [
            ShiftType(
                id="test",
                name="Test",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
                applicable_days=frozenset([0, 1, 2, 3, 4]),  # Mon-Fri
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = CoverageConstraint(model, variables)

        # Full week starting Monday: Jan 5, 2026 is Monday
        weekday_count = constraint._count_applicable_days(
            shift_types[0], date(2026, 1, 5), date(2026, 1, 11)
        )
        assert weekday_count == 5  # Mon-Fri = 5 days

        # Weekend shift
        weekend_shift = ShiftType(
            id="weekend",
            name="Weekend",
            category="weekend",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            workers_required=1,
            applicable_days=frozenset([5, 6]),  # Sat-Sun
        )
        weekend_count = constraint._count_applicable_days(
            weekend_shift, date(2026, 1, 5), date(2026, 1, 11)
        )
        assert weekend_count == 2  # Sat-Sun = 2 days

        # Weekday-only period (Mon-Fri)
        weekend_in_weekday_period = constraint._count_applicable_days(
            weekend_shift, date(2026, 1, 5), date(2026, 1, 9)
        )
        assert weekend_in_weekday_period == 0  # No weekend days

    def test_multiple_periods_with_applicable_days(self) -> None:
        """Coverage works across multiple periods with applicable_days."""
        model = cp_model.CpModel()
        workers = [Worker(id=f"W{i:03d}", name=f"Worker{i}") for i in range(3)]
        shift_types = [
            ShiftType(
                id="weekday",
                name="Weekday",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
                applicable_days=frozenset([0, 1, 2, 3, 4]),
            ),
            ShiftType(
                id="weekend",
                name="Weekend",
                category="weekend",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
                applicable_days=frozenset([5, 6]),
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=2)
        variables = builder.build()

        # Two weeks
        period_dates = [
            (date(2026, 1, 5), date(2026, 1, 11)),  # Week 1
            (date(2026, 1, 12), date(2026, 1, 18)),  # Week 2
        ]

        constraint = CoverageConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=2,
            period_dates=period_dates,
        )

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Each period should have coverage for both shift types
        for period in range(2):
            weekday_count = sum(
                solver.Value(variables.get_assignment_var(w.id, period, "weekday"))
                for w in workers
            )
            assert weekday_count == 1

            weekend_count = sum(
                solver.Value(variables.get_assignment_var(w.id, period, "weekend"))
                for w in workers
            )
            assert weekend_count == 1
