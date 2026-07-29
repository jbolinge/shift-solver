"""Skills validation strategy."""

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


class SkillsValidationStrategy(BaseValidationStrategy):
    """
    Validates that assigned workers satisfy each shift type's required
    attributes (skills).

    Mirrors the "skills" hard constraint: a worker may only be assigned a
    shift type whose required_attributes are all satisfied by the worker's
    attributes. Shift types with empty required_attributes are unconstrained.
    """

    def validate(
        self,
        schedule: Schedule,
        result: ValidationResult,
        worker_map: dict[str, Worker],
        shift_type_map: dict[str, ShiftType],
        availabilities: list[Availability] | None = None,  # noqa: ARG002
        requests: list[SchedulingRequest] | None = None,  # noqa: ARG002
    ) -> None:
        """Validate that workers have the skills required by their shifts."""
        for period in schedule.periods:
            for worker_id, shifts in period.assignments.items():
                worker = worker_map.get(worker_id)
                if worker is None:
                    # Unknown worker is already flagged elsewhere ([data]).
                    continue

                for shift in shifts:
                    shift_type = shift_type_map.get(shift.shift_type_id)
                    if shift_type is None:
                        # Unknown shift type is already flagged elsewhere.
                        continue

                    missing = self._missing_attributes(worker, shift_type)
                    if not missing:
                        continue

                    result.add_violation(
                        "skills",
                        f"Worker '{worker.name}' assigned to '{shift_type.name}' "
                        f"in period {period.period_index} but does not satisfy "
                        f"required attributes: {', '.join(missing)}",
                        worker_id=worker_id,
                        shift_type_id=shift.shift_type_id,
                        period_index=period.period_index,
                        missing_attributes=missing,
                    )

    def _missing_attributes(self, worker: Worker, shift_type: ShiftType) -> list[str]:
        """Return the required_attributes keys the worker does not satisfy."""
        if not shift_type.required_attributes:
            return []

        missing = []
        for key, required_value in shift_type.required_attributes.items():
            worker_value = worker.attributes.get(key)
            if worker_value != required_value:
                missing.append(key)
        return missing
