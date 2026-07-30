"""Coverage validation strategy."""

from collections import defaultdict
from datetime import timedelta

from shift_solver.models import (
    Availability,
    PeriodAssignment,
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
    """
    Validates that coverage requirements are met.

    Mirrors CoverageConstraint's rule on the solver side: each shift type
    must have EXACTLY workers_required workers assigned per period - not
    merely "at least" - and a shift type with zero applicable days in a
    period (see ShiftType.applicable_days) expects zero workers instead.
    """

    def validate(
        self,
        schedule: Schedule,
        result: ValidationResult,
        worker_map: dict[str, Worker],  # noqa: ARG002
        shift_type_map: dict[str, ShiftType],
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

            # Check each shift type has exactly the required coverage. Use
            # shift_type_map (schedule.shift_types plus any caller-supplied
            # overrides) so richer metadata takes effect here too.
            for shift_type in shift_type_map.values():
                count = shift_type_counts.get(shift_type.id, 0)
                required = self._expected_workers(shift_type, period)

                if count < required:
                    result.add_violation(
                        "coverage",
                        f"Period {period.period_index}: Shift '{shift_type.name}' "
                        f"has {count} workers, requires {required}",
                        period_index=period.period_index,
                        shift_type_id=shift_type.id,
                        assigned=count,
                        required=required,
                    )
                elif count > required:
                    # Reported as a distinct violation type from under-coverage:
                    # the solver enforces an exact match, so over-coverage is
                    # just as invalid but has a different root cause.
                    result.add_violation(
                        "coverage_excess",
                        f"Period {period.period_index}: Shift '{shift_type.name}' "
                        f"has {count} workers, requires exactly {required} "
                        f"(over-covered by {count - required})",
                        period_index=period.period_index,
                        shift_type_id=shift_type.id,
                        assigned=count,
                        required=required,
                    )

    def _expected_workers(self, shift_type: ShiftType, period: PeriodAssignment) -> int:
        """
        Compute the expected worker count for a shift type in a period.

        Mirrors CoverageConstraint._add_coverage_for_shift: a shift type
        with applicable_days set but zero matching days in this period
        expects zero workers; otherwise it expects workers_required.
        """
        if shift_type.applicable_days is None:
            return shift_type.workers_required

        if self._count_applicable_days(shift_type, period) == 0:
            return 0
        return shift_type.workers_required

    def _count_applicable_days(
        self, shift_type: ShiftType, period: PeriodAssignment
    ) -> int:
        """Count how many days in the period the shift type applies to."""
        applicable_days = shift_type.applicable_days
        assert applicable_days is not None  # only called when days are restricted

        count = 0
        current = period.period_start
        while current <= period.period_end:
            if current.weekday() in applicable_days:
                count += 1
            current += timedelta(days=1)
        return count
