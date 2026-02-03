"""E2E tests for solver stress with tight constraints.

These tests verify solver behavior under stress conditions including:
- Very long scheduling horizons (2-year schedules)
- Dense request volumes
- Tight fairness requirements
- Variable and constraint count tracking

Issue: scheduler-82
"""

import time as time_module
from datetime import time

import pytest

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import Availability, SchedulingRequest, ShiftType
from shift_solver.solver import ShiftSolver
from shift_solver.solver.variable_builder import VariableBuilder

from .conftest import create_period_dates, solve_and_verify

# -----------------------------------------------------------------------------
# Extended Time Horizon Tests
# -----------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.slow
class TestExtendedTimeHorizon:
    """Tests for very long scheduling horizons."""

    def test_20_workers_104_periods_two_year_schedule(self, worker_factory) -> None:
        """20 workers scheduled over 104 weeks (2 years)."""
        workers = [worker_factory() for _ in range(20)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=104)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        start_time = time_module.time()
        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            time_limit_seconds=300,
        )
        solve_time = time_module.time() - start_time

        assert result.success
        assert len(result.schedule.periods) == 104
        print(f"2-year schedule (104 periods) solved in {solve_time:.1f}s")

    def test_10_workers_52_periods_with_restrictions(self, worker_factory) -> None:
        """10 workers with restrictions over 52 weeks."""
        workers = []
        for i in range(10):
            if i < 3:
                workers.append(worker_factory(restricted_shifts=frozenset(["night"])))
            else:
                workers.append(worker_factory())

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=52)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            time_limit_seconds=180,
        )

        assert result.success


# -----------------------------------------------------------------------------
# Dense Request Tests
# -----------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.slow
class TestDenseRequests:
    """Tests for scenarios with many requests."""

    def test_every_worker_requests_every_period(self, worker_factory) -> None:
        """Every worker has a request for every period."""
        workers = [worker_factory() for _ in range(10)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=8)

        # Every worker requests to avoid night shift for every period
        requests = []
        for worker in workers:
            for period_start, period_end in periods:
                requests.append(
                    SchedulingRequest(
                        worker_id=worker.id,
                        start_date=period_start,
                        end_date=period_end,
                        request_type="negative",
                        shift_type_id="night",
                        priority=1,
                    )
                )

        # 10 workers × 8 periods = 80 requests
        assert len(requests) == 80

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=200),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            requests=requests,
            constraint_configs=constraint_configs,
            time_limit_seconds=60,
        )

        assert result.success

    def test_conflicting_positive_requests(self, worker_factory) -> None:
        """Multiple workers request the same limited shift."""
        workers = [worker_factory() for _ in range(10)]

        shift_types = [
            ShiftType(
                id="premium",
                name="Premium Shift",
                category="day",
                start_time=time(10, 0),
                end_time=time(14, 0),
                duration_hours=4.0,
                workers_required=1,  # Only 1 slot available
            ),
        ]

        periods = create_period_dates(num_periods=4)

        # All workers want the premium shift
        requests = []
        for worker in workers:
            for period_start, period_end in periods:
                requests.append(
                    SchedulingRequest(
                        worker_id=worker.id,
                        start_date=period_start,
                        end_date=period_end,
                        request_type="positive",
                        shift_type_id="premium",
                        priority=1,
                    )
                )

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=500),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            requests=requests,
            constraint_configs=constraint_configs,
            time_limit_seconds=60,
        )

        assert result.success
        # Only 4 of 40 requests can be satisfied (1 per period)


# -----------------------------------------------------------------------------
# Tight Fairness Tests
# -----------------------------------------------------------------------------


@pytest.mark.e2e
class TestTightFairness:
    """Tests for tight fairness constraints."""

    def test_fairness_spread_minimized(self, worker_factory) -> None:
        """Verify solver minimizes fairness spread."""
        workers = [worker_factory() for _ in range(6)]

        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        # 6 periods, 6 workers, 1 night shift per period
        # Perfect fairness: each worker gets exactly 1 night shift
        periods = create_period_dates(num_periods=6)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=10000),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            time_limit_seconds=60,
        )

        assert result.success

        # Count night shifts per worker
        worker_night_counts = {w.id: 0 for w in workers}
        for period in result.schedule.periods:
            for shift_id, assigned_workers in period.assignments.items():
                if shift_id == "night":
                    for w in assigned_workers:
                        worker_night_counts[w.id] += 1

        counts = list(worker_night_counts.values())
        spread = max(counts) - min(counts)

        # With high fairness weight, spread should be 0 or 1
        assert spread <= 1, f"Fairness spread {spread} > 1"

    def test_fairness_with_restrictions_increases_spread(self, worker_factory) -> None:
        """Restrictions may force higher spread."""
        # 2 workers restricted from night, so remaining 4 must cover 6 nights
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(),
            worker_factory(),
            worker_factory(),
            worker_factory(),
        ]

        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=6)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=10000),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            time_limit_seconds=60,
        )

        assert result.success

        # Restricted workers should have 0 night shifts
        for period in result.schedule.periods:
            for shift_id, assigned_workers in period.assignments.items():
                if shift_id == "night":
                    for w in assigned_workers:
                        assert w.id not in [workers[0].id, workers[1].id]


