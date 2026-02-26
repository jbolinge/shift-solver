"""Tests for ShiftSolver - main orchestrator for shift scheduling."""

from datetime import date, time, timedelta

import pytest

from shift_solver.models import Availability, Schedule, ShiftType, Worker
from shift_solver.solver.shift_solver import ShiftSolver


class TestShiftSolver:
    """Tests for ShiftSolver."""

    @pytest.fixture
    def workers(self) -> list[Worker]:
        """Create sample workers."""
        return [
            Worker(id="W001", name="Alice"),
            Worker(id="W002", name="Bob"),
            Worker(id="W003", name="Charlie"),
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
        """Create period date ranges (4 weekly periods)."""
        base = date(2026, 1, 5)  # Monday
        return [
            (base + timedelta(weeks=i), base + timedelta(weeks=i, days=6))
            for i in range(4)
        ]

    def test_solve_finds_solution(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """ShiftSolver finds a valid solution."""
        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-001",
        )

        result = solver.solve(time_limit_seconds=30)

        assert result.success
        assert result.schedule is not None

    def test_solve_returns_schedule(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Solution includes a valid Schedule."""
        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-001",
        )

        result = solver.solve(time_limit_seconds=30)

        assert isinstance(result.schedule, Schedule)
        assert result.schedule.schedule_id == "TEST-001"
        assert len(result.schedule.periods) == 4

    def test_solve_respects_coverage(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Solution satisfies coverage requirements."""
        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-001",
        )

        result = solver.solve(time_limit_seconds=30)

        assert result.success
        schedule = result.schedule
        assert schedule is not None

        # Each period should have required coverage
        for period in schedule.periods:
            day_count = len(period.get_shifts_by_type("day"))
            night_count = len(period.get_shifts_by_type("night"))
            assert day_count >= 1  # At least 1 day shift assigned
            assert night_count >= 1  # At least 1 night shift assigned

    def test_solve_respects_restrictions(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Solution respects worker restrictions."""
        workers = [
            Worker(id="W001", name="Alice", restricted_shifts=frozenset(["night"])),
            Worker(id="W002", name="Bob"),
            Worker(id="W003", name="Charlie"),
        ]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-001",
        )

        result = solver.solve(time_limit_seconds=30)

        assert result.success
        schedule = result.schedule
        assert schedule is not None

        # W001 should never be assigned to night shift
        for period in schedule.periods:
            w001_shifts = period.get_worker_shifts("W001")
            for shift in w001_shifts:
                assert shift.shift_type_id != "night"

    def test_solve_respects_availability(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Solution respects availability constraints."""
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                availability_type="unavailable",
            ),
        ]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
            schedule_id="TEST-001",
        )

        result = solver.solve(time_limit_seconds=30)

        assert result.success
        schedule = result.schedule
        assert schedule is not None

        # W001 should not be assigned in period 1
        w001_shifts = schedule.periods[1].get_worker_shifts("W001")
        assert len(w001_shifts) == 0

    def test_solve_returns_statistics(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Result includes solve statistics."""
        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-001",
        )

        result = solver.solve(time_limit_seconds=30)

        assert result.solve_time_seconds >= 0
        assert result.status_name is not None

    def test_solve_infeasible_returns_failure(self) -> None:
        """Infeasible problem returns success=False."""
        # Only 1 worker but need 2 for coverage
        workers = [Worker(id="W001", name="Solo")]
        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="any",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
                workers_required=2,  # Need 2 but only 1 available
            ),
        ]
        period_dates = [(date(2026, 1, 5), date(2026, 1, 11))]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-INFEASIBLE",
        )

        result = solver.solve(time_limit_seconds=10)

        assert not result.success
        assert result.schedule is None


class TestShiftSolverValidation:
    """Validation tests for ShiftSolver."""

    def test_requires_workers(self) -> None:
        """Raises ValueError for empty workers."""
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

        with pytest.raises(ValueError, match="workers"):
            ShiftSolver(
                workers=[],
                shift_types=shift_types,
                period_dates=[(date(2026, 1, 5), date(2026, 1, 11))],
                schedule_id="TEST",
            )

    def test_requires_shift_types(self) -> None:
        """Raises ValueError for empty shift types."""
        workers = [Worker(id="W001", name="A")]

        with pytest.raises(ValueError, match="shift_types"):
            ShiftSolver(
                workers=workers,
                shift_types=[],
                period_dates=[(date(2026, 1, 5), date(2026, 1, 11))],
                schedule_id="TEST",
            )

    def test_requires_period_dates(self) -> None:
        """Raises ValueError for empty period dates."""
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

        with pytest.raises(ValueError, match="period_dates"):
            ShiftSolver(
                workers=workers,
                shift_types=shift_types,
                period_dates=[],
                schedule_id="TEST",
            )


class TestShiftSolverPreSolveFeasibility:
    """Tests for pre-solve feasibility checking (scheduler-53)."""

    def test_infeasible_detects_all_workers_restricted(self) -> None:
        """Solver detects when all workers are restricted from required shift."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["night"])),
            Worker(id="W2", name="Bob", restricted_shifts=frozenset(["night"])),
            Worker(id="W3", name="Charlie", restricted_shifts=frozenset(["night"])),
        ]
        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]
        period_dates = [(date(2026, 1, 1), date(2026, 1, 7))]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-INFEASIBLE",
        )

        result = solver.solve(time_limit_seconds=10)

        # Should fail with clear reason
        assert not result.success
        assert result.feasibility_issues is not None
        assert len(result.feasibility_issues) > 0
        # Should identify the restriction issue
        assert any(i["type"] == "restriction" for i in result.feasibility_issues)

    def test_infeasible_message_identifies_shift_type(self) -> None:
        """Feasibility error message identifies which shift type is infeasible."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["night"])),
        ]
        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        period_dates = [(date(2026, 1, 1), date(2026, 1, 7))]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-INFEASIBLE",
        )

        result = solver.solve(time_limit_seconds=10)

        assert not result.success
        assert result.feasibility_issues is not None
        issue = next(i for i in result.feasibility_issues if i["type"] == "restriction")
        assert "Night Shift" in issue["message"]


class TestShiftSolverRequestConstraintConfig:
    """Tests for RequestConstraint config handling (scheduler-56)."""

    def test_explicit_disabled_config_respected_with_requests(self) -> None:
        """Test that explicit enabled=False is respected even with requests."""
        from shift_solver.constraints.base import ConstraintConfig
        from shift_solver.models import SchedulingRequest

        workers = [Worker(id="W1", name="Alice")]
        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        period_dates = [(date(2026, 1, 1), date(2026, 1, 7))]
        # Request exists
        requests = [
            SchedulingRequest(
                worker_id="W1",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                request_type="positive",
                shift_type_id="day",
                priority=1,
            )
        ]

        # Explicitly disable request constraint
        constraint_configs = {
            "request": ConstraintConfig(enabled=False, is_hard=False, weight=100)
        }

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-DISABLED",
            requests=requests,
            constraint_configs=constraint_configs,
        )

        result = solver.solve(time_limit_seconds=10)

        # Should solve successfully (no request constraint applied)
        assert result.success


class TestShiftSolverLargerScale:
    """Tests with larger problem sizes."""

    def test_solve_10_workers_4_shifts_8_periods(self) -> None:
        """Solves problem with 10 workers, 4 shift types, 8 periods."""
        workers = [Worker(id=f"W{i:03d}", name=f"Worker {i}") for i in range(10)]
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
                id="afternoon",
                name="Afternoon",
                category="day",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
            ShiftType(
                id="weekend",
                name="Weekend",
                category="weekend",
                start_time=time(8, 0),
                end_time=time(20, 0),
                duration_hours=12.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        base = date(2026, 1, 5)
        period_dates = [
            (base + timedelta(weeks=i), base + timedelta(weeks=i, days=6))
            for i in range(8)
        ]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="LARGE-TEST",
        )

        result = solver.solve(time_limit_seconds=60)

        assert result.success
        assert result.schedule is not None
        assert len(result.schedule.periods) == 8


class TestShiftSolverShiftFrequencyIntegration:
    """Integration tests for shift_frequency constraint (scheduler-95)."""

    def test_shift_frequency_requirements_from_parameter(self) -> None:
        """Test shift_frequency_requirements passed directly to solver."""
        from shift_solver.constraints.base import ConstraintConfig
        from shift_solver.models import ShiftFrequencyRequirement

        workers = [
            Worker(id="W1", name="Alice"),
            Worker(id="W2", name="Bob"),
            Worker(id="W3", name="Charlie"),
        ]
        shift_types = [
            ShiftType(
                id="mvsc_day",
                name="MVSC Day",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="mvsc_night",
                name="MVSC Night",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        base = date(2026, 1, 5)
        period_dates = [
            (base + timedelta(weeks=i), base + timedelta(weeks=i, days=6))
            for i in range(8)
        ]

        requirements = [
            ShiftFrequencyRequirement(
                worker_id="W1",
                shift_types=frozenset(["mvsc_day", "mvsc_night"]),
                max_periods_between=4,
            )
        ]

        constraint_configs = {
            "shift_frequency": ConstraintConfig(
                enabled=True, is_hard=False, weight=500
            )
        }

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-SF-PARAM",
            constraint_configs=constraint_configs,
            shift_frequency_requirements=requirements,
        )

        assert solver.shift_frequency_requirements == requirements
        result = solver.solve(time_limit_seconds=30)
        assert result.success

    def test_shift_frequency_requirements_from_config(self) -> None:
        """Test shift_frequency_requirements parsed from config."""
        from shift_solver.constraints.base import ConstraintConfig

        workers = [
            Worker(id="W1", name="Alice"),
            Worker(id="W2", name="Bob"),
        ]
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
        ]
        period_dates = [(date(2026, 1, 5), date(2026, 1, 11))]

        constraint_configs = {
            "shift_frequency": ConstraintConfig(
                enabled=True,
                is_hard=False,
                weight=500,
                parameters={
                    "requirements": [
                        {
                            "worker_id": "W1",
                            "shift_types": ["day"],
                            "max_periods_between": 1,
                        }
                    ]
                },
            )
        }

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-SF-CONFIG",
            constraint_configs=constraint_configs,
        )

        # Requirements should be parsed from config
        assert len(solver.shift_frequency_requirements) == 1
        assert solver.shift_frequency_requirements[0].worker_id == "W1"
        assert solver.shift_frequency_requirements[0].shift_types == frozenset(["day"])

        result = solver.solve(time_limit_seconds=30)
        assert result.success

    def test_empty_requirements_when_no_config(self) -> None:
        """Test empty requirements when no shift_frequency config."""
        workers = [Worker(id="W1", name="Alice")]
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
        ]
        period_dates = [(date(2026, 1, 5), date(2026, 1, 11))]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-NO-SF",
        )

        assert solver.shift_frequency_requirements == []


class TestShiftSolverParameters:
    """Tests for additional solver parameters (num_workers, relative_gap_limit, log_search_progress)."""

    @pytest.fixture
    def simple_solver(self) -> ShiftSolver:
        """Create a simple solver for parameter testing."""
        workers = [Worker(id="W1", name="Alice"), Worker(id="W2", name="Bob")]
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
        ]
        period_dates = [(date(2026, 1, 5), date(2026, 1, 11))]
        return ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-PARAMS",
        )

    def test_solve_accepts_num_workers_parameter(self, simple_solver: ShiftSolver) -> None:
        """num_workers parameter is accepted and solver still works."""
        result = simple_solver.solve(time_limit_seconds=10, num_workers=2)
        assert result.success
        # Verify the parameter was set on the solver
        assert simple_solver._solver is not None
        assert simple_solver._solver.parameters.num_workers == 2

    def test_solve_accepts_relative_gap_limit(self, simple_solver: ShiftSolver) -> None:
        """relative_gap_limit parameter is accepted and set."""
        result = simple_solver.solve(time_limit_seconds=10, relative_gap_limit=0.1)
        assert result.success
        assert simple_solver._solver is not None
        assert abs(simple_solver._solver.parameters.relative_gap_limit - 0.1) < 1e-6

    def test_solve_accepts_log_search_progress(self, simple_solver: ShiftSolver) -> None:
        """log_search_progress parameter is accepted and set."""
        result = simple_solver.solve(time_limit_seconds=10, log_search_progress=True)
        assert result.success
        assert simple_solver._solver is not None
        assert simple_solver._solver.parameters.log_search_progress is True

    def test_solve_default_parameters_not_set(self, simple_solver: ShiftSolver) -> None:
        """When parameters are None (default), solver defaults are preserved."""
        result = simple_solver.solve(time_limit_seconds=10)
        assert result.success
        # With None args, num_workers should be at solver default (typically 0 = auto)
        assert simple_solver._solver is not None
