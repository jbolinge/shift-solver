"""Tests for the Schedule and PeriodAssignment models."""

from datetime import date, time

import pytest

from shift_solver.models.schedule import PeriodAssignment, Schedule
from shift_solver.models.shift import ShiftInstance, ShiftType
from shift_solver.models.worker import Worker


class TestPeriodAssignment:
    """Tests for PeriodAssignment dataclass."""

    def test_create_period_assignment(self) -> None:
        """PeriodAssignment can be created with required fields."""
        period = PeriodAssignment(
            period_index=0,
            period_start=date(2026, 1, 5),
            period_end=date(2026, 1, 11),
        )

        assert period.period_index == 0
        assert period.period_start == date(2026, 1, 5)
        assert period.period_end == date(2026, 1, 11)
        assert period.assignments == {}

    def test_period_assignment_with_assignments(self) -> None:
        """PeriodAssignment can include worker assignments."""
        shift1 = ShiftInstance(
            shift_type_id="day_shift",
            period_index=0,
            date=date(2026, 1, 5),
            worker_id="W001",
        )
        shift2 = ShiftInstance(
            shift_type_id="night_shift",
            period_index=0,
            date=date(2026, 1, 5),
            worker_id="W002",
        )

        period = PeriodAssignment(
            period_index=0,
            period_start=date(2026, 1, 5),
            period_end=date(2026, 1, 11),
            assignments={"W001": [shift1], "W002": [shift2]},
        )

        assert len(period.assignments) == 2
        assert "W001" in period.assignments
        assert period.assignments["W001"][0].shift_type_id == "day_shift"

    def test_get_worker_shifts(self) -> None:
        """Get all shifts for a specific worker in this period."""
        shift1 = ShiftInstance(
            shift_type_id="day_shift",
            period_index=0,
            date=date(2026, 1, 5),
            worker_id="W001",
        )

        period = PeriodAssignment(
            period_index=0,
            period_start=date(2026, 1, 5),
            period_end=date(2026, 1, 11),
            assignments={"W001": [shift1]},
        )

        shifts = period.get_worker_shifts("W001")
        assert len(shifts) == 1
        assert shifts[0].shift_type_id == "day_shift"

        # Non-existent worker returns empty list
        assert period.get_worker_shifts("W999") == []

    def test_get_shifts_by_type(self) -> None:
        """Get all shifts of a specific type in this period."""
        shift1 = ShiftInstance(
            shift_type_id="day_shift",
            period_index=0,
            date=date(2026, 1, 5),
            worker_id="W001",
        )
        shift2 = ShiftInstance(
            shift_type_id="day_shift",
            period_index=0,
            date=date(2026, 1, 6),
            worker_id="W002",
        )
        shift3 = ShiftInstance(
            shift_type_id="night_shift",
            period_index=0,
            date=date(2026, 1, 5),
            worker_id="W003",
        )

        period = PeriodAssignment(
            period_index=0,
            period_start=date(2026, 1, 5),
            period_end=date(2026, 1, 11),
            assignments={
                "W001": [shift1],
                "W002": [shift2],
                "W003": [shift3],
            },
        )

        day_shifts = period.get_shifts_by_type("day_shift")
        assert len(day_shifts) == 2

        night_shifts = period.get_shifts_by_type("night_shift")
        assert len(night_shifts) == 1

        # Non-existent shift type returns empty list
        assert period.get_shifts_by_type("unknown") == []


class TestPeriodAssignmentValidation:
    """Tests for PeriodAssignment validation."""

    def test_period_end_must_be_after_start(self) -> None:
        """Period end date must be after or equal to start date."""
        with pytest.raises(ValueError, match="period_end must be >= period_start"):
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 11),
                period_end=date(2026, 1, 5),
            )


