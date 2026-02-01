"""Tests for the ShiftType and ShiftInstance models."""

from datetime import date, time

import pytest

from shift_solver.models.shift import ShiftInstance, ShiftType


class TestShiftType:
    """Tests for ShiftType dataclass."""

    def test_create_shift_type_minimal(self) -> None:
        """ShiftType can be created with required fields."""
        shift = ShiftType(
            id="day_shift",
            name="Day Shift",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
        )

        assert shift.id == "day_shift"
        assert shift.name == "Day Shift"
        assert shift.category == "day"
        assert shift.start_time == time(7, 0)
        assert shift.end_time == time(15, 0)
        assert shift.duration_hours == 8.0
        assert shift.is_undesirable is False
        assert shift.workers_required == 1
        assert shift.required_attributes == {}

    def test_create_shift_type_with_all_fields(self) -> None:
        """ShiftType can be created with all optional fields."""
        shift = ShiftType(
            id="night_shift",
            name="Night Shift",
            category="night",
            start_time=time(23, 0),
            end_time=time(7, 0),
            duration_hours=8.0,
            is_undesirable=True,
            workers_required=2,
            required_attributes={"certification": "night_certified"},
        )

        assert shift.id == "night_shift"
        assert shift.is_undesirable is True
        assert shift.workers_required == 2
        assert shift.required_attributes["certification"] == "night_certified"

    def test_shift_type_is_frozen(self) -> None:
        """ShiftType should be immutable."""
        shift = ShiftType(
            id="test",
            name="Test",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
        )

        with pytest.raises(AttributeError):
            shift.name = "Changed"  # type: ignore[misc]

    def test_shift_type_equality(self) -> None:
        """Two shift types with same fields should be equal."""
        shift1 = ShiftType(
            id="test",
            name="Test",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
        )
        shift2 = ShiftType(
            id="test",
            name="Test",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
        )

        assert shift1 == shift2

    def test_shift_type_hash(self) -> None:
        """ShiftType should be hashable."""
        shift1 = ShiftType(
            id="day",
            name="Day",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
        )
        shift2 = ShiftType(
            id="night",
            name="Night",
            category="night",
            start_time=time(23, 0),
            end_time=time(7, 0),
            duration_hours=8.0,
        )

        shift_set = {shift1, shift2}
        assert len(shift_set) == 2


class TestShiftTypeValidation:
    """Tests for ShiftType validation."""

    def test_shift_type_id_cannot_be_empty(self) -> None:
        """ShiftType id should not be empty."""
        with pytest.raises(ValueError, match="id cannot be empty"):
            ShiftType(
                id="",
                name="Test",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
            )

    def test_shift_type_duration_must_be_positive(self) -> None:
        """ShiftType duration_hours must be positive."""
        with pytest.raises(ValueError, match="duration_hours must be positive"):
            ShiftType(
                id="test",
                name="Test",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=0,
            )

    def test_shift_type_workers_required_must_be_positive(self) -> None:
        """ShiftType workers_required must be at least 1."""
        with pytest.raises(ValueError, match="workers_required must be at least 1"):
            ShiftType(
                id="test",
                name="Test",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=0,
            )


class TestShiftInstance:
    """Tests for ShiftInstance dataclass."""

    def test_create_shift_instance_minimal(self) -> None:
        """ShiftInstance can be created with required fields."""
        instance = ShiftInstance(
            shift_type_id="day_shift",
            period_index=0,
            date=date(2026, 1, 5),
        )

        assert instance.shift_type_id == "day_shift"
        assert instance.period_index == 0
        assert instance.date == date(2026, 1, 5)
        assert instance.worker_id is None
        assert instance.override_start_time is None
        assert instance.override_end_time is None

    def test_create_shift_instance_with_assignment(self) -> None:
        """ShiftInstance can be created with a worker assignment."""
        instance = ShiftInstance(
            shift_type_id="day_shift",
            period_index=0,
            date=date(2026, 1, 5),
            worker_id="W001",
        )

        assert instance.worker_id == "W001"

    def test_shift_instance_is_assigned(self) -> None:
        """Check if a shift instance has a worker assigned."""
        unassigned = ShiftInstance(
            shift_type_id="day_shift",
            period_index=0,
            date=date(2026, 1, 5),
        )
        assigned = ShiftInstance(
            shift_type_id="day_shift",
            period_index=0,
            date=date(2026, 1, 5),
            worker_id="W001",
        )

        assert not unassigned.is_assigned
        assert assigned.is_assigned

    def test_shift_instance_with_time_override(self) -> None:
        """ShiftInstance can override default shift times."""
        instance = ShiftInstance(
            shift_type_id="day_shift",
            period_index=0,
            date=date(2026, 1, 5),
            override_start_time=time(8, 0),
            override_end_time=time(16, 0),
        )

        assert instance.override_start_time == time(8, 0)
        assert instance.override_end_time == time(16, 0)


class TestShiftInstanceValidation:
    """Tests for ShiftInstance validation."""

    def test_period_index_cannot_be_negative(self) -> None:
        """ShiftInstance period_index must be non-negative."""
        with pytest.raises(ValueError, match="period_index cannot be negative"):
            ShiftInstance(
                shift_type_id="day_shift",
                period_index=-1,
                date=date(2026, 1, 5),
            )
