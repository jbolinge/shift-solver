"""Worker shift-limit (exclusivity) validation strategy."""

from shift_solver.models import (
    Availability,
    Schedule,
    SchedulingRequest,
    ShiftType,
    Worker,
)
from shift_solver.validation.schedule_validator.result import ValidationResult
from shift_solver.validation.schedule_validator.strategies.base import (
    BaseValidationStrategy,
)


class WorkerShiftLimitValidationStrategy(BaseValidationStrategy):
    """
    Validates that no worker exceeds the maximum shift assignments per period.

    Mirrors the "worker_shift_limit" hard constraint: at most
    max_shifts_per_period assignments are allowed per (worker, period). By
    default this is 1, so a worker assigned to several shifts within the
    same period (e.g. overlapping day and night shifts) is caught.
    """

    def __init__(self, max_shifts_per_period: int = 1) -> None:
        """
        Initialize the strategy.

        Args:
            max_shifts_per_period: Maximum number of shift assignments a
                worker may have within a single period (default 1).
        """
        self.max_shifts_per_period = max_shifts_per_period

    def validate(
        self,
        schedule: Schedule,
        result: ValidationResult,
        worker_map: dict[str, Worker],
        shift_type_map: dict[str, ShiftType],  # noqa: ARG002
        availabilities: list[Availability] | None = None,  # noqa: ARG002
        requests: list[SchedulingRequest] | None = None,  # noqa: ARG002
    ) -> None:
        """Validate that no worker exceeds the per-period shift limit."""
        for period in schedule.periods:
            for worker_id, shifts in period.assignments.items():
                count = len(shifts)
                if count <= self.max_shifts_per_period:
                    continue

                worker = worker_map.get(worker_id)
                worker_name = worker.name if worker else worker_id
                result.add_violation(
                    "worker_shift_limit",
                    f"Worker '{worker_name}' has {count} shift assignments in "
                    f"period {period.period_index}, exceeds limit of "
                    f"{self.max_shifts_per_period}",
                    worker_id=worker_id,
                    period_index=period.period_index,
                    assigned=count,
                    limit=self.max_shifts_per_period,
                )
