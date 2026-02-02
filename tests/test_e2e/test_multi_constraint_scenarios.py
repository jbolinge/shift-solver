"""E2E tests for multi-constraint interaction scenarios.

scheduler-81: Tests for complex interactions between multiple constraints,
including fairness + availability + request conflicts and constraint cascades.
"""

from datetime import time

import pytest

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import Availability, SchedulingRequest, ShiftType

from .conftest import create_period_dates, solve_and_verify


@pytest.mark.e2e
class TestFairnessAvailabilityRequestConflicts:
    """Tests for three-way conflicts between fairness, availability, and requests."""

    def test_fairness_vs_availability_constraint(
        self, worker_factory, periods_4
    ) -> None:
        """Fairness cannot balance when some workers are unavailable."""
        workers = [worker_factory() for _ in range(6)]
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

        # Half the workers unavailable for first period
        availabilities = [
            Availability(
                worker_id=workers[i].id,
                start_date=period_start,
                end_date=period_end,
                availability_type="unavailable",
            )
            for i in range(3)
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "availability": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            availabilities=availabilities,
            constraint_configs=constraint_configs,
        )

        assert result.success
        # Unavailable workers should not be assigned in period 0
        period_0 = result.schedule.periods[0]
        for i in range(3):
            worker_id = workers[i].id
            assert (
                worker_id not in period_0.assignments
                or not period_0.assignments[worker_id]
            )

    def test_request_vs_fairness_vs_availability(
        self, worker_factory, periods_4
    ) -> None:
        """Three-way conflict: request, fairness, and availability compete."""
        workers = [worker_factory() for _ in range(8)]

        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        # Workers 0-3 have negative requests for night
        # Workers 4-5 are unavailable for all periods
        # Only workers 6-7 are fully available without requests
        requests = [
            SchedulingRequest(
                worker_id=workers[i].id,
                start_date=periods_4[0][0],
                end_date=periods_4[-1][1],
                request_type="negative",
                shift_type_id="night",
                priority=3,
            )
            for i in range(4)
        ]

        availabilities = [
            Availability(
                worker_id=workers[i].id,
                start_date=periods_4[0][0],
                end_date=periods_4[-1][1],
                availability_type="unavailable",
            )
            for i in range(4, 6)
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "availability": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=50),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            availabilities=availabilities,
            constraint_configs=constraint_configs,
        )

        assert result.success


@pytest.mark.e2e
class TestConstraintCascadeEffects:
    """Tests for cascade effects where one constraint affects another."""

    def test_restriction_cascades_to_fairness(self, worker_factory, periods_4) -> None:
        """Restrictions reduce the pool, affecting fairness distribution."""
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
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs=constraint_configs,
        )

        assert result.success
        # Restricted workers should not work night shifts
        for period in result.schedule.periods:
            for i in range(2):
                worker_id = workers[i].id
                if worker_id in period.assignments:
                    assigned_shifts = period.assignments[worker_id]
                    assert "night" not in assigned_shifts

    def test_availability_cascades_to_frequency(
        self, worker_factory, periods_4
    ) -> None:
        """Unavailability affects frequency distribution."""
        workers = [worker_factory() for _ in range(6)]

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

        # Worker 0 unavailable for periods 0-2
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=periods_4[0][0],
                end_date=periods_4[2][1],
                availability_type="unavailable",
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "availability": ConstraintConfig(enabled=True, is_hard=True),
            "frequency": ConstraintConfig(
                enabled=True,
                is_hard=False,
                weight=50,
            ),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            availabilities=availabilities,
            constraint_configs=constraint_configs,
        )

        assert result.success


@pytest.mark.e2e
class TestConflictingRequestScenarios:
    """Tests for conflicting scheduling requests."""

    def test_all_workers_negative_request_same_shift(
        self, worker_factory, periods_4
    ) -> None:
        """All workers request to avoid the same shift - someone must work it."""
        workers = [worker_factory() for _ in range(5)]
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

        # All workers want to avoid night
        requests = [
            SchedulingRequest(
                worker_id=w.id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="night",
                priority=3,
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

        assert result.success
        # Coverage is hard, so someone must work night despite all requests

    def test_conflicting_positive_requests_same_shift(
        self, worker_factory, periods_4
    ) -> None:
        """Multiple workers request the same shift, but only one slot available."""
        workers = [worker_factory() for _ in range(5)]
        period_start, period_end = periods_4[0]

        shift_types = [
            ShiftType(
                id="preferred",
                name="Preferred Shift",
                category="day",
                start_time=time(10, 0),
                end_time=time(14, 0),
                duration_hours=4.0,
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
                shift_type_id="preferred",
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


@pytest.mark.e2e
class TestHardVsSoftConstraintTension:
    """Tests for tension between hard and soft constraints."""

    def test_hard_coverage_limits_soft_fairness(self, worker_factory) -> None:
        """Hard coverage requirements limit fairness optimization."""
        workers = [worker_factory() for _ in range(4)]

        shift_types = [
            ShiftType(
                id="undesirable",
                name="Undesirable Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=3,  # 3 of 4 workers must work each period
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=4)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=1000),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
        )

        assert result.success
        # With 4 workers and 3 required per period, fairness is constrained

    def test_hard_availability_blocks_soft_request(
        self, worker_factory, periods_4
    ) -> None:
        """Hard availability prevents honoring soft requests."""
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
                workers_required=2,
            ),
        ]

        # Worker 0 has positive request for period 0
        requests = [
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                request_type="positive",
                shift_type_id="shift",
                priority=5,
            ),
        ]

        # But worker 0 is unavailable for period 0
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
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            availabilities=availabilities,
            constraint_configs=constraint_configs,
        )

        assert result.success
        # Worker 0 should NOT be assigned to period 0 despite request
        period_0 = result.schedule.periods[0]
        assert (
            workers[0].id not in period_0.assignments
            or not period_0.assignments[workers[0].id]
        )


