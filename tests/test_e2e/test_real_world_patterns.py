"""E2E tests for real-world scheduling patterns.

scheduler-48: Tests realistic industry patterns including seasonal demand,
rotating schedules, seniority, and part-time distribution.
"""

from datetime import date, time, timedelta

import pytest

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import Availability, SchedulingRequest, ShiftType, Worker
from shift_solver.solver import ShiftSolver

from .conftest import create_period_dates, solve_and_verify


@pytest.mark.e2e
class TestSeasonalDemandVariations:
    """Tests for varying staffing requirements by period."""

    def test_varying_coverage_by_period(self, worker_factory) -> None:
        """Different workers_required for different periods (simulated)."""
        workers = [worker_factory() for _ in range(15)]

        # Simulate seasonal variation with different shift types
        # representing different coverage levels
        shift_types = [
            ShiftType(
                id="regular",
                name="Regular",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="peak",
                name="Peak",
                category="peak",
                start_time=time(10, 0),
                end_time=time(18, 0),
                duration_hours=8.0,
                workers_required=5,
            ),
            ShiftType(
                id="low",
                name="Low Season",
                category="low",
                start_time=time(10, 0),
                end_time=time(18, 0),
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

    def test_holiday_season_surge(self, worker_factory) -> None:
        """Increased demand during holiday period."""
        workers = [worker_factory() for _ in range(20)]

        shift_types = [
            ShiftType(
                id="normal",
                name="Normal",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=4,
            ),
            ShiftType(
                id="holiday_surge",
                name="Holiday Surge",
                category="holiday",
                start_time=time(8, 0),
                end_time=time(20, 0),
                duration_hours=12.0,
                workers_required=6,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=4)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success


@pytest.mark.e2e
class TestRotatingSchedules:
    """Tests for rotating schedule patterns."""

    def test_day_night_weekend_off_rotation(self, worker_factory, periods_4) -> None:
        """Rotating pattern: Day -> Night -> Weekend -> Off."""
        workers = [worker_factory() for _ in range(12)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
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

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=150),
            "sequence": ConstraintConfig(
                enabled=True,
                is_hard=False,
                weight=50,
                parameters={"min_gap_periods": 1},
            ),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs=constraint_configs,
        )

        assert result.success

    def test_three_shift_rotation(self, worker_factory) -> None:
        """Classic three-shift rotation pattern."""
        workers = [worker_factory() for _ in range(15)]

        shift_types = [
            ShiftType(
                id="first",
                name="First Shift",
                category="first",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="second",
                name="Second Shift",
                category="second",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="third",
                name="Third Shift",
                category="third",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=6)

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


@pytest.mark.e2e
class TestSeniorityBasedPreferences:
    """Tests for seniority-based scheduling preferences."""

    def test_seniority_via_request_priority(self, worker_factory, periods_4) -> None:
        """Model seniority using request priority levels."""
        # Create workers with seniority levels
        workers = [
            worker_factory(attributes={"seniority": 5, "name": "Senior 1"}),
            worker_factory(attributes={"seniority": 5, "name": "Senior 2"}),
            worker_factory(attributes={"seniority": 3, "name": "Mid 1"}),
            worker_factory(attributes={"seniority": 3, "name": "Mid 2"}),
            worker_factory(attributes={"seniority": 1, "name": "Junior 1"}),
            worker_factory(attributes={"seniority": 1, "name": "Junior 2"}),
        ]

        shift_types = [
            ShiftType(
                id="day",
                name="Day (Desirable)",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night (Undesirable)",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        period_start, period_end = periods_4[0]

        # Senior workers request day shifts with high priority
        # Junior workers have lower priority requests
        requests = []
        for worker in workers:
            seniority = worker.attributes.get("seniority", 1)
            requests.append(
                SchedulingRequest(
                    worker_id=worker.id,
                    start_date=period_start,
                    end_date=period_end,
                    request_type="positive",
                    shift_type_id="day",
                    priority=seniority,  # Seniority = priority
                )
            )

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=50),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        assert result.success

    def test_seniority_attributes_recorded(self, worker_factory, periods_4) -> None:
        """Verify worker attributes are preserved in schedule."""
        workers = [
            worker_factory(attributes={"seniority": i + 1, "department": "A"})
            for i in range(5)
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
            period_dates=periods_4,
        )

        assert result.success
        # Verify workers with attributes are in the schedule
        for worker in result.schedule.workers:
            assert "seniority" in worker.attributes


@pytest.mark.e2e
class TestTrainingMentorshipRequirements:
    """Tests for pairing/mentorship constraints."""

    def test_senior_junior_coverage_model(self, worker_factory, periods_4) -> None:
        """Model pairing by requiring coverage from different groups."""
        # Seniors and juniors
        seniors = [
            worker_factory(attributes={"level": "senior"}) for _ in range(4)
        ]
        # Juniors can't work alone (restrict from senior-only shift)
        juniors = [
            worker_factory(
                attributes={"level": "junior"},
                restricted_shifts=frozenset(["senior_only"]),
            )
            for _ in range(4)
        ]
        workers = seniors + juniors

        shift_types = [
            ShiftType(
                id="paired",
                name="Paired Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,  # Need both senior and junior
            ),
            ShiftType(
                id="senior_only",
                name="Senior Only",
                category="senior",
                start_time=time(17, 0),
                end_time=time(21, 0),
                duration_hours=4.0,
                workers_required=1,
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
        )

        assert result.success

    def test_training_shift_with_mentor(self, worker_factory, periods_4) -> None:
        """Training shifts require both trainee and mentor."""
        mentors = [worker_factory(attributes={"role": "mentor"}) for _ in range(3)]
        trainees = [
            worker_factory(
                attributes={"role": "trainee"},
                restricted_shifts=frozenset(["advanced"]),
            )
            for _ in range(3)
        ]
        workers = mentors + trainees

        shift_types = [
            ShiftType(
                id="training",
                name="Training",
                category="training",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,  # Mentor + trainee
            ),
            ShiftType(
                id="advanced",
                name="Advanced",
                category="advanced",
                start_time=time(17, 0),
                end_time=time(21, 0),
                duration_hours=4.0,
                workers_required=1,  # Mentors only
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
        )

        assert result.success


@pytest.mark.e2e
class TestPartTimeFullTimeDistribution:
    """Tests for part-time vs full-time worker distribution."""

    def test_mixed_part_time_full_time(self, worker_factory, periods_4) -> None:
        """Schedule with both part-time and full-time workers."""
        full_time = [
            worker_factory(attributes={"type": "full_time"}) for _ in range(5)
        ]
        part_time = [
            worker_factory(attributes={"type": "part_time"}) for _ in range(5)
        ]
        workers = full_time + part_time

        shift_types = [
            ShiftType(
                id="regular",
                name="Regular",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="short",
                name="Short",
                category="part",
                start_time=time(12, 0),
                end_time=time(16, 0),
                duration_hours=4.0,
                workers_required=2,
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
        )

        assert result.success

    def test_part_time_hour_limits(self, worker_factory, periods_4) -> None:
        """Part-time workers with shift restrictions."""
        full_time = [worker_factory() for _ in range(4)]
        # Part-time workers restricted from long shifts
        part_time = [
            worker_factory(restricted_shifts=frozenset(["long_shift"]))
            for _ in range(4)
        ]
        workers = full_time + part_time

        shift_types = [
            ShiftType(
                id="long_shift",
                name="Long Shift",
                category="long",
                start_time=time(6, 0),
                end_time=time(18, 0),
                duration_hours=12.0,
                workers_required=2,
            ),
            ShiftType(
                id="short_shift",
                name="Short Shift",
                category="short",
                start_time=time(9, 0),
                end_time=time(13, 0),
                duration_hours=4.0,
                workers_required=2,
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
        )

        assert result.success


@pytest.mark.e2e
class TestOnCallRotationPatterns:
    """Tests for on-call rotation patterns."""

    def test_weekly_on_call_rotation(self, worker_factory) -> None:
        """Weekly on-call rotation among workers."""
        workers = [worker_factory() for _ in range(8)]

        shift_types = [
            ShiftType(
                id="regular",
                name="Regular",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="on_call",
                name="On-Call",
                category="on_call",
                start_time=time(17, 0),
                end_time=time(9, 0),
                duration_hours=16.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=8)

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

        # Verify on-call distribution
        on_call_counts = {w.id: 0 for w in workers}
        for period in result.schedule.periods:
            for worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    if shift.shift_type_id == "on_call":
                        on_call_counts[worker_id] += 1

        # With 8 periods and 8 workers, each should have ~1 on-call
        values = list(on_call_counts.values())
        spread = max(values) - min(values)
        assert spread <= 2

    def test_backup_on_call_coverage(self, worker_factory, periods_4) -> None:
        """Primary and backup on-call coverage."""
        workers = [worker_factory() for _ in range(10)]

        shift_types = [
            ShiftType(
                id="regular",
                name="Regular",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="primary_on_call",
                name="Primary On-Call",
                category="on_call",
                start_time=time(17, 0),
                end_time=time(9, 0),
                duration_hours=16.0,
                workers_required=1,
                is_undesirable=True,
            ),
            ShiftType(
                id="backup_on_call",
                name="Backup On-Call",
                category="on_call",
                start_time=time(17, 0),
                end_time=time(9, 0),
                duration_hours=16.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=150),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs=constraint_configs,
        )

        assert result.success


@pytest.mark.e2e
class TestMixedPatterns:
    """Tests combining multiple real-world patterns."""

    def test_combined_patterns_realistic_scenario(self, worker_factory) -> None:
        """Realistic scenario combining multiple patterns."""
        # Mix of full-time, part-time, seniors
        full_time_senior = [
            worker_factory(attributes={"type": "full_time", "seniority": 5})
            for _ in range(4)
        ]
        full_time_junior = [
            worker_factory(attributes={"type": "full_time", "seniority": 1})
            for _ in range(4)
        ]
        part_time = [
            worker_factory(
                attributes={"type": "part_time", "seniority": 2},
                restricted_shifts=frozenset(["night", "on_call"]),
            )
            for _ in range(4)
        ]
        workers = full_time_senior + full_time_junior + part_time

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
                id="on_call",
                name="On-Call",
                category="on_call",
                start_time=time(17, 0),
                end_time=time(21, 0),
                duration_hours=4.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=4)
        period_start, period_end = periods[0]

        # Seniors request day shifts
        requests = [
            SchedulingRequest(
                worker_id=w.id,
                start_date=period_start,
                end_date=period_end,
                request_type="positive",
                shift_type_id="day",
                priority=w.attributes.get("seniority", 1),
            )
            for w in full_time_senior
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=75),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        assert result.success
        assert len(result.schedule.workers) == 12
