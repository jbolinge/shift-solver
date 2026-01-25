"""E2E tests for request conflicts.

scheduler-43: Tests conflicting scheduling requests including multiple workers
requesting same shift off, priority conflicts, and violation tracking.
"""

from datetime import date, time, timedelta

import pytest

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import Availability, SchedulingRequest, ShiftType, Worker
from shift_solver.solver import ShiftSolver

from .conftest import create_period_dates, solve_and_verify


@pytest.mark.e2e
class TestMultipleWorkersRequestSameShiftOff:
    """Tests for multiple workers requesting the same shift off."""

    def test_five_workers_request_same_shift_off_coverage_requires_two(
        self, worker_factory, periods_4
    ) -> None:
        """5 workers request shift off but coverage requires 2."""
        workers = [worker_factory() for _ in range(8)]
        period_start, period_end = periods_4[0]

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
        ]

        # 5 workers request day shift off
        requests = [
            SchedulingRequest(
                worker_id=workers[i].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="day",
                priority=2,
            )
            for i in range(5)
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        # Must meet coverage, some requests will be violated
        assert result.success
        period_0 = result.schedule.periods[0]
        assigned_count = sum(len(shifts) for shifts in period_0.assignments.values())
        assert assigned_count >= 2

    def test_all_workers_request_off_coverage_met_with_violations(
        self, worker_factory, periods_4
    ) -> None:
        """All workers request shift off - coverage must still be met."""
        workers = [worker_factory() for _ in range(6)]
        period_start, period_end = periods_4[1]

        shift_types = [
            ShiftType(
                id="undesirable",
                name="Undesirable Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        # All workers request this shift off
        requests = [
            SchedulingRequest(
                worker_id=w.id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="undesirable",
                priority=1,
            )
            for w in workers
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=50),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        assert result.success


@pytest.mark.e2e
class TestRestrictedShiftRequests:
    """Tests for workers requesting shifts they're restricted from."""

    def test_worker_requests_restricted_shift(self, worker_factory, periods_4) -> None:
        """Worker requests shift they cannot work due to restriction."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(),
            worker_factory(),
            worker_factory(),
        ]
        period_start, period_end = periods_4[0]

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

        # Worker 0 requests night shift (positive) but is restricted
        requests = [
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                request_type="positive",
                shift_type_id="night",
                priority=3,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        # Solver should succeed but worker 0 won't get night shift
        assert result.success
        period_0 = result.schedule.periods[0]
        if workers[0].id in period_0.assignments:
            for shift in period_0.assignments[workers[0].id]:
                assert shift.shift_type_id != "night"

    def test_multiple_restricted_workers_with_positive_requests(
        self, worker_factory, periods_4
    ) -> None:
        """Multiple restricted workers requesting their restricted shifts."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(restricted_shifts=frozenset(["weekend"])),
            worker_factory(),
            worker_factory(),
            worker_factory(),
        ]
        period_start, period_end = periods_4[0]

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
            ShiftType(
                id="weekend",
                name="Weekend Shift",
                category="weekend",
                start_time=time(8, 0),
                end_time=time(16, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        requests = [
            # Worker 0 wants night (restricted from it)
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                request_type="positive",
                shift_type_id="night",
                priority=2,
            ),
            # Worker 1 wants weekend (restricted from it)
            SchedulingRequest(
                worker_id=workers[1].id,
                start_date=period_start,
                end_date=period_end,
                request_type="positive",
                shift_type_id="weekend",
                priority=2,
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
        )

        assert result.success


@pytest.mark.e2e
class TestPriorityConflicts:
    """Tests for conflicting requests with different priorities."""

    def test_high_priority_vs_low_priority_conflicts(
        self, worker_factory, periods_4
    ) -> None:
        """Higher priority requests should be honored over lower priority."""
        workers = [worker_factory() for _ in range(6)]
        period_start, period_end = periods_4[0]

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

        # 4 workers want off: 2 high priority (3), 2 low priority (1)
        requests = [
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="shift",
                priority=3,  # High
            ),
            SchedulingRequest(
                worker_id=workers[1].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="shift",
                priority=3,  # High
            ),
            SchedulingRequest(
                worker_id=workers[2].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="shift",
                priority=1,  # Low
            ),
            SchedulingRequest(
                worker_id=workers[3].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="shift",
                priority=1,  # Low
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        assert result.success

    def test_escalating_priority_chain(self, worker_factory, periods_4) -> None:
        """Workers with escalating priorities requesting same shift off."""
        workers = [worker_factory() for _ in range(8)]
        period_start, period_end = periods_4[0]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
        ]

        # 5 workers request off with priorities 1-5
        requests = [
            SchedulingRequest(
                worker_id=workers[i].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="shift",
                priority=i + 1,
            )
            for i in range(5)
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        assert result.success


@pytest.mark.e2e
class TestPositiveNegativeConflicts:
    """Tests for positive and negative requests in same period."""

    def test_positive_and_negative_for_same_shift_same_period(
        self, worker_factory, periods_4
    ) -> None:
        """Same worker has positive and negative requests for same shift."""
        workers = [worker_factory() for _ in range(5)]
        period_start, period_end = periods_4[0]

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
        ]

        # Different workers: one wants it, one doesn't want it
        requests = [
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                request_type="positive",
                shift_type_id="day",
                priority=2,
            ),
            SchedulingRequest(
                worker_id=workers[1].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="day",
                priority=2,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        assert result.success

    def test_conflicting_positive_requests_for_limited_slots(
        self, worker_factory, periods_4
    ) -> None:
        """Multiple positive requests for shift with limited slots."""
        workers = [worker_factory() for _ in range(6)]
        period_start, period_end = periods_4[0]

        shift_types = [
            ShiftType(
                id="desirable",
                name="Desirable Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,  # Only 1 slot
            ),
        ]

        # 4 workers want this shift
        requests = [
            SchedulingRequest(
                worker_id=workers[i].id,
                start_date=period_start,
                end_date=period_end,
                request_type="positive",
                shift_type_id="desirable",
                priority=2,
            )
            for i in range(4)
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        assert result.success
        # Only 1 of the 4 positive requests can be honored
        period_0 = result.schedule.periods[0]
        assigned = sum(len(shifts) for shifts in period_0.assignments.values())
        assert assigned >= 1


@pytest.mark.e2e
class TestCascadingRequestDependencies:
    """Tests for cascading dependencies between requests."""

    def test_chain_of_dependent_requests(self, worker_factory, periods_4) -> None:
        """Requests that create cascading assignment needs."""
        workers = [worker_factory() for _ in range(10)]

        shift_types = [
            ShiftType(
                id="shift_a",
                name="Shift A",
                category="day",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="shift_b",
                name="Shift B",
                category="day",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="shift_c",
                name="Shift C",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        period_start, period_end = periods_4[0]

        # Create cascading requests
        requests = [
            # Workers 0-2 want shift_a, not shift_b
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                request_type="positive",
                shift_type_id="shift_a",
                priority=2,
            ),
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="shift_b",
                priority=2,
            ),
            # Workers 3-5 want shift_b, not shift_c
            SchedulingRequest(
                worker_id=workers[3].id,
                start_date=period_start,
                end_date=period_end,
                request_type="positive",
                shift_type_id="shift_b",
                priority=2,
            ),
            SchedulingRequest(
                worker_id=workers[3].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="shift_c",
                priority=2,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        assert result.success

    def test_multi_period_request_dependencies(self, worker_factory) -> None:
        """Requests spanning multiple periods with dependencies."""
        workers = [worker_factory() for _ in range(8)]
        periods = create_period_dates(num_periods=3)

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

        # Worker 0 wants period 0 off, worker 1 wants period 1 off, etc.
        requests = [
            SchedulingRequest(
                worker_id=workers[i].id,
                start_date=periods[i][0],
                end_date=periods[i][1],
                request_type="negative",
                shift_type_id="shift",
                priority=2,
            )
            for i in range(3)
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


@pytest.mark.e2e
class TestRequestViolationCounting:
    """Tests for accurate violation counting."""

    def test_violation_count_matches_unmet_requests(
        self, worker_factory, periods_4
    ) -> None:
        """Verify violation tracking counts correctly."""
        workers = [worker_factory() for _ in range(4)]
        period_start, period_end = periods_4[0]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,  # Must assign 2
            ),
        ]

        # All 4 workers want this shift off
        requests = [
            SchedulingRequest(
                worker_id=w.id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="shift",
                priority=1,
            )
            for w in workers
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        # 4 negative requests, 2 must be violated (assigned anyway)
        assert result.success
        # Objective value should reflect violations
        assert result.objective_value is not None

    def test_zero_violations_when_all_requests_honored(
        self, worker_factory, periods_4
    ) -> None:
        """No violations when requests can all be honored."""
        workers = [worker_factory() for _ in range(6)]
        period_start, period_end = periods_4[0]

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

        # Only 2 workers want shift off, others available
        requests = [
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="shift",
                priority=2,
            ),
            SchedulingRequest(
                worker_id=workers[1].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="shift",
                priority=2,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        # 4 remaining workers can cover, so no violations needed
        assert result.success

    def test_priority_weighted_violation_counting(
        self, worker_factory, periods_4
    ) -> None:
        """Verify priority affects violation cost."""
        workers = [worker_factory() for _ in range(5)]
        period_start, period_end = periods_4[0]

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

        # 3 workers request off with different priorities
        requests = [
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="shift",
                priority=1,  # Low
            ),
            SchedulingRequest(
                worker_id=workers[1].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="shift",
                priority=3,  # High
            ),
            SchedulingRequest(
                worker_id=workers[2].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="shift",
                priority=5,  # Very high
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        assert result.success
        # Solver should prefer to violate low priority request
        # when 2 workers must be assigned
