"""Worker model for shift-solver."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, eq=False)
class Worker:
    """
    Represents a worker that can be scheduled for shifts.

    Workers are immutable (frozen) to ensure they can be used as dict keys
    and in sets, and to prevent accidental modification during scheduling.

    Attributes:
        id: Unique identifier for the worker (e.g., "W001", "EMP-123")
        name: Display name of the worker
        worker_type: Optional classification (e.g., "full_time", "part_time")
        restricted_shifts: Set of shift type IDs this worker cannot work
        preferred_shifts: Set of shift type IDs this worker prefers
        attributes: Additional custom attributes for constraint matching
    """

    id: str
    name: str
    worker_type: str | None = None
    restricted_shifts: frozenset[str] = field(default_factory=frozenset)
    preferred_shifts: frozenset[str] = field(default_factory=frozenset)
    attributes: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self) -> None:
        """Validate worker fields after initialization."""
        if not self.id:
            raise ValueError("id cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")

        # Check for conflicts between restricted and preferred shifts
        conflicting = self.restricted_shifts & self.preferred_shifts
        if conflicting:
            shifts_str = ", ".join(sorted(conflicting))
            raise ValueError(
                f"Shifts cannot be both restricted and preferred: {shifts_str}"
            )

    def __eq__(self, other: object) -> bool:
        """Workers are equal if all fields except attributes are equal."""
        if not isinstance(other, Worker):
            return NotImplemented
        return (
            self.id == other.id
            and self.name == other.name
            and self.worker_type == other.worker_type
            and self.restricted_shifts == other.restricted_shifts
            and self.preferred_shifts == other.preferred_shifts
        )

    def __hash__(self) -> int:
        """Hash based on immutable fields only (excluding attributes dict)."""
        return hash(
            (
                self.id,
                self.name,
                self.worker_type,
                self.restricted_shifts,
                self.preferred_shifts,
            )
        )

    def can_work_shift(self, shift_type_id: str) -> bool:
        """
        Check if this worker can work a given shift type.

        Args:
            shift_type_id: The ID of the shift type to check

        Returns:
            True if the worker is not restricted from this shift type
        """
        return shift_type_id not in self.restricted_shifts

    def prefers_shift(self, shift_type_id: str) -> bool:
        """
        Check if this worker prefers a given shift type.

        Args:
            shift_type_id: The ID of the shift type to check

        Returns:
            True if the worker has marked this shift type as preferred
        """
        return shift_type_id in self.preferred_shifts
