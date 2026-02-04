"""Coverage constraint - ensures required workers for each shift type."""

from datetime import date
from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables


class CoverageConstraint(BaseConstraint):
    """
    Hard constraint ensuring each shift type has the required number of workers.

    For each period and each shift type, exactly workers_required workers
    must be assigned. This is a fundamental constraint that ensures
    all shifts are properly staffed.

    Supports `applicable_days` on ShiftType to restrict which days of the week
    a shift applies. If a shift has no applicable days in a period, zero
    workers are required.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types with workers_required
        - num_periods: int - number of scheduling periods
        - period_dates: list[tuple[date, date]] - (start, end) for each period (optional)
    """

    constraint_id = "coverage"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize coverage constraint."""
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply coverage constraints to the model.

        Args:
            **context: Must include workers, shift_types, num_periods.
                       Optionally includes period_dates for applicable_days support.
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]
        period_dates: list[tuple[date, date]] | None = context.get("period_dates")

        for period in range(num_periods):
            period_start = period_dates[period][0] if period_dates else None
            period_end = period_dates[period][1] if period_dates else None

            for shift_type in shift_types:
                self._add_coverage_for_shift(
                    workers=workers,
                    shift_type=shift_type,
                    period=period,
                    period_start=period_start,
                    period_end=period_end,
                )

    def _count_applicable_days(
        self,
        shift_type: ShiftType,
        period_start: date,
        period_end: date,
    ) -> int:
        """
        Count how many days in the period the shift type applies to.

        Args:
            shift_type: Shift type with applicable_days
            period_start: Start date of the period
            period_end: End date of the period

        Returns:
            Number of days in the period where the shift applies
        """
        if shift_type.applicable_days is None:
            # None means all days - count all days in period
            return (period_end - period_start).days + 1

        from datetime import timedelta

        count = 0
        current = period_start
        while current <= period_end:
            if current.weekday() in shift_type.applicable_days:
                count += 1
            current += timedelta(days=1)
        return count

    def _add_coverage_for_shift(
        self,
        workers: list[Worker],
        shift_type: ShiftType,
        period: int,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> None:
        """
        Add coverage constraint for a specific shift type in a period.

        Args:
            workers: Available workers
            shift_type: Shift type requiring coverage
            period: Period index
            period_start: Start date of the period (for applicable_days check)
            period_end: End date of the period (for applicable_days check)
        """
        # Check if shift has applicable_days restriction
        if (
            shift_type.applicable_days is not None
            and period_start is not None
            and period_end is not None
        ):
            applicable_count = self._count_applicable_days(
                shift_type, period_start, period_end
            )

            if applicable_count == 0:
                # No applicable days in this period - force zero assignments
                for worker in workers:
                    var = self.variables.get_assignment_var(
                        worker.id, period, shift_type.id
                    )
                    self.model.add(var == 0)
                    self._constraint_count += 1
                return

        # Collect assignment variables for all workers for this shift
        assignment_vars = [
            self.variables.get_assignment_var(worker.id, period, shift_type.id)
            for worker in workers
        ]

        # Sum of assignments must equal workers_required
        self.model.add(sum(assignment_vars) == shift_type.workers_required)
        self._constraint_count += 1
