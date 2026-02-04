"""Shift models for shift-solver."""

from dataclasses import dataclass, field
from datetime import date, time
from typing import Any


@dataclass(frozen=True, eq=False)
class ShiftType:
    """
    Defines a type of shift that can be scheduled.

    ShiftTypes are templates that define the characteristics of shifts.
    Actual shift instances are created for specific dates/periods.

    Attributes:
        id: Unique identifier (e.g., "day_shift", "night", "weekend")
        name: Human-readable display name
        category: Grouping category (e.g., "day", "night", "weekend")
        start_time: Default start time for this shift type
        end_time: Default end time for this shift type
        duration_hours: Duration in hours
        is_undesirable: Whether this shift is considered undesirable for fairness
        workers_required: Default number of workers needed per period
        required_attributes: Worker attributes required to work this shift
    """

    id: str
    name: str
    category: str
    start_time: time
    end_time: time
    duration_hours: float
    is_undesirable: bool = False
    workers_required: int = 1
    required_attributes: dict[str, Any] = field(
        default_factory=dict, compare=False, hash=False
    )
    applicable_days: frozenset[int] | None = None  # 0=Mon, 6=Sun; None=all days

    def __post_init__(self) -> None:
        """Validate shift type fields after initialization."""
        if not self.id:
            raise ValueError("id cannot be empty")
        if self.duration_hours <= 0:
            raise ValueError("duration_hours must be positive")
        if self.workers_required < 1:
            raise ValueError("workers_required must be at least 1")
        if self.applicable_days is not None:
            invalid = {d for d in self.applicable_days if d < 0 or d > 6}
            if invalid:
                raise ValueError(f"applicable_days must be 0-6, got: {invalid}")

    def __eq__(self, other: object) -> bool:
        """ShiftTypes are equal if all fields except required_attributes are equal."""
        if not isinstance(other, ShiftType):
            return NotImplemented
        return (
            self.id == other.id
            and self.name == other.name
            and self.category == other.category
            and self.start_time == other.start_time
            and self.end_time == other.end_time
            and self.duration_hours == other.duration_hours
            and self.is_undesirable == other.is_undesirable
            and self.workers_required == other.workers_required
            and self.applicable_days == other.applicable_days
        )

    def __hash__(self) -> int:
        """Hash based on immutable fields only."""
        return hash(
            (
                self.id,
                self.name,
                self.category,
                self.start_time,
                self.end_time,
                self.duration_hours,
                self.is_undesirable,
                self.workers_required,
                self.applicable_days,
            )
        )

    def is_applicable_on(self, day_of_week: int) -> bool:
        """
        Check if this shift applies on a given day of the week.

        Args:
            day_of_week: Day of week where 0=Monday, 6=Sunday

        Returns:
            True if shift applies on this day, False otherwise
        """
        return self.applicable_days is None or day_of_week in self.applicable_days


@dataclass
class ShiftInstance:
    """
    A concrete shift occurrence at a specific date.

    ShiftInstance represents an actual shift that needs to be filled
    or has been assigned to a worker.

    Attributes:
        shift_type_id: Reference to the ShiftType this instance is based on
        period_index: Which scheduling period this belongs to (0-indexed)
        date: The specific date of this shift
        worker_id: ID of assigned worker (None if unassigned)
        override_start_time: Override the default start time
        override_end_time: Override the default end time
    """

    shift_type_id: str
    period_index: int
    date: date
    worker_id: str | None = None
    override_start_time: time | None = None
    override_end_time: time | None = None

    def __post_init__(self) -> None:
        """Validate shift instance fields after initialization."""
        if self.period_index < 0:
            raise ValueError("period_index cannot be negative")

    @property
    def is_assigned(self) -> bool:
        """Check if this shift instance has a worker assigned."""
        return self.worker_id is not None
