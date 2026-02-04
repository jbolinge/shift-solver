"""Tests for Availability and SchedulingRequest models."""

from datetime import date

import pytest

from shift_solver.models.data_models import Availability, SchedulingRequest


class TestAvailability:
    """Tests for Availability dataclass."""

    def test_create_unavailable(self) -> None:
        """Create an unavailability entry (e.g., vacation)."""
        avail = Availability(
            worker_id="W001",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 14),
            availability_type="unavailable",
        )

        assert avail.worker_id == "W001"
        assert avail.start_date == date(2026, 7, 1)
        assert avail.end_date == date(2026, 7, 14)
        assert avail.availability_type == "unavailable"
        assert avail.shift_type_id is None  # All shifts

    def test_create_unavailable_for_specific_shift(self) -> None:
        """Create unavailability for a specific shift type."""
        avail = Availability(
            worker_id="W001",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 14),
            availability_type="unavailable",
            shift_type_id="night_shift",
        )

        assert avail.shift_type_id == "night_shift"

    def test_create_preferred_availability(self) -> None:
        """Create a preferred availability entry."""
        avail = Availability(
            worker_id="W001",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 7),
            availability_type="preferred",
            shift_type_id="day_shift",
        )

        assert avail.availability_type == "preferred"
        assert avail.shift_type_id == "day_shift"

    def test_duration_days(self) -> None:
        """Calculate duration in days."""
        avail = Availability(
            worker_id="W001",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 7),
            availability_type="unavailable",
        )

        assert avail.duration_days == 7  # Inclusive

    def test_contains_date(self) -> None:
        """Check if a date falls within the availability period."""
        avail = Availability(
            worker_id="W001",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 14),
            availability_type="unavailable",
        )

        assert avail.contains_date(date(2026, 7, 1))  # Start date
        assert avail.contains_date(date(2026, 7, 7))  # Middle
        assert avail.contains_date(date(2026, 7, 14))  # End date
        assert not avail.contains_date(date(2026, 6, 30))  # Before
        assert not avail.contains_date(date(2026, 7, 15))  # After


class TestAvailabilityValidation:
    """Tests for Availability validation."""

    def test_end_date_must_be_after_start(self) -> None:
        """End date must be >= start date."""
        with pytest.raises(ValueError, match="end_date must be >= start_date"):
            Availability(
                worker_id="W001",
                start_date=date(2026, 7, 14),
                end_date=date(2026, 7, 1),
                availability_type="unavailable",
            )

    def test_invalid_availability_type(self) -> None:
        """Availability type must be valid."""
        with pytest.raises(ValueError, match="availability_type must be one of"):
            Availability(
                worker_id="W001",
                start_date=date(2026, 7, 1),
                end_date=date(2026, 7, 14),
                availability_type="invalid",
            )


class TestSchedulingRequest:
    """Tests for SchedulingRequest dataclass."""

    def test_create_positive_request(self) -> None:
        """Create a positive scheduling request (prefer to work)."""
        request = SchedulingRequest(
            worker_id="W001",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 7),
            request_type="positive",
            shift_type_id="day_shift",
        )

        assert request.worker_id == "W001"
        assert request.request_type == "positive"
        assert request.shift_type_id == "day_shift"
        assert request.priority == 1  # Default priority

    def test_create_negative_request(self) -> None:
        """Create a negative scheduling request (prefer to avoid)."""
        request = SchedulingRequest(
            worker_id="W002",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 7),
            request_type="negative",
            shift_type_id="weekend",
        )

        assert request.request_type == "negative"
        assert request.shift_type_id == "weekend"

    def test_request_with_priority(self) -> None:
        """Create request with custom priority."""
        request = SchedulingRequest(
            worker_id="W001",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 7),
            request_type="positive",
            shift_type_id="day_shift",
            priority=3,
        )

        assert request.priority == 3

    def test_is_positive(self) -> None:
        """Check if request is positive."""
        positive = SchedulingRequest(
            worker_id="W001",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 7),
            request_type="positive",
            shift_type_id="day_shift",
        )
        negative = SchedulingRequest(
            worker_id="W001",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 7),
            request_type="negative",
            shift_type_id="night_shift",
        )

        assert positive.is_positive
        assert not negative.is_positive

    def test_contains_date(self) -> None:
        """Check if a date falls within the request period."""
        request = SchedulingRequest(
            worker_id="W001",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 7),
            request_type="positive",
            shift_type_id="day_shift",
        )

        assert request.contains_date(date(2026, 3, 1))
        assert request.contains_date(date(2026, 3, 5))
        assert not request.contains_date(date(2026, 2, 28))
        assert not request.contains_date(date(2026, 3, 8))


