"""E2E tests for barely feasible and boundary scenarios.

scheduler-83: Tests for scenarios at the edge of feasibility, including
barely feasible configurations and boundary condition handling.
"""

from datetime import time

import pytest

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import Availability, ShiftType

from .conftest import create_period_dates, solve_and_verify


@pytest.mark.e2e
class TestBarelyFeasibleCoverage:
    """Tests for barely feasible coverage scenarios."""

    def test_exact_workers_for_exact_coverage(self, worker_factory) -> None:
        """Exactly N workers for shift requiring N."""
        workers = [worker_factory() for _ in range(3)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,  # Exactly 3 workers available
            ),
        ]

        periods = create_period_dates(num_periods=1)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success
        # All workers must be assigned
        period = result.schedule.periods[0]
        assert len(period.assignments) == 3

    def test_one_worker_slack_remains_feasible(self, worker_factory) -> None:
        """N+1 workers for shift requiring N."""
        workers = [worker_factory() for _ in range(4)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,  # 4 workers available = 1 slack
            ),
        ]

        periods = create_period_dates(num_periods=1)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success

    def test_one_worker_short_becomes_infeasible(self, worker_factory) -> None:
        """N-1 workers for shift requiring N."""
        workers = [worker_factory() for _ in range(2)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,  # 2 workers available = infeasible
            ),
        ]

        periods = create_period_dates(num_periods=1)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            expect_feasible=False,
        )

        assert not result.success


@pytest.mark.e2e
class TestBarelyFeasibleWithRestrictions:
    """Tests for barely feasible scenarios with restrictions."""

    def test_exactly_enough_unrestricted_workers(self, worker_factory) -> None:
        """Exactly N unrestricted workers for shift requiring N."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(),
            worker_factory(),
        ]

        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=2,  # Exactly 2 unrestricted
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success

    def test_one_unrestricted_short_becomes_infeasible(
        self, worker_factory
    ) -> None:
        """N-1 unrestricted workers for shift requiring N."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(),  # Only 1 unrestricted
        ]

        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=2,  # Need 2, only 1 unrestricted
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            expect_feasible=False,
        )

        assert not result.success


@pytest.mark.e2e
class TestBarelyFeasibleWithAvailability:
    """Tests for barely feasible scenarios with availability."""

    def test_exactly_enough_available_workers(self, worker_factory) -> None:
        """Exactly N available workers for shift requiring N."""
        workers = [worker_factory() for _ in range(4)]

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

        # Workers 0-1 unavailable for period 0
        # Leaves exactly 2 for period 0
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=periods[0][0],
                end_date=periods[0][1],
                availability_type="unavailable",
            ),
            Availability(
                worker_id=workers[1].id,
                start_date=periods[0][0],
                end_date=periods[0][1],
                availability_type="unavailable",
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            availabilities=availabilities,
        )

        assert result.success

    def test_one_available_short_becomes_infeasible(self, worker_factory) -> None:
        """N-1 available workers for shift requiring N."""
        workers = [worker_factory() for _ in range(3)]

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

        periods = create_period_dates(num_periods=1)

        # 2 workers unavailable, leaves only 1 for shift requiring 2
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=periods[0][0],
                end_date=periods[0][1],
                availability_type="unavailable",
            ),
            Availability(
                worker_id=workers[1].id,
                start_date=periods[0][0],
                end_date=periods[0][1],
                availability_type="unavailable",
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            availabilities=availabilities,
            expect_feasible=False,
        )

        assert not result.success


@pytest.mark.e2e
class TestZeroBoundaries:
    """Tests for zero-value boundary conditions."""

    def test_single_period_schedule(self, worker_factory) -> None:
        """Minimum: single period schedule."""
        workers = [worker_factory()]

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

        periods = create_period_dates(num_periods=1)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success
        assert len(result.schedule.periods) == 1

    def test_single_worker_schedule(self, worker_factory) -> None:
        """Minimum: single worker schedule."""
        workers = [worker_factory()]

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

        periods = create_period_dates(num_periods=4)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success
        assert len(result.schedule.workers) == 1

    def test_single_shift_type_schedule(self, worker_factory) -> None:
        """Minimum: single shift type schedule."""
        workers = [worker_factory() for _ in range(3)]

        shift_types = [
            ShiftType(
                id="only_shift",
                name="Only Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        periods = create_period_dates(num_periods=4)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success
        assert len(result.schedule.shift_types) == 1


@pytest.mark.e2e
class TestMaximumBoundaries:
    """Tests for high-value boundary conditions."""

    def test_many_workers_moderate_coverage(self, worker_factory) -> None:
        """Many workers with moderate coverage requirement."""
        workers = [worker_factory() for _ in range(20)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=5,
            ),
        ]

        periods = create_period_dates(num_periods=4)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success

    def test_many_shift_types_single_worker_each(self, worker_factory) -> None:
        """Many shift types each requiring 1 worker."""
        workers = [worker_factory() for _ in range(10)]

        shift_types = [
            ShiftType(
                id=f"shift_{i}",
                name=f"Shift {i}",
                category="day",
                start_time=time(6 + i, 0),
                end_time=time(14 + i, 0),
                duration_hours=8.0,
                workers_required=1,
            )
            for i in range(5)
        ]

        periods = create_period_dates(num_periods=2)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success

    @pytest.mark.slow
    def test_many_periods_schedule(self, worker_factory) -> None:
        """Schedule with many periods (12 weeks)."""
        workers = [worker_factory() for _ in range(8)]

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

        periods = create_period_dates(num_periods=12)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            time_limit_seconds=120,
        )

        assert result.success
        assert len(result.schedule.periods) == 12


@pytest.mark.e2e
class TestCombinedBoundaries:
    """Tests for combined boundary conditions."""

    def test_barely_feasible_with_all_constraints(self, worker_factory) -> None:
        """Barely feasible with all constraints enabled."""
        workers = [worker_factory() for _ in range(6)]

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
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "frequency": ConstraintConfig(enabled=True, is_hard=False, weight=50),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
        )

        assert result.success

    def test_tight_constraints_still_feasible(self, worker_factory) -> None:
        """Tight constraints but still feasible."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(),  # Can work night
            worker_factory(),  # Can work night
            worker_factory(),  # Can work night
        ]

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
                workers_required=2,  # Exactly 3 can work, need 2
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=2)

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
        )

        assert result.success
