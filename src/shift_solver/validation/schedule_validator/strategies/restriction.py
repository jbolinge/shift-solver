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
        """Validate that no worker is assigned to a restricted or unknown shift."""
        for period in schedule.periods:
            for worker_id, shifts in period.assignments.items():
                worker = worker_map.get(worker_id)
                if not worker:
                    result.add_violation(
                        "data",
                        f"Unknown worker '{worker_id}' in assignments",
                        worker_id=worker_id,
                    )

                for shift in shifts:
                    shift_type = shift_type_map.get(shift.shift_type_id)
                    if shift_type is None:
                        result.add_violation(
                            "data",
                            f"Unknown shift type '{shift.shift_type_id}' assigned "
                            f"to worker '{worker_id}'",
                            worker_id=worker_id,
                            shift_type_id=shift.shift_type_id,
                        )
                        continue

                    if worker is None:
                        # Already flagged as an unknown worker above; without a
                        # worker record there is nothing more to check here.
                        continue

                    if not worker.can_work_shift(shift.shift_type_id):
                        result.add_violation(
                            "restriction",
                            f"Worker '{worker.name}' assigned to restricted "
                            f"shift '{shift_type.name}' on {shift.date}",
                            worker_id=worker_id,
                            shift_type_id=shift.shift_type_id,
                            date=str(shift.date),
                        )
