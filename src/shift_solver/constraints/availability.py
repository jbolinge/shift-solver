"""Availability constraint - handles worker unavailability periods."""

from datetime import date
from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import Worker, ShiftType, Availability

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables


class AvailabilityConstraint(BaseConstraint):
    """
    Hard constraint enforcing worker availability/unavailability.

    When a worker has an unavailable period, they cannot be assigned
    to any shift (or a specific shift type if specified) during that time.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types
        - num_periods: int - number of scheduling periods
        - availabilities: list[Availability] - availability records
        - period_dates: list[tuple[date, date]] - (start, end) for each period
    """

    constraint_id = "availability"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize availability constraint."""
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply availability constraints to the model.

        Args:
            **context: Must include workers, shift_types, num_periods,
                      availabilities, period_dates
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]
        availabilities: list[Availability] = context["availabilities"]
        period_dates: list[tuple[date, date]] = context["period_dates"]

        # Build lookup for valid worker IDs
        valid_worker_ids = {w.id for w in workers}

        for availability in availabilities:
            # Skip if worker doesn't exist
            if availability.worker_id not in valid_worker_ids:
                continue

            # Only handle unavailable type (other types could be soft preferences)
            if availability.availability_type != "unavailable":
                continue

            # Find which periods overlap with this unavailability
            for period_idx in range(num_periods):
                period_start, period_end = period_dates[period_idx]

                if self._periods_overlap(
                    availability.start_date,
                    availability.end_date,
                    period_start,
                    period_end,
                ):
                    self._add_unavailability(
                        worker_id=availability.worker_id,
                        period=period_idx,
                        shift_types=shift_types,
                        specific_shift_id=availability.shift_type_id,
                    )

    def _periods_overlap(
        self,
        avail_start: date,
        avail_end: date,
        period_start: date,
        period_end: date,
    ) -> bool:
        """Check if availability period overlaps with scheduling period."""
        return avail_start <= period_end and avail_end >= period_start

    def _add_unavailability(
        self,
        worker_id: str,
        period: int,
        shift_types: list[ShiftType],
        specific_shift_id: str | None = None,
    ) -> None:
        """
        Add unavailability constraints for a worker in a period.

        Args:
            worker_id: Worker identifier
            period: Period index
            shift_types: Available shift types
            specific_shift_id: If set, only block this shift type; else block all
        """
        if specific_shift_id:
            # Block only the specific shift type
            assignment_var = self.variables.get_assignment_var(
                worker_id, period, specific_shift_id
            )
            self.model.add(assignment_var == 0)
            self._constraint_count += 1
        else:
            # Block all shift types
            for shift_type in shift_types:
                assignment_var = self.variables.get_assignment_var(
                    worker_id, period, shift_type.id
                )
                self.model.add(assignment_var == 0)
                self._constraint_count += 1
