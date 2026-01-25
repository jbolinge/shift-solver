"""Coverage validation strategy."""

from collections import defaultdict

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


class CoverageValidationStrategy(BaseValidationStrategy):
    """Validates that coverage requirements are met."""

    def validate(
        self,
        schedule: Schedule,
        result: ValidationResult,
        worker_map: dict[str, Worker],  # noqa: ARG002
        shift_type_map: dict[str, ShiftType],  # noqa: ARG002
        availabilities: list[Availability] | None = None,  # noqa: ARG002
        requests: list[SchedulingRequest] | None = None,  # noqa: ARG002
    ) -> None:
        """Validate that coverage requirements are met."""
        for period in schedule.periods:
            # Count assignments per shift type for this period
            shift_type_counts: dict[str, int] = defaultdict(int)

            for _worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    shift_type_counts[shift.shift_type_id] += 1

            # Check each shift type has required coverage
            for shift_type in schedule.shift_types:
                count = shift_type_counts.get(shift_type.id, 0)
                if count < shift_type.workers_required:
                    result.add_violation(
                        "coverage",
                        f"Period {period.period_index}: Shift '{shift_type.name}' "
                        f"has {count} workers, requires {shift_type.workers_required}",
                        period_index=period.period_index,
                        shift_type_id=shift_type.id,
                        assigned=count,
                        required=shift_type.workers_required,
                    )
