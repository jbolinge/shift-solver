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

    def test_hard_request_conflicting_with_restriction_is_diagnosed(self) -> None:
        """A hard positive request for a restricted shift is now diagnosed
        with a specific 'request' issue instead of a bare infeasible
        (scheduler contract item B.2: FeasibilityChecker must be given
        requests)."""
        from shift_solver.models import SchedulingRequest

        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["night"])),
            Worker(id="W2", name="Bob"),
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
        requests = [
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="positive",
                shift_type_id="night",
                priority=1,
                is_hard=True,
            )
        ]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-REQ-CONFLICT",
            requests=requests,
        )

        result = solver.solve(time_limit_seconds=10)

        assert not result.success
        assert result.feasibility_issues is not None
        assert any(i["type"] == "request" for i in result.feasibility_issues)


class TestSolverResultWarnings:
    """
    Tests that SolverResult surfaces FeasibilityResult warnings on both
    success and failure paths (scheduler contract item C).
    """

    def test_warnings_surfaced_on_pre_solve_failure(self) -> None:
        """Warnings accompany an INFEASIBLE_PRE_SOLVE result."""
        from shift_solver.models import ShiftFrequencyRequirement

        # Infeasible: only 1 worker but 2 required.
        workers = [Worker(id="W1", name="Alice")]
        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]
        period_dates = [(date(2026, 1, 1), date(2026, 1, 7))]
        # Also references an unknown worker - should surface as a warning
        # alongside the hard coverage issue.
        requirements = [
            ShiftFrequencyRequirement(
                worker_id="UNKNOWN_WORKER",
                shift_types=frozenset(["day"]),
                max_periods_between=1,
            )
        ]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-WARNINGS-FAIL",
            shift_frequency_requirements=requirements,
        )

        result = solver.solve(time_limit_seconds=10)

        assert not result.success
        assert any("UNKNOWN_WORKER" in w for w in result.warnings)

    def test_warnings_surfaced_on_success(self) -> None:
        """Warnings accompany a successful solve too."""
        from shift_solver.models import Availability

        workers = [Worker(id="W1", name="Alice"), Worker(id="W2", name="Bob")]
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
        # References an unknown worker - warning only, still feasible/solvable.
        availabilities = [
            Availability(
                worker_id="UNKNOWN_WORKER",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                availability_type="unavailable",
            ),
        ]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-WARNINGS-SUCCESS",
            availabilities=availabilities,
        )

        result = solver.solve(time_limit_seconds=10)

        assert result.success
        assert any("UNKNOWN_WORKER" in w for w in result.warnings)

    def test_no_warnings_defaults_to_empty_list(self) -> None:
        """A clean solve with nothing to warn about has an empty warnings list."""
        solver = ShiftSolver(
            workers=[Worker(id="W1", name="Alice")],
            shift_types=[
                ShiftType(
                    id="day",
                    name="Day Shift",
                    category="day",
                    start_time=time(7, 0),
                    end_time=time(15, 0),
                    duration_hours=8.0,
                    workers_required=1,
                ),
            ],
            period_dates=[(date(2026, 1, 1), date(2026, 1, 7))],
            schedule_id="TEST-NO-WARNINGS",
        )

        result = solver.solve(time_limit_seconds=10)

        assert result.success
        assert result.warnings == []


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
            "shift_frequency": ConstraintConfig(enabled=True, is_hard=False, weight=500)
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


class TestShiftSolverSingleDayPeriod:
    """Regression test: a schedule with exactly one single-day period should solve."""

    def test_single_one_day_period_solves(self) -> None:
        """A 1-period, 1-day schedule should solve and extract successfully."""
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
        period_dates = [(date(2026, 1, 5), date(2026, 1, 5))]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-1DAY",
        )

        result = solver.solve(time_limit_seconds=10)

        assert result.success
        assert result.schedule is not None
        assert len(result.schedule.periods) == 1
        assert result.schedule.period_type == "day"


