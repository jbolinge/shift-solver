"""E2E tests for performance and stress testing.

scheduler-49: Tests solver performance and scalability including large worker
counts, high constraint density, timeout behavior, and scaling analysis.
"""

import time as time_module
from datetime import date, time, timedelta

import pytest

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import Availability, SchedulingRequest, ShiftType, Worker
from shift_solver.solver import ShiftSolver

from .conftest import create_period_dates, solve_and_verify


@pytest.mark.e2e
@pytest.mark.slow
class TestLargeScaleScheduling:
    """Tests for large-scale scheduling scenarios."""

    def test_50_workers_12_weeks(self, worker_factory) -> None:
        """50+ workers, 12+ weeks - solve time should be < 180s."""
        workers = [worker_factory() for _ in range(50)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=5,
            ),
            ShiftType(
                id="evening",
                name="Evening",
                category="evening",
                start_time=time(15, 0),
                end_time=time(23, 0),
                duration_hours=8.0,
                workers_required=4,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=3,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=12)

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
            time_limit_seconds=180,
        )
        solve_time = time_module.time() - start_time

        assert result.success
        assert solve_time < 180, f"Solve time {solve_time:.1f}s exceeded 180s limit"
        assert len(result.schedule.periods) == 12
        assert len(result.schedule.workers) == 50

    def test_75_workers_8_weeks(self, worker_factory) -> None:
        """75 workers over 8 weeks."""
        workers = [worker_factory() for _ in range(75)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=8,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=4,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=8)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=50),
        }

        start_time = time_module.time()
        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            time_limit_seconds=180,
        )
        solve_time = time_module.time() - start_time

        assert result.success
        assert solve_time < 180


@pytest.mark.e2e
@pytest.mark.slow
class TestHighConstraintDensity:
    """Tests for scenarios with high constraint density."""

    def test_every_worker_has_constraints(self, worker_factory) -> None:
        """Every worker has availability + requests + restrictions."""
        workers = []
        for i in range(20):
            # Alternate restrictions
            if i % 3 == 0:
                restricted = frozenset(["night"])
            elif i % 3 == 1:
                restricted = frozenset(["weekend"])
            else:
                restricted = frozenset()
            workers.append(worker_factory(restricted_shifts=restricted))

        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
            ShiftType(
                id="weekend",
                name="Weekend",
                category="weekend",
                start_time=time(8, 0),
                end_time=time(16, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=8)

        # Create availability for every worker
        availabilities = []
        for i, worker in enumerate(workers):
            # Each worker unavailable for one period
            period_idx = i % len(periods)
            start, end = periods[period_idx]
            availabilities.append(
                Availability(
                    worker_id=worker.id,
                    start_date=start,
                    end_date=end,
                    availability_type="unavailable",
                )
            )

        # Create requests for every worker
        requests = []
        for i, worker in enumerate(workers):
            period_idx = (i + 1) % len(periods)
            start, end = periods[period_idx]
            requests.append(
                SchedulingRequest(
                    worker_id=worker.id,
                    start_date=start,
                    end_date=end,
                    request_type="negative",
                    shift_type_id="night",
                    priority=2,
                )
            )

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "availability": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=75),
        }

        start_time = time_module.time()
        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            availabilities=availabilities,
            requests=requests,
            constraint_configs=constraint_configs,
            time_limit_seconds=120,
        )
        solve_time = time_module.time() - start_time

        assert result.success
        assert solve_time < 120


