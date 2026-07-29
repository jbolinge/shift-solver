"""Availability validation strategy."""

from collections import defaultdict
from datetime import date

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


class AvailabilityValidationStrategy(BaseValidationStrategy):
    """
    Validates that no worker is assigned when unavailable.

    The engine is period-granular: a single assignment covers an entire
    scheduling period, and SolutionExtractor always stamps ShiftInstance.date
    as the period's start date. Comparing unavailability ranges against that
    fixed date would miss any unavailability that doesn't happen to start
    exactly on the period's first day, so this strategy instead checks
    whether the unavailability range OVERLAPS the assignment's period date
    range - mirroring how AvailabilityConstraint enforces it on the solver
    side. Shift-type-scoped unavailability (avail.shift_type_id set) is
    validated against the matching shift type only.
    """

    def validate(
        self,
        schedule: Schedule,
        result: ValidationResult,
        worker_map: dict[str, Worker],
        shift_type_map: dict[str, ShiftType],  # noqa: ARG002
        availabilities: list[Availability] | None = None,
        requests: list[SchedulingRequest] | None = None,  # noqa: ARG002
    ) -> None:
        """Validate that no worker is assigned during an unavailable period."""
        if not availabilities:
            return

        unavailable_by_worker: dict[str, list[Availability]] = defaultdict(list)
        for avail in availabilities:
            if avail.availability_type != "unavailable":
                continue
            unavailable_by_worker[avail.worker_id].append(avail)

        if not unavailable_by_worker:
            return

        for period in schedule.periods:
            for worker_id, shifts in period.assignments.items():
                avail_records = unavailable_by_worker.get(worker_id)
                if not avail_records:
                    continue

                for shift in shifts:
                    conflict = self._find_conflict(
                        avail_records, shift.shift_type_id, period
                    )
                    if conflict is None:
                        continue

                    worker = worker_map.get(worker_id)
                    worker_name = worker.name if worker else worker_id
                    result.add_violation(
                        "availability",
                        f"Worker '{worker_name}' assigned to '{shift.shift_type_id}' "
                        f"in period {period.period_index} "
                        f"({period.period_start} to {period.period_end}) but marked "
                        f"unavailable ({conflict.start_date} to {conflict.end_date})",
                        worker_id=worker_id,
                        period_index=period.period_index,
                        shift_type_id=shift.shift_type_id,
                        date=str(shift.date),
                    )

    def _find_conflict(
        self,
        avail_records: list[Availability],
        shift_type_id: str,
        period: PeriodAssignment,
    ) -> Availability | None:
        """Find the first unavailability record that conflicts with a shift."""
        for avail in avail_records:
            if avail.shift_type_id is not None and avail.shift_type_id != shift_type_id:
                continue
            if self._ranges_overlap(
                avail.start_date, avail.end_date, period.period_start, period.period_end
            ):
                return avail
        return None

    def _ranges_overlap(
        self,
        start_a: date,
        end_a: date,
        start_b: date,
        end_b: date,
    ) -> bool:
        """Check whether two inclusive date ranges overlap."""
        return start_a <= end_b and end_a >= start_b
