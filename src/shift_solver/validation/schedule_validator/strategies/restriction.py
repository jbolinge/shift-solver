"""Restriction validation strategy."""

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


class RestrictionValidationStrategy(BaseValidationStrategy):
    """Validates that no worker is assigned to a restricted shift."""

    def validate(
        self,
        schedule: Schedule,
        result: ValidationResult,
        worker_map: dict[str, Worker],
        shift_type_map: dict[str, ShiftType],
        availabilities: list[Availability] | None = None,  # noqa: ARG002
        requests: list[SchedulingRequest] | None = None,  # noqa: ARG002
    ) -> None:
        """Validate that no worker is assigned to a restricted shift."""
        for period in schedule.periods:
            for worker_id, shifts in period.assignments.items():
                worker = worker_map.get(worker_id)
                if not worker:
                    result.add_violation(
                        "data",
                        f"Unknown worker '{worker_id}' in assignments",
                        worker_id=worker_id,
                    )
                    continue

                for shift in shifts:
                    if not worker.can_work_shift(shift.shift_type_id):
                        shift_type = shift_type_map.get(shift.shift_type_id)
                        shift_name = (
                            shift_type.name if shift_type else shift.shift_type_id
                        )
                        result.add_violation(
                            "restriction",
                            f"Worker '{worker.name}' assigned to restricted "
                            f"shift '{shift_name}' on {shift.date}",
                            worker_id=worker_id,
                            shift_type_id=shift.shift_type_id,
                            date=str(shift.date),
                        )
