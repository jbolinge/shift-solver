"""Data models for schedule input data."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

AVAILABILITY_TYPES = ("unavailable", "preferred", "required")
REQUEST_TYPES = ("positive", "negative")


@dataclass
class Availability:
    """
    Worker availability or unavailability entry.

    Used to mark periods when a worker is unavailable (vacation, leave)
    or has preferences about working certain shifts.

    Attributes:
        worker_id: ID of the worker
        start_date: Start of the availability period (inclusive)
        end_date: End of the availability period (inclusive)
        availability_type: Type of availability
            - "unavailable": Worker cannot work (vacation, leave)
            - "preferred": Worker prefers to work
            - "required": Worker must work (on-call, mandatory)
        shift_type_id: If set, applies only to this shift type.
            If None, applies to all shifts.
    """

    worker_id: str
    start_date: date
    end_date: date
    availability_type: Literal["unavailable", "preferred", "required"]
    shift_type_id: str | None = None

    def __post_init__(self) -> None:
        """Validate availability fields."""
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        if self.availability_type not in AVAILABILITY_TYPES:
            raise ValueError(
                f"availability_type must be one of {AVAILABILITY_TYPES}, "
                f"got '{self.availability_type}'"
            )

    @property
    def duration_days(self) -> int:
        """Get the duration of this availability period in days (inclusive)."""
        return (self.end_date - self.start_date).days + 1

    def contains_date(self, check_date: date) -> bool:
        """
        Check if a date falls within this availability period.

        Args:
            check_date: The date to check

        Returns:
            True if the date is within [start_date, end_date]
        """
        return self.start_date <= check_date <= self.end_date


@dataclass
class SchedulingRequest:
    """
    Worker scheduling request or preference.

    Used to express worker preferences for or against working certain
    shifts during specific time periods.

    Attributes:
        worker_id: ID of the worker making the request
        start_date: Start of the request period (inclusive)
        end_date: End of the request period (inclusive)
        request_type: Type of request
            - "positive": Worker wants to work this shift
            - "negative": Worker wants to avoid this shift
        shift_type_id: The shift type this request applies to
        priority: Priority level (1 = normal, higher = more important)
    """

    worker_id: str
    start_date: date
    end_date: date
    request_type: Literal["positive", "negative"]
    shift_type_id: str
    priority: int = 1

    def __post_init__(self) -> None:
        """Validate scheduling request fields."""
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        if self.request_type not in REQUEST_TYPES:
            raise ValueError(
                f"request_type must be {REQUEST_TYPES}, got '{self.request_type}'"
            )
        if self.priority < 1:
            raise ValueError("priority must be >= 1")

    @property
    def is_positive(self) -> bool:
        """Check if this is a positive (prefer to work) request."""
        return self.request_type == "positive"

    def contains_date(self, check_date: date) -> bool:
        """
        Check if a date falls within this request period.

        Args:
            check_date: The date to check

        Returns:
            True if the date is within [start_date, end_date]
        """
        return self.start_date <= check_date <= self.end_date
