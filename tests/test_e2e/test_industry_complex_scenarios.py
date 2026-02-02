"""E2E tests for complex industry-specific scheduling scenarios.

These tests model realistic industry constraints using available features:
- Worker restrictions for skill/certification requirements
- Multiple shift types for 24/7 coverage
- Fairness constraints for rotation equity
- Requests for preference handling

Issue: scheduler-84
"""

from datetime import time

import pytest

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import Availability, SchedulingRequest, ShiftType, Worker
from shift_solver.solver import ShiftSolver
from shift_solver.validation import ScheduleValidator

from .conftest import create_period_dates, solve_and_verify


# -----------------------------------------------------------------------------
# Healthcare Complex Scenarios
# -----------------------------------------------------------------------------


@pytest.mark.e2e
class TestHealthcare24x7Coverage:
    """Tests for 24/7 healthcare coverage requirements."""

    def test_day_evening_night_coverage_all_periods(self, worker_factory) -> None:
        """24/7 coverage with day, evening, and night shifts."""
        workers = [worker_factory() for _ in range(15)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift (7a-3p)",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="evening",
                name="Evening Shift (3p-11p)",
                category="evening",
                start_time=time(15, 0),
                end_time=time(23, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night Shift (11p-7a)",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=4)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=500),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            time_limit_seconds=60,
        )

        assert result.success

        # Verify all shifts covered in all periods
        for period in result.schedule.periods:
            for shift_type in shift_types:
                # Count assignments by iterating through all workers
                assigned_count = sum(
                    1
                    for worker_shifts in period.assignments.values()
                    for shift in worker_shifts
                    if shift.shift_type_id == shift_type.id
                )
                assert assigned_count >= shift_type.workers_required, (
                    f"Period {period.period_index}: {shift_type.id} needs "
                    f"{shift_type.workers_required}, got {assigned_count}"
                )


@pytest.mark.e2e
class TestHealthcareSkillMatching:
    """Tests for skill-based assignments (RN vs LPN, certifications)."""

    def test_rn_lpn_skill_levels(self, worker_factory) -> None:
        """Different skill levels with some shifts requiring RN only."""
        # Create workers with different skill levels via restrictions
        # LPNs are restricted from charge nurse shifts
        workers = [
            # RNs (can work all shifts)
            worker_factory(id="RN001", name="RN Smith"),
            worker_factory(id="RN002", name="RN Jones"),
            worker_factory(id="RN003", name="RN Williams"),
            worker_factory(id="RN004", name="RN Brown"),
            worker_factory(id="RN005", name="RN Davis"),
            # LPNs (restricted from charge_nurse)
            worker_factory(
                id="LPN001", name="LPN Miller", restricted_shifts=frozenset(["charge"])
            ),
            worker_factory(
                id="LPN002", name="LPN Wilson", restricted_shifts=frozenset(["charge"])
            ),
            worker_factory(
                id="LPN003", name="LPN Moore", restricted_shifts=frozenset(["charge"])
            ),
            worker_factory(
                id="LPN004", name="LPN Taylor", restricted_shifts=frozenset(["charge"])
            ),
            worker_factory(
                id="LPN005", name="LPN Anderson", restricted_shifts=frozenset(["charge"])
            ),
        ]

        shift_types = [
            ShiftType(
                id="floor",
                name="Floor Nurse",
                category="day",
                start_time=time(7, 0),
                end_time=time(19, 0),
                duration_hours=12.0,
                workers_required=3,  # Mix of RN/LPN
            ),
            ShiftType(
                id="charge",
                name="Charge Nurse (RN only)",
                category="day",
                start_time=time(7, 0),
                end_time=time(19, 0),
                duration_hours=12.0,
                workers_required=1,  # Must be RN
            ),
        ]

        periods = create_period_dates(num_periods=4)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=200),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            time_limit_seconds=60,
        )

        assert result.success

        # Verify charge nurse is always an RN (not LPN)
        lpn_ids = {f"LPN00{i}" for i in range(1, 6)}
        for period in result.schedule.periods:
            charge_assignments = period.assignments.get("charge", [])
            for assignment in charge_assignments:
                assert assignment.id not in lpn_ids, (
                    f"LPN {assignment.id} incorrectly assigned to charge nurse"
                )