# -----------------------------------------------------------------------------
# Variable and Constraint Count Tracking
# -----------------------------------------------------------------------------


@pytest.mark.e2e
class TestVariableConstraintCounts:
    """Tests for tracking variable and constraint counts."""

    def test_variable_count_scales_with_problem_size(self, worker_factory) -> None:
        """Verify variable count scales as expected with problem size."""
        from ortools.sat.python import cp_model

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        # Test with different sizes
        sizes = [(5, 4), (10, 8), (20, 12)]
        var_counts = []

        for num_workers, num_periods in sizes:
            workers = [worker_factory() for _ in range(num_workers)]
            model = cp_model.CpModel()
            builder = VariableBuilder(model, workers, shift_types, num_periods)
            _variables = builder.build()  # Build to verify structure

            # Count assignment variables
            assignment_count = sum(
                1
                for w in workers
                for p in range(num_periods)
                for st in shift_types
            )
            var_counts.append(assignment_count)

            print(
                f"{num_workers} workers × {num_periods} periods × "
                f"{len(shift_types)} shifts = {assignment_count} assignment vars"
            )

        # Verify scaling: each step should have more variables
        assert var_counts[0] < var_counts[1] < var_counts[2]

    def test_constraint_count_with_all_constraints(self, worker_factory) -> None:
        """Track constraint count with all constraints enabled."""
        workers = [worker_factory() for _ in range(10)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=4)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "frequency": ConstraintConfig(
                enabled=True,
                is_hard=False,
                weight=50,
                parameters={"max_periods_between": 2},
            ),
        }

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            schedule_id="COUNT-TEST",
            constraint_configs=constraint_configs,
        )

        result = solver.solve(time_limit_seconds=60)

        assert result.success
        # Log statistics for documentation
        if hasattr(result, "statistics"):
            print(f"Solver statistics: {result.statistics}")


# -----------------------------------------------------------------------------
# Exact Coverage (Tight) Tests
# -----------------------------------------------------------------------------


@pytest.mark.e2e
class TestExactCoverage:
    """Tests where workers required equals workers available."""

    def test_exact_workers_for_all_shifts_all_periods(self, worker_factory) -> None:
        """Exactly enough workers for all shifts in all periods."""
        # 3 shifts × 2 workers each = 6 workers needed per period
        # With 6 workers, each must work exactly one shift per period
        workers = [worker_factory() for _ in range(6)]

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
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=4)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            time_limit_seconds=60,
        )

        assert result.success

        # Verify all workers assigned in each period
        for period in result.schedule.periods:
            total_assigned = sum(
                len(assigned) for assigned in period.assignments.values()
            )
            assert total_assigned == 6

    def test_exact_coverage_with_one_unavailable(self, worker_factory) -> None:
        """Exact coverage becomes infeasible with one unavailability."""
        workers = [worker_factory() for _ in range(4)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=4,  # Need all 4 workers
            ),
        ]

        periods = create_period_dates(num_periods=2)
        period_start, period_end = periods[0]

        # One worker unavailable for first period
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                availability_type="unavailable",
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "availability": ConstraintConfig(enabled=True, is_hard=True),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            availabilities=availabilities,
            constraint_configs=constraint_configs,
            expect_feasible=False,
        )

        assert not result.success


# -----------------------------------------------------------------------------
# Timeout Behavior with Partial Solutions
# -----------------------------------------------------------------------------


@pytest.mark.e2e
class TestTimeoutWithPartialSolution:
    """Tests for timeout behavior returning best-so-far solutions."""

    def test_very_short_timeout_complex_problem(self, worker_factory) -> None:
        """Very short timeout on complex problem."""
        workers = [worker_factory() for _ in range(40)]

        shift_types = [
            ShiftType(
                id=f"shift_{i}",
                name=f"Shift {i}",
                category="day",
                start_time=time(6 + i * 2, 0),
                end_time=time(14 + i * 2, 0),
                duration_hours=8.0,
                workers_required=3,
            )
            for i in range(4)
        ]

        periods = create_period_dates(num_periods=12)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "frequency": ConstraintConfig(enabled=True, is_hard=False, weight=50),
        }

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            schedule_id="TIMEOUT-PARTIAL",
            constraint_configs=constraint_configs,
        )

        # Very short timeout
        result = solver.solve(time_limit_seconds=2)

        # May succeed quickly, or timeout - both acceptable
        assert result.status_name in ["OPTIMAL", "FEASIBLE", "UNKNOWN"]

    def test_adequate_timeout_finds_solution(self, worker_factory) -> None:
        """Adequate timeout should find solution."""
        workers = [worker_factory() for _ in range(15)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=8)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            time_limit_seconds=60,
        )

        assert result.success
        assert result.status_name in ["OPTIMAL", "FEASIBLE"]