class TestSchedule:
    """Tests for Schedule dataclass."""

    @pytest.fixture
    def sample_workers(self) -> list[Worker]:
        """Create sample workers for testing."""
        return [
            Worker(id="W001", name="Alice"),
            Worker(id="W002", name="Bob"),
        ]

    @pytest.fixture
    def sample_shift_types(self) -> list[ShiftType]:
        """Create sample shift types for testing."""
        return [
            ShiftType(
                id="day_shift",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
            ),
            ShiftType(
                id="night_shift",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                is_undesirable=True,
            ),
        ]

    def test_create_schedule_minimal(
        self, sample_workers: list[Worker], sample_shift_types: list[ShiftType]
    ) -> None:
        """Schedule can be created with required fields."""
        schedule = Schedule(
            schedule_id="SCH-001",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            period_type="week",
            periods=[],
            workers=sample_workers,
            shift_types=sample_shift_types,
        )

        assert schedule.schedule_id == "SCH-001"
        assert schedule.start_date == date(2026, 1, 1)
        assert schedule.end_date == date(2026, 3, 31)
        assert schedule.period_type == "week"
        assert len(schedule.workers) == 2
        assert len(schedule.shift_types) == 2
        assert schedule.statistics == {}

    def test_schedule_with_periods(
        self, sample_workers: list[Worker], sample_shift_types: list[ShiftType]
    ) -> None:
        """Schedule can include period assignments."""
        period1 = PeriodAssignment(
            period_index=0,
            period_start=date(2026, 1, 5),
            period_end=date(2026, 1, 11),
        )
        period2 = PeriodAssignment(
            period_index=1,
            period_start=date(2026, 1, 12),
            period_end=date(2026, 1, 18),
        )

        schedule = Schedule(
            schedule_id="SCH-001",
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 18),
            period_type="week",
            periods=[period1, period2],
            workers=sample_workers,
            shift_types=sample_shift_types,
        )

        assert len(schedule.periods) == 2
        assert schedule.periods[0].period_index == 0
        assert schedule.periods[1].period_index == 1

    def test_get_worker_by_id(
        self, sample_workers: list[Worker], sample_shift_types: list[ShiftType]
    ) -> None:
        """Get a worker by their ID."""
        schedule = Schedule(
            schedule_id="SCH-001",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            period_type="week",
            periods=[],
            workers=sample_workers,
            shift_types=sample_shift_types,
        )

        worker = schedule.get_worker_by_id("W001")
        assert worker is not None
        assert worker.name == "Alice"

        # Non-existent worker returns None
        assert schedule.get_worker_by_id("W999") is None

    def test_get_shift_type_by_id(
        self, sample_workers: list[Worker], sample_shift_types: list[ShiftType]
    ) -> None:
        """Get a shift type by its ID."""
        schedule = Schedule(
            schedule_id="SCH-001",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            period_type="week",
            periods=[],
            workers=sample_workers,
            shift_types=sample_shift_types,
        )

        shift_type = schedule.get_shift_type_by_id("day_shift")
        assert shift_type is not None
        assert shift_type.name == "Day Shift"

        # Non-existent shift type returns None
        assert schedule.get_shift_type_by_id("unknown") is None

    def test_num_periods(
        self, sample_workers: list[Worker], sample_shift_types: list[ShiftType]
    ) -> None:
        """Get the number of periods in the schedule."""
        from datetime import timedelta

        base_date = date(2026, 1, 5)
        periods = [
            PeriodAssignment(
                period_index=i,
                period_start=base_date + timedelta(days=i * 7),
                period_end=base_date + timedelta(days=i * 7 + 6),
            )
            for i in range(4)
        ]

        schedule = Schedule(
            schedule_id="SCH-001",
            start_date=date(2026, 1, 5),
            end_date=date(2026, 2, 1),
            period_type="week",
            periods=periods,
            workers=sample_workers,
            shift_types=sample_shift_types,
        )

        assert schedule.num_periods == 4


class TestScheduleValidation:
    """Tests for Schedule validation."""

    def test_schedule_end_must_be_after_start(self) -> None:
        """Schedule end date must be after start date."""
        with pytest.raises(ValueError, match="end_date must be > start_date"):
            Schedule(
                schedule_id="SCH-001",
                start_date=date(2026, 3, 31),
                end_date=date(2026, 1, 1),
                period_type="week",
                periods=[],
                workers=[],
                shift_types=[],
            )

    def test_schedule_id_cannot_be_empty(self) -> None:
        """Schedule ID cannot be empty."""
        with pytest.raises(ValueError, match="schedule_id cannot be empty"):
            Schedule(
                schedule_id="",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 3, 31),
                period_type="week",
                periods=[],
                workers=[],
                shift_types=[],
            )
