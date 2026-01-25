"""Base class for validation strategies."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shift_solver.models import (
        Availability,
        Schedule,
        SchedulingRequest,
        ShiftType,
        Worker,
    )
    from shift_solver.validation.schedule_validator.result import ValidationResult


class BaseValidationStrategy(ABC):
    """
    Abstract base class for validation strategies.

    Each strategy encapsulates a specific type of validation logic.
    """

    @abstractmethod
    def validate(
        self,
        schedule: "Schedule",
        result: "ValidationResult",
        worker_map: dict[str, "Worker"],
        shift_type_map: dict[str, "ShiftType"],
        availabilities: list["Availability"] | None = None,
        requests: list["SchedulingRequest"] | None = None,
    ) -> None:
        """
        Perform validation and update the result.

        Args:
            schedule: The schedule to validate
            result: ValidationResult to update
            worker_map: Map of worker_id to Worker
            shift_type_map: Map of shift_type_id to ShiftType
            availabilities: Optional list of availability records
            requests: Optional list of scheduling requests
        """
        pass