class TestSchedulingRequestValidation:
    """Tests for SchedulingRequest validation."""

    def test_end_date_must_be_after_start(self) -> None:
        """End date must be >= start date."""
        with pytest.raises(ValueError, match="end_date must be >= start_date"):
            SchedulingRequest(
                worker_id="W001",
                start_date=date(2026, 3, 7),
                end_date=date(2026, 3, 1),
                request_type="positive",
                shift_type_id="day_shift",
            )

    def test_invalid_request_type(self) -> None:
        """Request type must be 'positive' or 'negative'."""
        with pytest.raises(ValueError, match="request_type must be"):
            SchedulingRequest(
                worker_id="W001",
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 7),
                request_type="maybe",
                shift_type_id="day_shift",
            )

    def test_priority_must_be_positive(self) -> None:
        """Priority must be >= 1."""
        with pytest.raises(ValueError, match="priority must be >= 1"):
            SchedulingRequest(
                worker_id="W001",
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 7),
                request_type="positive",
                shift_type_id="day_shift",
                priority=0,
            )


class TestShiftFrequencyRequirement:
    """Tests for ShiftFrequencyRequirement dataclass."""

    def test_create_requirement(self) -> None:
        """Create a shift frequency requirement."""
        from shift_solver.models.data_models import ShiftFrequencyRequirement

        req = ShiftFrequencyRequirement(
            worker_id="W001",
            shift_types=frozenset(["mvsc_day", "mvsc_night"]),
            max_periods_between=4,
        )

        assert req.worker_id == "W001"
        assert req.shift_types == frozenset(["mvsc_day", "mvsc_night"])
        assert req.max_periods_between == 4

    def test_create_with_single_shift_type(self) -> None:
        """Create requirement with a single shift type."""
        from shift_solver.models.data_models import ShiftFrequencyRequirement

        req = ShiftFrequencyRequirement(
            worker_id="W002",
            shift_types=frozenset(["stf_day"]),
            max_periods_between=2,
        )

        assert len(req.shift_types) == 1
        assert "stf_day" in req.shift_types


class TestShiftFrequencyRequirementValidation:
    """Tests for ShiftFrequencyRequirement validation."""

    def test_max_periods_between_must_be_positive(self) -> None:
        """max_periods_between must be > 0."""
        from shift_solver.models.data_models import ShiftFrequencyRequirement

        with pytest.raises(ValueError, match="max_periods_between must be > 0"):
            ShiftFrequencyRequirement(
                worker_id="W001",
                shift_types=frozenset(["day_shift"]),
                max_periods_between=0,
            )

    def test_max_periods_between_negative(self) -> None:
        """max_periods_between must be > 0 (negative case)."""
        from shift_solver.models.data_models import ShiftFrequencyRequirement

        with pytest.raises(ValueError, match="max_periods_between must be > 0"):
            ShiftFrequencyRequirement(
                worker_id="W001",
                shift_types=frozenset(["day_shift"]),
                max_periods_between=-1,
            )

    def test_shift_types_must_not_be_empty(self) -> None:
        """shift_types must not be empty."""
        from shift_solver.models.data_models import ShiftFrequencyRequirement

        with pytest.raises(ValueError, match="shift_types must not be empty"):
            ShiftFrequencyRequirement(
                worker_id="W001",
                shift_types=frozenset(),
                max_periods_between=4,
            )
