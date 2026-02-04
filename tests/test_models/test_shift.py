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


class TestShiftTypeApplicableDays:
    """Tests for ShiftType applicable_days field."""

    def test_applicable_days_default_is_none(self) -> None:
        """ShiftType applicable_days defaults to None (all days)."""
        shift = ShiftType(
            id="test",
            name="Test",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
        )
        assert shift.applicable_days is None

    def test_applicable_days_weekdays(self) -> None:
        """ShiftType can be created with weekday-only applicable_days."""
        weekdays = frozenset([0, 1, 2, 3, 4])  # Mon-Fri
        shift = ShiftType(
            id="weekday",
            name="Weekday Shift",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            applicable_days=weekdays,
        )
        assert shift.applicable_days == weekdays

    def test_applicable_days_weekends(self) -> None:
        """ShiftType can be created with weekend-only applicable_days."""
        weekend = frozenset([5, 6])  # Sat-Sun
        shift = ShiftType(
            id="weekend",
            name="Weekend Shift",
            category="weekend",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            applicable_days=weekend,
        )
        assert shift.applicable_days == weekend

    def test_applicable_days_validates_range(self) -> None:
        """ShiftType rejects applicable_days outside 0-6."""
        with pytest.raises(ValueError, match="applicable_days must be 0-6"):
            ShiftType(
                id="test",
                name="Test",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                applicable_days=frozenset([7]),  # Invalid: 7 is out of range
            )

    def test_applicable_days_validates_negative(self) -> None:
        """ShiftType rejects negative applicable_days values."""
        with pytest.raises(ValueError, match="applicable_days must be 0-6"):
            ShiftType(
                id="test",
                name="Test",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                applicable_days=frozenset([-1, 0, 1]),
            )

    def test_is_applicable_on_none_means_all_days(self) -> None:
        """is_applicable_on returns True for all days when applicable_days is None."""
        shift = ShiftType(
            id="test",
            name="Test",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            applicable_days=None,
        )
        for day in range(7):
            assert shift.is_applicable_on(day) is True

    def test_is_applicable_on_weekdays(self) -> None:
        """is_applicable_on correctly checks weekday shifts."""
        shift = ShiftType(
            id="weekday",
            name="Weekday",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            applicable_days=frozenset([0, 1, 2, 3, 4]),  # Mon-Fri
        )
        # Weekdays should be applicable
        assert shift.is_applicable_on(0) is True  # Monday
        assert shift.is_applicable_on(4) is True  # Friday
        # Weekends should not be applicable
        assert shift.is_applicable_on(5) is False  # Saturday
        assert shift.is_applicable_on(6) is False  # Sunday

    def test_is_applicable_on_weekends(self) -> None:
        """is_applicable_on correctly checks weekend shifts."""
        shift = ShiftType(
            id="weekend",
            name="Weekend",
            category="weekend",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            applicable_days=frozenset([5, 6]),  # Sat-Sun
        )
        # Weekdays should not be applicable
        assert shift.is_applicable_on(0) is False  # Monday
        assert shift.is_applicable_on(4) is False  # Friday
        # Weekends should be applicable
        assert shift.is_applicable_on(5) is True  # Saturday
        assert shift.is_applicable_on(6) is True  # Sunday

    def test_equality_includes_applicable_days(self) -> None:
        """Two ShiftTypes with different applicable_days are not equal."""
        shift1 = ShiftType(
            id="test",
            name="Test",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            applicable_days=frozenset([0, 1, 2, 3, 4]),
        )
        shift2 = ShiftType(
            id="test",
            name="Test",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            applicable_days=frozenset([5, 6]),
        )
        assert shift1 != shift2

    def test_equality_same_applicable_days(self) -> None:
        """Two ShiftTypes with same applicable_days are equal."""
        weekdays = frozenset([0, 1, 2, 3, 4])
        shift1 = ShiftType(
            id="test",
            name="Test",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            applicable_days=weekdays,
        )
        shift2 = ShiftType(
            id="test",
            name="Test",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            applicable_days=weekdays,
        )
        assert shift1 == shift2

    def test_hash_includes_applicable_days(self) -> None:
        """ShiftType hash includes applicable_days."""
        weekdays = frozenset([0, 1, 2, 3, 4])
        weekend = frozenset([5, 6])
        shift1 = ShiftType(
            id="test",
            name="Test",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            applicable_days=weekdays,
        )
        shift2 = ShiftType(
            id="test",
            name="Test",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            applicable_days=weekend,
        )
        # Different applicable_days should produce different hashes
        assert hash(shift1) != hash(shift2)


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
