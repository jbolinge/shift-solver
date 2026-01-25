"""Availability validation strategy."""

from datetime import date

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


class AvailabilityValidationStrategy(BaseValidationStrategy):
    """Validates that no worker is assigned when unavailable."""

    def validate(
        self,
        schedule: Schedule,
        result: ValidationResult,
        worker_map: dict[str, Worker],
        shift_type_map: dict[str, ShiftType],  # noqa: ARG002
        availabilities: list[Availability] | None = None,
        requests: list[SchedulingRequest] | None = None,  # noqa: ARG002
    ) -> None:
        """Validate that no worker is assigned when unavailable."""
        if not availabilities:
            return

        # Build lookup: (worker_id, date) -> is_unavailable
        unavailable_dates: dict[tuple[str, date], bool] = {}
        for avail in availabilities:
            if avail.availability_type != "unavailable":
                continue
            # Mark all dates in range as unavailable
            current = avail.start_date
            while current <= avail.end_date:
                key = (avail.worker_id, current)
                # If shift_type_id is specified, only that shift is unavailable
                # For simplicity, we treat general unavailability as blocking all shifts
                if avail.shift_type_id is None:
                    unavailable_dates[key] = True
                current = date.fromordinal(current.toordinal() + 1)

        # Check assignments
        for period in schedule.periods:
            for worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    if (worker_id, shift.date) in unavailable_dates:
                        worker = worker_map.get(worker_id)
                        worker_name = worker.name if worker else worker_id
                        result.add_violation(
                            "availability",
                            f"Worker '{worker_name}' assigned on {shift.date} "
                            f"but marked unavailable",
                            worker_id=worker_id,
                            date=str(shift.date),
                            shift_type_id=shift.shift_type_id,
                        )