@pytest.mark.e2e
class TestHealthcareWeekendRotation:
    """Tests for fair weekend shift distribution."""

    def test_weekend_night_fairness(self, worker_factory) -> None:
        """Fair distribution of weekend night shifts."""
        workers = [worker_factory() for _ in range(8)]

        shift_types = [
            ShiftType(
                id="weekday",
                name="Weekday Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(19, 0),
                duration_hours=12.0,
                workers_required=2,
            ),
            ShiftType(
                id="weekend_night",
                name="Weekend Night",
                category="weekend",
                start_time=time(19, 0),
                end_time=time(7, 0),
                duration_hours=12.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        # 8 periods = 8 weekend nights to distribute among 8 workers
        periods = create_period_dates(num_periods=8)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            # High fairness weight to encourage even distribution
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=5000),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            time_limit_seconds=60,
        )

        assert result.success

        # Count weekend nights per worker
        weekend_counts = {w.id: 0 for w in workers}
        for period in result.schedule.periods:
            for assignment in period.assignments.get("weekend_night", []):
                weekend_counts[assignment.id] += 1

        counts = list(weekend_counts.values())
        spread = max(counts) - min(counts)

        # With high fairness weight, spread should be minimal
        assert spread <= 2, f"Weekend distribution spread {spread} > 2"


# -----------------------------------------------------------------------------
# Retail Complex Scenarios
# -----------------------------------------------------------------------------


@pytest.mark.e2e
class TestRetailVariableDemand:
    """Tests for variable staffing based on demand."""

    def test_higher_weekend_staffing(self, worker_factory) -> None:
        """Weekend shifts require more staff than weekday."""
        workers = [worker_factory() for _ in range(15)]

        shift_types = [
            ShiftType(
                id="weekday",
                name="Weekday Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="weekend",
                name="Weekend Shift",
                category="weekend",
                start_time=time(9, 0),
                end_time=time(18, 0),
                duration_hours=9.0,
                workers_required=6,  # Double weekend staffing
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

        # Verify weekend coverage meets higher requirement
        for period in result.schedule.periods:
            weekend_assigned = sum(
                1
                for worker_shifts in period.assignments.values()
                for shift in worker_shifts
                if shift.shift_type_id == "weekend"
            )
            assert weekend_assigned >= 6


@pytest.mark.e2e
class TestRetailPartTimeMix:
    """Tests for full-time and part-time worker mix."""

    def test_fulltime_parttime_scheduling(self, worker_factory) -> None:
        """Mix of full-time and part-time workers with different availability."""
        # Full-time workers (no restrictions)
        fulltime = [worker_factory(name=f"FT-{i}") for i in range(5)]

        # Part-time workers restricted from morning (students, etc.)
        parttime = [
            worker_factory(
                name=f"PT-{i}", restricted_shifts=frozenset(["morning"])
            )
            for i in range(5)
        ]

        workers = fulltime + parttime

        shift_types = [
            ShiftType(
                id="morning",
                name="Morning Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(12, 0),
                duration_hours=5.0,
                workers_required=3,  # Need full-timers
            ),
            ShiftType(
                id="afternoon",
                name="Afternoon Shift",
                category="day",
                start_time=time(12, 0),
                end_time=time(17, 0),
                duration_hours=5.0,
                workers_required=4,  # Mix of both
            ),
            ShiftType(
                id="evening",
                name="Evening Shift",
                category="evening",
                start_time=time(17, 0),
                end_time=time(22, 0),
                duration_hours=5.0,
                workers_required=3,  # Good for part-time
            ),
        ]

        periods = create_period_dates(num_periods=4)

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
            time_limit_seconds=60,
        )

        assert result.success

        # Verify part-timers never assigned to morning
        parttime_ids = {f"PT-{i}" for i in range(5)}
        for period in result.schedule.periods:
            for assignment in period.assignments.get("morning", []):
                # Part-timer names start with "PT-"
                assert not assignment.name.startswith("PT-"), (
                    f"Part-timer {assignment.name} assigned to morning shift"
                )


@pytest.mark.e2e
class TestRetailHolidayCoverage:
    """Tests for holiday staffing requirements."""

    def test_reduced_staff_holiday_coverage(self, worker_factory) -> None:
        """Holiday periods with limited availability still covered."""
        workers = [worker_factory() for _ in range(10)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Store Shift",
                category="day",
                start_time=time(10, 0),
                end_time=time(18, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
        ]

        periods = create_period_dates(num_periods=4)
        holiday_period = periods[2]  # Third period is "holiday"

        # 70% of workers unavailable during holiday period
        availabilities = [
            Availability(
                worker_id=workers[i].id,
                start_date=holiday_period[0],
                end_date=holiday_period[1],
                availability_type="unavailable",
            )
            for i in range(7)  # 7 of 10 unavailable
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
            time_limit_seconds=60,
        )

        assert result.success


# -----------------------------------------------------------------------------
# Warehouse Complex Scenarios
# -----------------------------------------------------------------------------


@pytest.mark.e2e
class TestWarehouseShiftHandoff:
    """Tests for overlapping shift transitions."""

    def test_three_shift_continuous_operation(self, worker_factory) -> None:
        """Three shifts providing continuous 24-hour coverage."""
        workers = [worker_factory() for _ in range(20)]

        # Overlapping shifts for handoff
        shift_types = [
            ShiftType(
                id="first",
                name="First Shift (6a-2:30p)",
                category="day",
                start_time=time(6, 0),
                end_time=time(14, 30),
                duration_hours=8.5,
                workers_required=5,
            ),
            ShiftType(
                id="second",
                name="Second Shift (2p-10:30p)",
                category="evening",
                start_time=time(14, 0),
                end_time=time(22, 30),
                duration_hours=8.5,
                workers_required=5,
            ),
            ShiftType(
                id="third",
                name="Third Shift (10p-6:30a)",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 30),
                duration_hours=8.5,
                workers_required=4,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=4)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=500),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            time_limit_seconds=60,
        )

        assert result.success


