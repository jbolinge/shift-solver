"""Tests for SolutionExtractor - extracts schedules from solver solutions."""

from datetime import date, time, timedelta

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints import CoverageConstraint
from shift_solver.models import Schedule, ShiftType, Worker
from shift_solver.solver import SolverVariables, VariableBuilder
from shift_solver.solver.solution_extractor import SolutionExtractor, _derive_period_type


class TestSolutionExtractor:
    """Tests for SolutionExtractor."""

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
        ]

    @pytest.fixture
    def shift_types(self) -> list[ShiftType]:
        """Create sample shift types."""
        return [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

    @pytest.fixture
    def period_dates(self) -> list[tuple[date, date]]:
        """Create period date ranges (2 weekly periods)."""
        base = date(2026, 1, 5)  # Monday
        return [
            (base + timedelta(weeks=i), base + timedelta(weeks=i, days=6))
            for i in range(2)
        ]

    @pytest.fixture
    def solved_model(
        self,
        model: cp_model.CpModel,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> tuple[cp_model.CpSolver, SolverVariables]:
        """Create and solve a model, returning solver and variables."""
        builder = VariableBuilder(model, workers, shift_types, num_periods=2)
        variables = builder.build()

        # Add coverage constraint
        coverage = CoverageConstraint(model, variables)
        coverage.apply(workers=workers, shift_types=shift_types, num_periods=2)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        return solver, variables

    def test_extract_creates_schedule(
        self,
        solved_model: tuple[cp_model.CpSolver, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """SolutionExtractor creates a Schedule object."""
        solver, variables = solved_model

        extractor = SolutionExtractor(
            solver=solver,
            variables=variables,
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-001",
        )

        schedule = extractor.extract()

        assert isinstance(schedule, Schedule)
        assert schedule.schedule_id == "TEST-001"

    def test_extract_includes_all_periods(
        self,
        solved_model: tuple[cp_model.CpSolver, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Extracted schedule includes all periods."""
        solver, variables = solved_model

        extractor = SolutionExtractor(
            solver=solver,
            variables=variables,
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-001",
        )

        schedule = extractor.extract()

        assert len(schedule.periods) == 2

    def test_extract_assigns_workers(
        self,
        solved_model: tuple[cp_model.CpSolver, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Extracted schedule has worker assignments."""
        solver, variables = solved_model

        extractor = SolutionExtractor(
            solver=solver,
            variables=variables,
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-001",
        )

        schedule = extractor.extract()

        # Check that shifts are assigned in each period
        for period in schedule.periods:
            all_shifts = period.get_shifts_by_type("day") + period.get_shifts_by_type("night")
            assigned_shifts = [s for s in all_shifts if s.is_assigned]
            # At least some shifts should be assigned
            assert len(assigned_shifts) > 0

    def test_extract_populates_shift_instances(
        self,
        solved_model: tuple[cp_model.CpSolver, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """ShiftInstances have correct properties."""
        solver, variables = solved_model

        extractor = SolutionExtractor(
            solver=solver,
            variables=variables,
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-001",
        )

        schedule = extractor.extract()

        # Check first period's day shifts
        period_0 = schedule.periods[0]
        day_shifts = period_0.get_shifts_by_type("day")
        for shift in day_shifts:
            if shift.is_assigned:
                assert shift.worker_id in ["W001", "W002"]
                assert shift.period_index == 0
                assert shift.date == period_dates[0][0]

    def test_extract_includes_statistics(
        self,
        solved_model: tuple[cp_model.CpSolver, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Extracted schedule includes worker statistics."""
        solver, variables = solved_model

        extractor = SolutionExtractor(
            solver=solver,
            variables=variables,
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-001",
        )

        schedule = extractor.extract()

        assert len(schedule.statistics) > 0
        # Stats should exist for each worker
        for worker in workers:
            assert worker.id in schedule.statistics


class TestSolutionExtractorValidation:
    """Validation tests for SolutionExtractor."""

    def test_requires_solver(self) -> None:
        """Raises ValueError when solver is None."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="A")]
        shift_types = [
            ShiftType(
                id="s",
                name="S",
                category="x",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        with pytest.raises(ValueError, match="solver"):
            SolutionExtractor(
                solver=None,  # type: ignore
                variables=variables,
                workers=workers,
                shift_types=shift_types,
                period_dates=[(date(2026, 1, 5), date(2026, 1, 11))],
                schedule_id="TEST",
            )

    def test_requires_variables(self) -> None:
        """Raises ValueError when variables is None."""
        model = cp_model.CpModel()
        solver = cp_model.CpSolver()
        workers = [Worker(id="W001", name="A")]
        shift_types = [
            ShiftType(
                id="s",
                name="S",
                category="x",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        with pytest.raises(ValueError, match="variables"):
            SolutionExtractor(
                solver=solver,
                variables=None,  # type: ignore
                workers=workers,
                shift_types=shift_types,
                period_dates=[(date(2026, 1, 5), date(2026, 1, 11))],
                schedule_id="TEST",
            )


class TestSolutionExtractorStatistics:
    """Tests for statistics calculation."""

    def test_statistics_count_shifts_per_worker(self) -> None:
        """Statistics include shift counts per worker."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="A"), Worker(id="W002", name="B")]
        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="any",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        coverage = CoverageConstraint(model, variables)
        coverage.apply(workers=workers, shift_types=shift_types, num_periods=4)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        base = date(2026, 1, 5)
        period_dates = [
            (base + timedelta(weeks=i), base + timedelta(weeks=i, days=6))
            for i in range(4)
        ]

        extractor = SolutionExtractor(
            solver=solver,
            variables=variables,
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST",
        )

        schedule = extractor.extract()

        # Total shifts assigned should be 4 (1 per period)
        total_w1 = schedule.statistics["W001"].get("total_shifts", 0)
        total_w2 = schedule.statistics["W002"].get("total_shifts", 0)
        assert total_w1 + total_w2 == 4

    def test_statistics_count_shift_types(self) -> None:
        """Statistics track counts by shift type."""
        model = cp_model.CpModel()
        workers = [Worker(id=f"W{i:03d}", name=f"W{i}") for i in range(3)]
        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=2)
        variables = builder.build()

        coverage = CoverageConstraint(model, variables)
        coverage.apply(workers=workers, shift_types=shift_types, num_periods=2)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        base = date(2026, 1, 5)
        period_dates = [
            (base + timedelta(weeks=i), base + timedelta(weeks=i, days=6))
            for i in range(2)
        ]

        extractor = SolutionExtractor(
            solver=solver,
            variables=variables,
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST",
        )

        schedule = extractor.extract()

        # Count total shifts by type
        total_day = sum(
            s.get("day", 0) for s in schedule.statistics.values()
        )
        total_night = sum(
            s.get("night", 0) for s in schedule.statistics.values()
        )

        # 2 periods, 1 day and 1 night each = 2 of each
        assert total_day == 2
        assert total_night == 2


class TestDerivePeriodType:
    """Tests for _derive_period_type function."""

    def test_derive_period_type_day(self) -> None:
        """Single day periods return 'day'."""
        period_dates = [
            (date(2026, 1, 5), date(2026, 1, 5)),
            (date(2026, 1, 6), date(2026, 1, 6)),
        ]
        assert _derive_period_type(period_dates) == "day"

    def test_derive_period_type_week(self) -> None:
        """Seven day periods return 'week'."""
        period_dates = [
            (date(2026, 1, 5), date(2026, 1, 11)),  # Mon-Sun = 7 days
            (date(2026, 1, 12), date(2026, 1, 18)),
        ]
        assert _derive_period_type(period_dates) == "week"

    def test_derive_period_type_biweek(self) -> None:
        """14 day periods return 'biweek'."""
        period_dates = [
            (date(2026, 1, 5), date(2026, 1, 18)),  # 14 days
        ]
        assert _derive_period_type(period_dates) == "biweek"

    def test_derive_period_type_month(self) -> None:
        """28-31 day periods return 'month'."""
        # 28 days
        period_dates = [(date(2026, 2, 1), date(2026, 2, 28))]
        assert _derive_period_type(period_dates) == "month"

        # 30 days
        period_dates = [(date(2026, 4, 1), date(2026, 4, 30))]
        assert _derive_period_type(period_dates) == "month"

        # 31 days
        period_dates = [(date(2026, 1, 1), date(2026, 1, 31))]
        assert _derive_period_type(period_dates) == "month"

    def test_derive_period_type_custom(self) -> None:
        """Other durations return 'custom'."""
        # 3 days
        period_dates = [(date(2026, 1, 5), date(2026, 1, 7))]
        assert _derive_period_type(period_dates) == "custom"

        # 10 days
        period_dates = [(date(2026, 1, 5), date(2026, 1, 14))]
        assert _derive_period_type(period_dates) == "custom"

    def test_derive_period_type_empty_list(self) -> None:
        """Empty period list returns default 'week'."""
        assert _derive_period_type([]) == "week"


class TestSolutionExtractorPeriodType:
    """Tests for period_type being correctly set from period_dates."""

    def test_extracted_schedule_has_correct_period_type_week(self) -> None:
        """Extracted schedule has 'week' period_type for 7-day periods."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="A")]
        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="any",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        coverage = CoverageConstraint(model, variables)
        coverage.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        solver.Solve(model)

        # 7-day period (Monday to Sunday)
        period_dates = [(date(2026, 1, 5), date(2026, 1, 11))]

        extractor = SolutionExtractor(
            solver=solver,
            variables=variables,
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST",
        )

        schedule = extractor.extract()
        assert schedule.period_type == "week"

    def test_extracted_schedule_has_correct_period_type_day(self) -> None:
        """Extracted schedule has 'day' period_type for 1-day periods."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="A")]
        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="any",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=2)
        variables = builder.build()

        coverage = CoverageConstraint(model, variables)
        coverage.apply(workers=workers, shift_types=shift_types, num_periods=2)

        solver = cp_model.CpSolver()
        solver.Solve(model)

        # Single-day periods
        period_dates = [
            (date(2026, 1, 5), date(2026, 1, 5)),
            (date(2026, 1, 6), date(2026, 1, 6)),
        ]

        extractor = SolutionExtractor(
            solver=solver,
            variables=variables,
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST",
        )

        schedule = extractor.extract()
        assert schedule.period_type == "day"