class TestSoftConstraintHardModeEnforcement:
    """
    Regression tests for scheduler contract item A: a soft-registered
    constraint configured with is_hard=True must actually be enforced as
    hard, not silently dropped (the old ObjectiveBuilder skipped is_hard
    constraints from the objective entirely, with nothing forcing their
    violation variables to 0 - a full no-op).
    """

    def test_fairness_is_hard_forces_zero_spread(self) -> None:
        """fairness is_hard=True must force spread==0, overriding a strong
        conflicting preference expressed via soft requests."""
        from shift_solver.constraints.base import ConstraintConfig
        from shift_solver.models import SchedulingRequest

        workers = [Worker(id="W1", name="Alice"), Worker(id="W2", name="Bob")]
        shift_types = [
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
        base = date(2026, 1, 5)
        period_dates = [
            (base + timedelta(weeks=i), base + timedelta(weeks=i, days=6))
            for i in range(2)
        ]

        # A very heavily-weighted preference for W1 to work BOTH nights -
        # without hard fairness enforcement this would win and produce an
        # uneven (2 vs 0) distribution.
        requests = [
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="positive",
                shift_type_id="night",
                priority=1,
            ),
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                request_type="positive",
                shift_type_id="night",
                priority=1,
            ),
        ]

        constraint_configs = {
            "fairness": ConstraintConfig(enabled=True, is_hard=True, weight=1),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=1_000_000),
        }

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-HARD-FAIRNESS",
            requests=requests,
            constraint_configs=constraint_configs,
        )

        result = solver.solve(time_limit_seconds=30)

        assert result.success
        assert result.schedule is not None

        # Hard fairness forces an even (1-1) split despite the strong
        # per-worker request preference.
        w1_nights = result.schedule.statistics["W1"].get("night", 0)
        w2_nights = result.schedule.statistics["W2"].get("night", 0)
        assert w1_nights == 1
        assert w2_nights == 1


class TestSoftRecordViolationNotDroppedByHardConstraintConfig:
    """
    Regression test for objective_builder bug B2: a soft-registered
    constraint whose *constraint-level* config is is_hard=True, but which
    implements its own per-record hard/soft semantics
    (handles_hard_mode=True, e.g. RequestConstraint), must still have its
    per-record soft violation variables priced in the objective.

    The old ObjectiveBuilder guard ``if constraint.is_hard: continue``
    dropped ALL of a handles_hard_mode constraint's violation vars from the
    objective whenever the constraint-level config was is_hard=True - even
    for individual records explicitly marked is_hard=False. Those records
    are also not force-enforced hard (ShiftSolver._enforce_hard_mode skips
    handles_hard_mode constraints on purpose), so they floated free at zero
    cost: neither hard-enforced nor priced.
    """

    def test_soft_record_violation_is_priced_under_hard_constraint_config(
        self,
    ) -> None:
        """A request record explicitly marked is_hard=False, under a
        request constraint configured is_hard=True at the constraint
        level, must still be able to outweigh a competing (much
        lower-weighted) soft fairness constraint - proving its violation
        actually carries its weight in the objective instead of floating
        free at zero cost."""
        from shift_solver.constraints.base import ConstraintConfig
        from shift_solver.models import SchedulingRequest

        workers = [
            Worker(id="W1", name="Worker One"),
            Worker(id="W2", name="Worker Two"),
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
                is_undesirable=True,
            ),
        ]
        base = date(2026, 1, 5)
        period_dates = [
            (base + timedelta(weeks=i), base + timedelta(weeks=i, days=6))
            for i in range(2)
        ]

        # W1 explicitly requests (record-level is_hard=False) both nights.
        # Satisfying both means an uneven 2-0 split, costing the soft
        # fairness constraint some spread. If these violations are priced
        # at their real weight (1000 each), satisfying them beats the
        # fairness cost; if they float free at zero cost (the bug),
        # fairness (weight 1) wins instead and the solver produces an
        # even 1-1 split.
        requests = [
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="positive",
                shift_type_id="night",
                priority=1,
                is_hard=False,
            ),
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                request_type="positive",
                shift_type_id="night",
                priority=1,
                is_hard=False,
            ),
        ]

        constraint_configs = {
            # Constraint-level is_hard=True: RequestConstraint implements
            # its own per-record hard/soft semantics (handles_hard_mode),
            # so this must NOT force every request to hard - the
            # explicit per-record is_hard=False above must still produce
            # violation vars priced heavily in the objective.
            "request": ConstraintConfig(enabled=True, is_hard=True, weight=1000),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=1),
        }

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="TEST-SOFT-RECORD-PRICING",
            requests=requests,
            constraint_configs=constraint_configs,
        )

        result = solver.solve(time_limit_seconds=30)

        assert result.success
        assert result.schedule is not None

        w1_nights = result.schedule.statistics["W1"].get("night", 0)
        w2_nights = result.schedule.statistics["W2"].get("night", 0)
        assert w1_nights == 2
        assert w2_nights == 0


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

    def test_solve_accepts_num_workers_parameter(
        self, simple_solver: ShiftSolver
    ) -> None:
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

    def test_solve_accepts_log_search_progress(
        self, simple_solver: ShiftSolver
    ) -> None:
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

    def test_solve_with_solution_callback(self, simple_solver: ShiftSolver) -> None:
        """solve() accepts and uses a solution_callback."""
        from shift_solver.solver.progress_callback import SolverProgressCallback

        callback = SolverProgressCallback()
        result = simple_solver.solve(time_limit_seconds=10, solution_callback=callback)
        assert result.success
        assert callback.solutions_found >= 1