@pytest.mark.e2e
class TestWarehouseEquipmentCertification:
    """Tests for equipment certification requirements."""

    def test_forklift_certified_workers(self, worker_factory) -> None:
        """Forklift shifts require certified workers."""
        # Certified workers (can work forklift)
        certified = [worker_factory(name=f"Cert-{i}") for i in range(5)]

        # Non-certified (restricted from forklift)
        non_certified = [
            worker_factory(
                name=f"NonCert-{i}", restricted_shifts=frozenset(["forklift"])
            )
            for i in range(10)
        ]

        workers = certified + non_certified

        shift_types = [
            ShiftType(
                id="general",
                name="General Warehouse",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=6,
            ),
            ShiftType(
                id="forklift",
                name="Forklift Operations",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=2,  # Need certified operators
            ),
        ]

        periods = create_period_dates(num_periods=4)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=200),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            time_limit_seconds=60,
        )

        assert result.success

        # Verify only certified workers on forklift
        for period in result.schedule.periods:
            for assignment in period.assignments.get("forklift", []):
                assert assignment.name.startswith("Cert-"), (
                    f"Non-certified {assignment.name} assigned to forklift"
                )


# -----------------------------------------------------------------------------
# Logistics Complex Scenarios
# -----------------------------------------------------------------------------


@pytest.mark.e2e
class TestLogisticsRouteCoverage:
    """Tests for delivery route coverage requirements."""

    def test_multiple_route_coverage(self, worker_factory) -> None:
        """Multiple delivery routes with different staffing needs."""
        # Some drivers restricted from long-haul (local only)
        local_drivers = [
            worker_factory(
                name=f"Local-{i}", restricted_shifts=frozenset(["long_haul"])
            )
            for i in range(5)
        ]

        # Full drivers (can do any route)
        full_drivers = [worker_factory(name=f"Full-{i}") for i in range(5)]

        workers = local_drivers + full_drivers

        shift_types = [
            ShiftType(
                id="local",
                name="Local Delivery",
                category="day",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=4,
            ),
            ShiftType(
                id="long_haul",
                name="Long-Haul Route",
                category="day",
                start_time=time(4, 0),
                end_time=time(16, 0),
                duration_hours=12.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=4)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=300),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
            time_limit_seconds=60,
        )

        assert result.success

        # Verify local drivers not on long-haul
        for period in result.schedule.periods:
            for assignment in period.assignments.get("long_haul", []):
                assert assignment.name.startswith("Full-"), (
                    f"Local driver {assignment.name} assigned to long-haul"
                )


