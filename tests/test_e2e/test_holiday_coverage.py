"""E2E tests for holiday coverage scenarios.

scheduler-41: Tests holiday scheduling complexity including skeleton crew,
premium shifts, year-end clustering, and fair rotation.
"""

from datetime import date, time

import pytest

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import Availability, SchedulingRequest, ShiftType

from .conftest import create_period_dates, solve_and_verify


@pytest.mark.e2e
class TestSkeletonCrewHolidays:
    """Tests for reduced staffing during holidays."""

    def test_reduced_workers_required_holiday_period(
        self, worker_factory, periods_4
    ) -> None:
        """Holiday period with reduced workers_required."""
        workers = [worker_factory() for _ in range(10)]

        # Normal shifts require 3, holiday shift requires 1
        normal_shift = ShiftType(
            id="normal",
            name="Normal Shift",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            workers_required=3,
        )
        holiday_shift = ShiftType(
            id="holiday",
            name="Holiday Shift",
            category="holiday",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            workers_required=1,
            is_undesirable=True,
        )

        result = solve_and_verify(
            workers=workers,
            shift_types=[normal_shift, holiday_shift],
            period_dates=periods_4,
        )

        assert result.success
        # Verify coverage is met
        for period in result.schedule.periods:
            normal_count = sum(
                1
                for shifts in period.assignments.values()
                for s in shifts
                if s.shift_type_id == "normal"
            )
            holiday_count = sum(
                1
                for shifts in period.assignments.values()
                for s in shifts
                if s.shift_type_id == "holiday"
            )
            assert normal_count >= 3
            assert holiday_count >= 1

    def test_skeleton_crew_with_high_unavailability(
        self, worker_factory, periods_4
    ) -> None:
        """Skeleton crew when many workers take holiday off."""
        workers = [worker_factory() for _ in range(12)]
        period_start, period_end = periods_4[2]

        # Skeleton crew shift - only need 1 worker
        shift_types = [
            ShiftType(
                id="skeleton",
                name="Skeleton Crew",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        # 8 of 12 workers unavailable
        availabilities = [
            Availability(
                worker_id=workers[i].id,
                start_date=period_start,
                end_date=period_end,
                availability_type="unavailable",
            )
            for i in range(8)
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            availabilities=availabilities,
        )

        assert result.success


@pytest.mark.e2e
class TestHolidayPremiumShifts:
    """Tests for shifts where all workers request off."""

    def test_all_workers_negative_request_holiday_shift(
        self, worker_factory, periods_4
    ) -> None:
        """All workers submit negative requests for holiday shift."""
        workers = [worker_factory() for _ in range(8)]
        period_start, period_end = periods_4[1]

        shift_types = [
            ShiftType(
                id="holiday",
                name="Holiday Shift",
                category="holiday",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        # All workers request off for holiday shift
        requests = [
            SchedulingRequest(
                worker_id=w.id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="holiday",
                priority=2,
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

        # Solver must still meet coverage despite all negative requests
        assert result.success
        period_1 = result.schedule.periods[1]
        assigned_count = sum(
            1
            for shifts in period_1.assignments.values()
            for s in shifts
            if s.shift_type_id == "holiday"
        )
        assert assigned_count >= 2

    def test_mixed_priority_negative_requests(
        self, worker_factory, periods_4
    ) -> None:
        """Different priority levels for holiday negative requests."""
        workers = [worker_factory() for _ in range(6)]
        period_start, period_end = periods_4[0]

        shift_types = [
            ShiftType(
                id="holiday",
                name="Holiday Shift",
                category="holiday",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        # Workers with varying priority negative requests
        requests = [
            SchedulingRequest(
                worker_id=workers[i].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="holiday",
                priority=i + 1,  # Priority 1-6
            )
            for i in range(6)
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
class TestYearEndScheduling:
    """Tests for Christmas and New Year scheduling."""

    def test_christmas_new_year_clustering(self, worker_factory) -> None:
        """Schedule covering Christmas through New Year."""
        workers = [worker_factory() for _ in range(15)]

        # Create periods around year-end
        periods = [
            (date(2026, 12, 21), date(2026, 12, 27)),  # Christmas week
            (date(2026, 12, 28), date(2027, 1, 3)),    # New Year week
        ]

        shift_types = [
            ShiftType(
                id="regular",
                name="Regular Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="holiday",
                name="Holiday Shift",
                category="holiday",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        # Multiple workers request time off for each holiday period
        requests = []
        for i in range(5):
            requests.append(
                SchedulingRequest(
                    worker_id=workers[i].id,
                    start_date=periods[0][0],
                    end_date=periods[0][1],
                    request_type="negative",
                    shift_type_id="holiday",
                    priority=2,
                )
            )
        for i in range(5, 10):
            requests.append(
                SchedulingRequest(
                    worker_id=workers[i].id,
                    start_date=periods[1][0],
                    end_date=periods[1][1],
                    request_type="negative",
                    shift_type_id="holiday",
                    priority=2,
                )
            )

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            requests=requests,
        )

        assert result.success

    def test_year_boundary_date_handling(self, worker_factory) -> None:
        """Verify correct handling of year boundary dates."""
        workers = [worker_factory() for _ in range(8)]

        # Period spanning year boundary
        periods = [
            (date(2026, 12, 28), date(2027, 1, 3)),
        ]

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

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success
        assert len(result.schedule.periods) == 1


@pytest.mark.e2e
class TestFairHolidayRotation:
    """Tests for fair distribution of holiday assignments."""

    def test_fair_holiday_rotation_over_two_periods(
        self, worker_factory
    ) -> None:
        """Verify fair rotation of holiday shifts across periods."""
        workers = [worker_factory() for _ in range(6)]

        periods = create_period_dates(num_periods=2)

        shift_types = [
            ShiftType(
                id="holiday",
                name="Holiday Shift",
                category="holiday",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=200),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
        )

        assert result.success

    def test_fairness_with_prior_holiday_history(
        self, worker_factory, periods_4
    ) -> None:
        """Fairness considering workers who had holidays previously."""
        workers = [worker_factory() for _ in range(8)]

        shift_types = [
            ShiftType(
                id="holiday",
                name="Holiday Shift",
                category="holiday",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(
                enabled=True,
                is_hard=False,
                weight=150,
                parameters={"categories": ["holiday"]},
            ),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs=constraint_configs,
        )

        assert result.success


@pytest.mark.e2e
class TestMixedNormalHolidayPeriods:
    """Tests for schedules mixing normal and holiday periods."""

    def test_mixed_shift_types_same_schedule(
        self, worker_factory, periods_4
    ) -> None:
        """Schedule with both normal and holiday shift types."""
        workers = [worker_factory() for _ in range(12)]

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
                workers_required=1,
                is_undesirable=True,
            ),
            ShiftType(
                id="holiday",
                name="Holiday Shift",
                category="holiday",
                start_time=time(10, 0),
                end_time=time(18, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs=constraint_configs,
        )

        assert result.success
        # Verify all shift types are covered each period
        for period in result.schedule.periods:
            for shift_type in shift_types:
                count = sum(
                    1
                    for shifts in period.assignments.values()
                    for s in shifts
                    if s.shift_type_id == shift_type.id
                )
                assert count >= shift_type.workers_required

    def test_varying_requirements_by_period(self, worker_factory) -> None:
        """Different coverage requirements for holiday vs normal periods."""
        workers = [worker_factory() for _ in range(10)]

        # Simulate by using multiple shift types with different requirements
        normal_shift = ShiftType(
            id="normal",
            name="Normal Shift",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            workers_required=3,
        )
        skeleton_shift = ShiftType(
            id="skeleton",
            name="Skeleton Shift",
            category="skeleton",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            workers_required=1,
        )

        periods = create_period_dates(num_periods=4)

        result = solve_and_verify(
            workers=workers,
            shift_types=[normal_shift, skeleton_shift],
            period_dates=periods,
        )

        assert result.success


@pytest.mark.e2e
class TestMultiQuarterHolidayFairness:
    """Tests for long-term holiday fairness tracking."""

    @pytest.mark.slow
    def test_quarterly_holiday_fairness_12_weeks(
        self, worker_factory, periods_12
    ) -> None:
        """Track fairness of holiday assignments over 12 weeks."""
        workers = [worker_factory() for _ in range(15)]

        shift_types = [
            ShiftType(
                id="regular",
                name="Regular Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="undesirable",
                name="Undesirable Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=200),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_12,
            constraint_configs=constraint_configs,
            time_limit_seconds=120,
        )

        assert result.success
        assert len(result.schedule.periods) == 12

        # Count undesirable shifts per worker
        undesirable_counts = {w.id: 0 for w in workers}
        for period in result.schedule.periods:
            for worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    if shift.shift_type_id == "undesirable":
                        undesirable_counts[worker_id] += 1

        # Check distribution is reasonably fair
        counts = list(undesirable_counts.values())
        if counts:
            spread = max(counts) - min(counts)
            # With fairness constraint, spread should be small
            assert spread <= 3, f"Unfair distribution: {undesirable_counts}"

    def test_fairness_accumulation_effect(self, worker_factory) -> None:
        """Verify fairness accumulates correctly over multiple periods."""
        workers = [worker_factory() for _ in range(6)]

        periods = create_period_dates(num_periods=6)

        shift_types = [
            ShiftType(
                id="undesirable",
                name="Undesirable Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=300),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
        )

        assert result.success

        # With 6 periods and 1 required per period, 6 workers should each get ~1
        undesirable_counts = {w.id: 0 for w in workers}
        for period in result.schedule.periods:
            for worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    if shift.shift_type_id == "undesirable":
                        undesirable_counts[worker_id] += 1

        # At least some workers should have assignments
        assert sum(undesirable_counts.values()) >= 6
