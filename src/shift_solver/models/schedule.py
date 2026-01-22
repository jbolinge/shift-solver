"""Schedule models for shift-solver."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from shift_solver.models.shift import ShiftInstance, ShiftType
from shift_solver.models.worker import Worker


@dataclass
class PeriodAssignment:
    """
    Assignments for one scheduling period (day, week, month).

    A period represents a discrete time unit in the schedule.
    It contains all shift assignments for workers during that period.

    Attributes:
        period_index: 0-based index of this period in the schedule
        period_start: Start date of the period (inclusive)
        period_end: End date of the period (inclusive)
        assignments: Dict mapping worker_id to list of assigned shifts
    """

    period_index: int
    period_start: date
    period_end: date
    assignments: dict[str, list[ShiftInstance]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate period assignment fields."""
        if self.period_end < self.period_start:
            raise ValueError("period_end must be >= period_start")

    def get_worker_shifts(self, worker_id: str) -> list[ShiftInstance]:
        """
        Get all shifts assigned to a worker in this period.

        Args:
            worker_id: The ID of the worker

        Returns:
            List of shift instances assigned to the worker (empty if none)
        """
        return self.assignments.get(worker_id, [])

    def get_shifts_by_type(self, shift_type_id: str) -> list[ShiftInstance]:
        """
        Get all shifts of a specific type in this period.

        Args:
            shift_type_id: The ID of the shift type

        Returns:
            List of shift instances of the given type
        """
        result = []
        for shifts in self.assignments.values():
            for shift in shifts:
                if shift.shift_type_id == shift_type_id:
                    result.append(shift)
        return result


@dataclass
class Schedule:
    """
    Complete schedule for an entire scheduling horizon.

    A schedule contains all period assignments, worker definitions,
    shift type definitions, and computed statistics.

    Attributes:
        schedule_id: Unique identifier for this schedule
        start_date: First day of the schedule (inclusive)
        end_date: Last day of the schedule (inclusive)
        period_type: Type of periods ("day", "week", "month")
        periods: List of PeriodAssignment objects
        workers: List of workers in this schedule
        shift_types: List of shift types in this schedule
        statistics: Computed metrics per worker (assignments, fairness, etc.)
    """

    schedule_id: str
    start_date: date
    end_date: date
    period_type: str
    periods: list[PeriodAssignment]
    workers: list[Worker]
    shift_types: list[ShiftType]
    statistics: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate schedule fields."""
        if not self.schedule_id:
            raise ValueError("schedule_id cannot be empty")
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be > start_date")

    @property
    def num_periods(self) -> int:
        """Get the number of periods in this schedule."""
        return len(self.periods)

    def get_worker_by_id(self, worker_id: str) -> Worker | None:
        """
        Get a worker by their ID.

        Args:
            worker_id: The ID of the worker to find

        Returns:
            The Worker object, or None if not found
        """
        for worker in self.workers:
            if worker.id == worker_id:
                return worker
        return None

    def get_shift_type_by_id(self, shift_type_id: str) -> ShiftType | None:
        """
        Get a shift type by its ID.

        Args:
            shift_type_id: The ID of the shift type to find

        Returns:
            The ShiftType object, or None if not found
        """
        for shift_type in self.shift_types:
            if shift_type.id == shift_type_id:
                return shift_type
        return None