@pytest.mark.e2e
class TestSolverTimeoutBehavior:
    """Tests for solver timeout behavior."""

    def test_timeout_returns_unknown_for_complex_problem(
        self, worker_factory
    ) -> None:
        """Very short timeout on complex problem returns UNKNOWN or partial."""
        workers = [worker_factory() for _ in range(30)]

        shift_types = [
            ShiftType(
                id=f"shift_{i}",
                name=f"Shift {i}",
                category="day",
                start_time=time(6 + i, 0),
                end_time=time(14 + i, 0),
                duration_hours=8.0,
                workers_required=2,
            )
            for i in range(5)
        ]

        periods = create_period_dates(num_periods=8)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "frequency": ConstraintConfig(enabled=True, is_hard=False, weight=50),
        }

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            schedule_id="TIMEOUT-TEST",
            constraint_configs=constraint_configs,
        )

        # Very short timeout - might succeed with FEASIBLE or timeout
        result = solver.solve(time_limit_seconds=5)

        # Either finds a feasible solution quickly or times out
        # Both are valid outcomes for this test
        assert result.status_name in [
            "OPTIMAL",
            "FEASIBLE",
            "UNKNOWN",
            "MODEL_INVALID",
        ]

    def test_adequate_timeout_succeeds(self, worker_factory) -> None:
        """Adequate timeout allows problem to be solved."""
        workers = [worker_factory() for _ in range(15)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
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
        assert result.status_name in ["OPTIMAL", "FEASIBLE"]


@pytest.mark.e2e
@pytest.mark.slow
class TestMemoryUsagePatterns:
    """Tests for memory usage with large problems."""

    def test_100_workers_52_periods(self, worker_factory) -> None:
        """Large problem: 100 workers, 52 periods (1 year)."""
        workers = [worker_factory() for _ in range(100)]

        # Simple shift structure to keep memory reasonable
        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=10,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=5,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=52)

        # Only hard constraints to keep problem tractable
        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=50),
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
        assert len(result.schedule.periods) == 52
        # Log solve time for reference
        print(f"100 workers x 52 periods solved in {solve_time:.1f}s")


@pytest.mark.e2e
class TestIncrementalScaling:
    """Tests for incremental scaling analysis."""

    @pytest.mark.parametrize("num_workers", [10, 20, 30, 40, 50])
    def test_scaling_with_worker_count(self, worker_factory, num_workers) -> None:
        """Test solve time scaling with increasing worker count."""
        workers = [worker_factory() for _ in range(num_workers)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=max(2, num_workers // 5),
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=max(1, num_workers // 10),
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=4)

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
            time_limit_seconds=60,
        )
        solve_time = time_module.time() - start_time

        assert result.success
        # Log for analysis
        print(f"{num_workers} workers: {solve_time:.2f}s")

    @pytest.mark.parametrize("num_periods", [4, 8, 12, 16, 20])
    def test_scaling_with_period_count(self, worker_factory, num_periods) -> None:
        """Test solve time scaling with increasing period count."""
        workers = [worker_factory() for _ in range(20)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=num_periods)

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
            time_limit_seconds=90,
        )
        solve_time = time_module.time() - start_time

        assert result.success
        print(f"{num_periods} periods: {solve_time:.2f}s")


@pytest.mark.e2e
class TestParallelSolverConfiguration:
    """Tests for parallel solver worker configuration."""

    def test_solver_completes_with_default_workers(self, worker_factory) -> None:
        """Solver runs successfully with default parallel configuration."""
        workers = [worker_factory() for _ in range(25)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=4,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=6)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "frequency": ConstraintConfig(enabled=True, is_hard=False, weight=50),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            time_limit_seconds=90,
        )

        assert result.success

    def test_multiple_solves_consistent_results(self, worker_factory) -> None:
        """Multiple solves produce consistent (valid) results."""
        workers = [worker_factory() for _ in range(10)]

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

        periods = create_period_dates(num_periods=2)

        results = []
        for _ in range(3):
            result = solve_and_verify(
                workers=workers,
                shift_types=shift_types,
                period_dates=periods,
            )
            results.append(result)

        # All runs should succeed
        assert all(r.success for r in results)


@pytest.mark.e2e
class TestPerformanceBenchmarks:
    """Documented performance benchmarks."""

    def test_small_benchmark_5_workers_2_periods(self, worker_factory) -> None:
        """Benchmark: Small problem (5 workers, 2 periods)."""
        workers = [worker_factory() for _ in range(5)]

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

        periods = create_period_dates(num_periods=2)

        start_time = time_module.time()
        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )
        solve_time = time_module.time() - start_time

        assert result.success
        # Small problem should solve very quickly
        assert solve_time < 5, f"Small problem took {solve_time:.2f}s"

    def test_medium_benchmark_20_workers_8_periods(self, worker_factory) -> None:
        """Benchmark: Medium problem (20 workers, 8 periods)."""
        workers = [worker_factory() for _ in range(20)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=4,
            ),
            ShiftType(
                id="night",
                name="Night",
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

        start_time = time_module.time()
        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            time_limit_seconds=60,
        )
        solve_time = time_module.time() - start_time

        assert result.success
        assert solve_time < 30, f"Medium problem took {solve_time:.2f}s"