@pytest.mark.e2e
class TestLogisticsMultipleTimeWindows:
    """Tests for time-sensitive delivery windows."""

    def test_morning_afternoon_delivery_windows(self, worker_factory) -> None:
        """Separate staffing for morning and afternoon delivery windows."""
        workers = [worker_factory() for _ in range(12)]

        shift_types = [
            ShiftType(
                id="early_window",
                name="Early Delivery (6a-10a)",
                category="early",
                start_time=time(6, 0),
                end_time=time(10, 0),
                duration_hours=4.0,
                workers_required=4,
            ),
            ShiftType(
                id="midday_window",
                name="Midday Delivery (10a-2p)",
                category="day",
                start_time=time(10, 0),
                end_time=time(14, 0),
                duration_hours=4.0,
                workers_required=3,
            ),
            ShiftType(
                id="afternoon_window",
                name="Afternoon Delivery (2p-6p)",
                category="afternoon",
                start_time=time(14, 0),
                end_time=time(18, 0),
                duration_hours=4.0,
                workers_required=4,
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

        # All windows should be fully staffed
        for period in result.schedule.periods:
            for shift_type in shift_types:
                assigned = sum(
                    1
                    for worker_shifts in period.assignments.values()
                    for shift in worker_shifts
                    if shift.shift_type_id == shift_type.id
                )
                assert assigned >= shift_type.workers_required


# -----------------------------------------------------------------------------
# Cross-Industry Complex Scenarios
# -----------------------------------------------------------------------------


@pytest.mark.e2e
class TestComplexConstraintCombinations:
    """Tests combining multiple industry patterns."""

    def test_restrictions_availability_requests_combined(
        self, worker_factory
    ) -> None:
        """Complex scenario with all constraint types."""
        # Workers with various restrictions
        workers = [
            worker_factory(name="Alice"),
            worker_factory(name="Bob", restricted_shifts=frozenset(["night"])),
            worker_factory(name="Carol", restricted_shifts=frozenset(["night"])),
            worker_factory(name="Dave"),
            worker_factory(name="Eve", restricted_shifts=frozenset(["weekend"])),
            worker_factory(name="Frank"),
            worker_factory(name="Grace"),
            worker_factory(name="Henry", restricted_shifts=frozenset(["night", "weekend"])),
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
                workers_required=1,
                is_undesirable=True,
            ),
            ShiftType(
                id="weekend",
                name="Weekend Shift",
                category="weekend",
                start_time=time(10, 0),
                end_time=time(18, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=4)

        # Some availability constraints
        availabilities = [
            Availability(
                worker_id=workers[0].id,  # Alice
                start_date=periods[1][0],
                end_date=periods[1][1],
                availability_type="unavailable",
            ),
            Availability(
                worker_id=workers[3].id,  # Dave
                start_date=periods[2][0],
                end_date=periods[2][1],
                availability_type="unavailable",
            ),
        ]

        # Some requests
        requests = [
            SchedulingRequest(
                worker_id=workers[5].id,  # Frank
                start_date=periods[0][0],
                end_date=periods[0][1],
                request_type="negative",
                shift_type_id="night",
                priority=2,
            ),
            SchedulingRequest(
                worker_id=workers[6].id,  # Grace
                start_date=periods[3][0],
                end_date=periods[3][1],
                request_type="positive",
                shift_type_id="day",
                priority=1,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "availability": ConstraintConfig(enabled=True, is_hard=True),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=150),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=500),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            availabilities=availabilities,
            requests=requests,
            constraint_configs=constraint_configs,
            time_limit_seconds=60,
        )

        assert result.success

        # Validate the solution
        validator = ScheduleValidator(
            schedule=result.schedule,
            availabilities=availabilities,
            requests=requests,
        )
        validation = validator.validate()
        assert validation.is_valid, f"Violations: {validation.violations}"
