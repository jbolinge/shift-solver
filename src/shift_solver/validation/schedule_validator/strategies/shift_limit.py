"""Worker shift-limit (exclusivity) validation strategy."""

from datetime import timedelta

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

    Mirrors the "worker_shift_limit" hard constraint, which is day-aware:
    shift types only compete for the same slots on days where they both apply
    (per ShiftType.applicable_days). For each calendar day of a period, the
    number of a worker's assigned shifts applicable on that day must not
    exceed max_shifts_per_period. Two assignments with disjoint
    applicable_days (e.g. a weekday shift plus a weekend shift) are therefore
    not a violation. Shift types missing from shift_type_map are treated as
    applicable every day (the conservative reading).
    """

    def __init__(self, max_shifts_per_period: int = 1) -> None:
        """
        Initialize the strategy.

        Args:
            max_shifts_per_period: Maximum number of shift assignments a
                worker may have on any single day of a period (default 1).
        """
        self.max_shifts_per_period = max_shifts_per_period

    def validate(
        self,
        schedule: Schedule,
        result: ValidationResult,
        worker_map: dict[str, Worker],
        shift_type_map: dict[str, ShiftType],
        availabilities: list[Availability] | None = None,  # noqa: ARG002
        requests: list[SchedulingRequest] | None = None,  # noqa: ARG002
    ) -> None:
        """Validate that no worker exceeds the per-period shift limit."""
        for period in schedule.periods:
            for worker_id, shifts in period.assignments.items():
                worst_count = 0
                worst_day = None
                current = period.period_start
                while current <= period.period_end:
                    weekday = current.weekday()
                    count = 0
                    for shift in shifts:
                        shift_type = shift_type_map.get(shift.shift_type_id)
                        applicable = (
                            shift_type is None
                            or shift_type.applicable_days is None
                            or weekday in shift_type.applicable_days
                        )
                        if applicable:
                            count += 1
                    if count > worst_count:
                        worst_count = count
                        worst_day = current
                    current += timedelta(days=1)

                if worst_count <= self.max_shifts_per_period:
                    continue

                worker = worker_map.get(worker_id)
                worker_name = worker.name if worker else worker_id
                result.add_violation(
                    "worker_shift_limit",
                    f"Worker '{worker_name}' has {worst_count} shift "
                    f"assignments applicable on {worst_day} in period "
                    f"{period.period_index}, exceeds limit of "
                    f"{self.max_shifts_per_period}",
                    worker_id=worker_id,
                    period_index=period.period_index,
                    assigned=worst_count,
                    limit=self.max_shifts_per_period,
                )