@pytest.mark.e2e
class TestSequenceAndOtherConstraints:
    """Tests for sequence constraint interactions."""

    def test_sequence_vs_coverage_balance(self, worker_factory) -> None:
        """Sequence constraint with tight coverage requirements."""
        workers = [worker_factory() for _ in range(6)]

        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=8)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "sequence": ConstraintConfig(
                enabled=True,
                is_hard=False,
                weight=50,
                parameters={"max_consecutive_same_category": 2},
            ),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
        )

        assert result.success

    def test_max_absence_with_availability(self, worker_factory, periods_4) -> None:
        """Max absence constraint combined with availability."""
        workers = [worker_factory() for _ in range(6)]

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

        # Worker 0 unavailable for period 0
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=periods_4[0][0],
                end_date=periods_4[0][1],
                availability_type="unavailable",
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "availability": ConstraintConfig(enabled=True, is_hard=True),
            "max_absence": ConstraintConfig(
                enabled=True,
                is_hard=False,
                weight=50,
                parameters={"max_consecutive_absent": 2},
            ),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            availabilities=availabilities,
            constraint_configs=constraint_configs,
        )

        assert result.success


@pytest.mark.e2e
class TestComplexRealWorldScenarios:
    """Complex real-world-like scenarios with multiple constraints."""

    @pytest.mark.slow
    def test_hospital_like_scenario(self, worker_factory) -> None:
        """Hospital-like scenario with multiple shift types and constraints."""
        # 12 nurses for 3 shifts
        workers = [worker_factory() for _ in range(12)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift (7am-3pm)",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="evening",
                name="Evening Shift (3pm-11pm)",
                category="evening",
                start_time=time(15, 0),
                end_time=time(23, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night Shift (11pm-7am)",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=4)

        # Some workers restricted from night
        workers[0] = worker_factory(
            id=workers[0].id,
            name=workers[0].name,
            restricted_shifts=frozenset(["night"]),
        )
        workers[1] = worker_factory(
            id=workers[1].id,
            name=workers[1].name,
            restricted_shifts=frozenset(["night"]),
        )

        # Some availability constraints
        availabilities = [
            Availability(
                worker_id=workers[3].id,
                start_date=periods[0][0],
                end_date=periods[0][1],
                availability_type="unavailable",
            ),
            Availability(
                worker_id=workers[4].id,
                start_date=periods[2][0],
                end_date=periods[2][1],
                availability_type="unavailable",
            ),
        ]

        # Some requests
        requests = [
            SchedulingRequest(
                worker_id=workers[5].id,
                start_date=periods[1][0],
                end_date=periods[1][1],
                request_type="positive",
                shift_type_id="day",
                priority=2,
            ),
            SchedulingRequest(
                worker_id=workers[6].id,
                start_date=periods[0][0],
                end_date=periods[0][1],
                request_type="negative",
                shift_type_id="night",
                priority=3,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "availability": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "frequency": ConstraintConfig(enabled=True, is_hard=False, weight=50),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=75),
            "sequence": ConstraintConfig(
                enabled=True,
                is_hard=False,
                weight=30,
                parameters={"max_consecutive_same_category": 3},
            ),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            requests=requests,
            availabilities=availabilities,
            constraint_configs=constraint_configs,
            time_limit_seconds=120,
        )

        assert result.success
        assert len(result.schedule.periods) == 4

    def test_retail_like_scenario(self, worker_factory, periods_4) -> None:
        """Retail-like scenario with part-time and full-time mix."""
        # Mix of full-time and part-time workers
        full_time = [
            worker_factory(id=f"FT{i+1:03d}", name=f"Full Time {i+1}")
            for i in range(4)
        ]
        part_time = [
            worker_factory(id=f"PT{i+1:03d}", name=f"Part Time {i+1}")
            for i in range(6)
        ]
        workers = full_time + part_time

        shift_types = [
            ShiftType(
                id="morning",
                name="Morning (6am-2pm)",
                category="day",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="afternoon",
                name="Afternoon (2pm-10pm)",
                category="evening",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="closing",
                name="Closing (6pm-10pm)",
                category="evening",
                start_time=time(18, 0),
                end_time=time(22, 0),
                duration_hours=4.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "frequency": ConstraintConfig(enabled=True, is_hard=False, weight=50),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs=constraint_configs,
        )

        assert result.success
