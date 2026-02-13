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


@dataclass
class ShiftFrequencyRequirement:
    """
    Per-worker shift frequency requirement.

    Specifies that a worker must work at least one of a set of shift types
    within every N periods. Used for constraints like "Worker X must work
    at least one of [mvsc_day, mvsc_night] within every 4 weeks."

    Attributes:
        worker_id: ID of the worker this requirement applies to
        shift_types: Set of shift type IDs the worker must work at least one of
        max_periods_between: Maximum number of periods between assignments
            (e.g., 4 means must work at least once every 4 periods)
    """

    worker_id: str
    shift_types: frozenset[str]
    max_periods_between: int

    def __post_init__(self) -> None:
        """Validate shift frequency requirement fields."""
        if self.max_periods_between <= 0:
            raise ValueError("max_periods_between must be > 0")
        if not self.shift_types:
            raise ValueError("shift_types must not be empty")


TRIGGER_TYPES = ("shift_type", "category", "unavailability")
DIRECTIONS = ("after", "before")
PREFERRED_TYPES = ("shift_type", "category")


@dataclass(frozen=True)
class ShiftOrderPreference:
    """
    Preference for shift transitions between adjacent periods.

    Specifies that when a trigger condition is met (worker works a shift type,
    a category, or is unavailable), a preferred shift/category should be
    assigned in the adjacent period.

    Attributes:
        rule_id: Unique identifier for this rule
        trigger_type: What triggers the preference
            - "shift_type": worker works a specific shift type
            - "category": worker works any shift in a category
            - "unavailability": worker is unavailable
        trigger_value: The shift type ID or category name that triggers.
            None only for unavailability trigger.
        direction: Whether the preferred shift is after or before the trigger
            - "after": preferred at N+1 when trigger at N
            - "before": preferred at N when trigger at N+1
        preferred_type: Type of preferred assignment
            - "shift_type": prefer a specific shift type
            - "category": prefer any shift in a category
        preferred_value: The shift type ID or category name preferred
        priority: Multiplier for penalty weight (higher = more important)
        worker_ids: If set, only apply to these workers. None = all workers.
    """

    rule_id: str
    trigger_type: Literal["shift_type", "category", "unavailability"]
    trigger_value: str | None
    direction: Literal["after", "before"]
    preferred_type: Literal["shift_type", "category"]
    preferred_value: str
    priority: int = 1
    worker_ids: frozenset[str] | None = None

    def __post_init__(self) -> None:
        """Validate shift order preference fields."""
        if not self.rule_id:
            raise ValueError("rule_id must not be empty")
        if self.trigger_type not in TRIGGER_TYPES:
            raise ValueError(
                f"trigger_type must be one of {TRIGGER_TYPES}, "
                f"got '{self.trigger_type}'"
            )
        if self.trigger_type != "unavailability" and self.trigger_value is None:
            raise ValueError(
                f"trigger_value is required for trigger_type '{self.trigger_type}'"
            )
        if self.direction not in DIRECTIONS:
            raise ValueError(
                f"direction must be one of {DIRECTIONS}, got '{self.direction}'"
            )
        if self.preferred_type not in PREFERRED_TYPES:
            raise ValueError(
                f"preferred_type must be one of {PREFERRED_TYPES}, "
                f"got '{self.preferred_type}'"
            )
        if self.priority < 1:
            raise ValueError("priority must be >= 1")
