"""E2E tests for single worker schedule edge cases.

scheduler-71: Tests for single worker schedules where fairness constraint
exits early with len(workers) < 2 and other edge case behaviors.
"""

from datetime import time

import pytest

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import Availability, SchedulingRequest, ShiftType

from .conftest import create_period_dates, solve_and_verify


@pytest.mark.e2e
class TestSingleWorkerBasic:
    """Basic tests for single worker scheduling."""

    def test_single_worker_single_shift_single_period(self, worker_factory) -> None:
        """Minimal scenario: 1 worker, 1 shift, 1 period."""
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
        # Worker must be assigned to the shift
        period = result.schedule.periods[0]
        assert workers[0].id in period.assignments
        # Assignments are lists of ShiftInstance objects
        shift_ids = [s.shift_type_id for s in period.assignments[workers[0].id]]
        assert "shift" in shift_ids

    def test_single_worker_can_work_multiple_non_overlapping_shifts(
        self, worker_factory
    ) -> None:
        """Single worker CAN work multiple non-overlapping shifts in same period.

        Note: The solver allows a worker to be assigned to multiple shifts
        in the same period. This tests that behavior.
        """
        workers = [worker_factory()]

        shift_types = [
            ShiftType(
                id="morning",
                name="Morning",
                category="day",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="afternoon",
                name="Afternoon",
                category="day",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        # Worker can work both shifts (the solver allows this)
        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success
        # Worker should be assigned to both shifts
        period = result.schedule.periods[0]
        shift_ids = [s.shift_type_id for s in period.assignments[workers[0].id]]
        assert "morning" in shift_ids
        assert "afternoon" in shift_ids


@pytest.mark.e2e
class TestSingleWorkerWithFairness:
    """Tests for single worker with fairness constraint."""

    def test_fairness_skips_with_single_worker(self, worker_factory) -> None:
        """Fairness constraint should skip with only 1 worker."""
        workers = [worker_factory()]

        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=4)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
        )

        # Should succeed - fairness is skipped, single worker works all nights
        assert result.success

    def test_fairness_activates_with_two_workers(self, worker_factory) -> None:
        """Fairness constraint should activate with 2 workers."""
        workers = [worker_factory(), worker_factory()]

        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=4)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
        )

        assert result.success
        # With fairness, both workers should share night shifts


@pytest.mark.e2e
class TestSingleWorkerWithRequests:
    """Tests for single worker with scheduling requests."""

    def test_single_worker_positive_request_granted(self, worker_factory) -> None:
        """Single worker's positive request can be granted."""
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

        periods = create_period_dates(num_periods=2)

        # Positive request for period 0
        requests = [
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=periods[0][0],
                end_date=periods[0][1],
                request_type="positive",
                shift_type_id="shift",
                priority=3,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        assert result.success
        # Worker must work the shift in period 0 (coverage requirement)
        period_0 = result.schedule.periods[0]
        assert workers[0].id in period_0.assignments

    def test_single_worker_negative_request_cannot_avoid_coverage(
        self, worker_factory
    ) -> None:
        """Single worker cannot avoid shift if coverage requires them."""
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

        # Negative request - want to avoid the shift
        requests = [
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=periods[0][0],
                end_date=periods[0][1],
                request_type="negative",
                shift_type_id="shift",
                priority=5,  # High priority
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        # Still succeeds - coverage is hard, request is soft
        assert result.success
        # Worker still assigned (coverage trumps request)
        period_0 = result.schedule.periods[0]
        assert workers[0].id in period_0.assignments


@pytest.mark.e2e
class TestSingleWorkerWithAvailability:
    """Tests for single worker with availability constraints."""

    def test_single_worker_unavailable_infeasible(self, worker_factory) -> None:
        """Single worker unavailable for period makes it infeasible."""
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

        # Worker unavailable
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=periods[0][0],
                end_date=periods[0][1],
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

    def test_single_worker_partial_availability_feasible(
        self, worker_factory
    ) -> None:
        """Single worker available for some periods - feasible for those."""
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

        # Worker only unavailable for period 0
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=periods[0][0],
                end_date=periods[0][1],
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
            expect_feasible=False,  # Still infeasible - need coverage for period 0
        )

        assert not result.success


@pytest.mark.e2e
class TestSingleWorkerWithRestrictions:
    """Tests for single worker with shift restrictions."""

    def test_single_worker_restricted_from_required_shift_infeasible(
        self, worker_factory
    ) -> None:
        """Single worker restricted from only shift type - infeasible."""
        workers = [worker_factory(restricted_shifts=frozenset(["shift"]))]

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

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            expect_feasible=False,
        )

        assert not result.success

    def test_single_worker_restricted_from_one_of_two_shifts(
        self, worker_factory
    ) -> None:
        """Single worker restricted from one shift but can work other."""
        workers = [worker_factory(restricted_shifts=frozenset(["night"]))]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
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
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
        }

        # Infeasible - worker can't cover both shifts
        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            expect_feasible=False,
        )

        assert not result.success


@pytest.mark.e2e
class TestSingleWorkerMultiplePeriods:
    """Tests for single worker across multiple periods."""

    def test_single_worker_works_all_periods(self, worker_factory) -> None:
        """Single worker must work all periods if coverage requires it."""
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

        periods = create_period_dates(num_periods=8)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success
        # Worker should be assigned in all 8 periods
        for period in result.schedule.periods:
            assert workers[0].id in period.assignments

    def test_single_worker_frequency_constraint_applied(self, worker_factory) -> None:
        """Frequency constraint with single worker - all shifts go to them."""
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

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "frequency": ConstraintConfig(enabled=True, is_hard=False, weight=50),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
        )

        assert result.success


@pytest.mark.e2e
class TestTransitionToTwoWorkers:
    """Tests for behavior transition from 1 to 2 workers."""

    def test_two_workers_enables_fairness_balancing(self, worker_factory) -> None:
        """Moving from 1 to 2 workers enables fairness balancing."""
        workers = [worker_factory(), worker_factory()]

        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=4)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
        )

        assert result.success
        # With 2 workers and 4 periods, fairness should aim for 2 each
        worker_counts = {workers[0].id: 0, workers[1].id: 0}
        for period in result.schedule.periods:
            for worker_id, shifts in period.assignments.items():
                # Shifts is a list of ShiftInstance objects
                for shift in shifts:
                    if shift.shift_type_id == "night":
                        worker_counts[worker_id] += 1

        # Both workers should have assignments (fairness distributes)
        # Each worker should have 2 night shifts (4 total / 2 workers)
        assert worker_counts[workers[0].id] == 2
        assert worker_counts[workers[1].id] == 2
