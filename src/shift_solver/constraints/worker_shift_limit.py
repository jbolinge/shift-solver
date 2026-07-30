"""Worker shift limit constraint - caps assignments per worker per period."""

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables


class WorkerShiftLimitConstraint(BaseConstraint):
    """
    Hard constraint capping how many shifts a worker may hold in one period.

    Without this constraint the solver has no notion of per-worker-per-period
    exclusivity: nothing stops a single worker from being assigned the day,
    evening, and night shifts (24h/day) in the same period.

    The limit is day-aware: shift types only compete for the same slots on
    days where they both apply (per ShiftType.applicable_days). For each
    calendar day in a period, the sum of a worker's assignments across the
    shift types applicable on that day is bounded by max_shifts_per_period.
    Two shifts with disjoint applicable_days (e.g. a weekday shift and a
    weekend shift) can therefore both be held by the same worker in the same
    period - they never occur on the same day. Without period_dates in the
    context, all shift types are treated as one group (every shift type
    competes with every other), matching the pre-day-aware behavior.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types
        - num_periods: int - number of scheduling periods
        - period_dates: list[tuple[date, date]] - (start, end) per period
          (optional; enables day-aware applicable_days handling)

    Config parameters:
        - max_shifts_per_period: int - maximum shift assignments a worker may
            hold on any single day of a period (default: 1, i.e. mutually
            exclusive shifts)
    """

    constraint_id = "worker_shift_limit"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize worker shift limit constraint."""
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply the per-worker-per-period shift limit to the model.

        Args:
            **context: Must include workers, shift_types, num_periods.
                Optionally includes period_dates for day-aware handling.
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]
        period_dates: list[tuple[date, date]] | None = context.get("period_dates")

        max_shifts_per_period: int = self.config.get_param("max_shifts_per_period", 1)

        for period in range(num_periods):
            groups = self._competing_groups(shift_types, period, period_dates)
            for worker in workers:
                for group in groups:
                    assignment_vars = [
                        self.variables.get_assignment_var(
                            worker.id, period, shift_type_id
                        )
                        for shift_type_id in group
                    ]
                    self.model.add(sum(assignment_vars) <= max_shifts_per_period)
                    self._constraint_count += 1

    @staticmethod
    def _competing_groups(
        shift_types: list[ShiftType],
        period: int,
        period_dates: list[tuple[date, date]] | None,
    ) -> list[frozenset[str]]:
        """
        Compute the sets of shift types that compete on some day of a period.

        Each returned group is the set of shift type ids applicable on one
        calendar day of the period (deduplicated across days, and with
        subsets of other groups dropped - a subset sum is implied by the
        superset's bound). Without period_dates, the single group of all
        shift types is returned.
        """
        if period_dates is None or period >= len(period_dates):
            return [frozenset(st.id for st in shift_types)]

        period_start, period_end = period_dates[period]
        groups: set[frozenset[str]] = set()
        current = period_start
        while current <= period_end:
            weekday = current.weekday()
            group = frozenset(
                st.id
                for st in shift_types
                if st.applicable_days is None or weekday in st.applicable_days
            )
            if group:
                groups.add(group)
            current += timedelta(days=1)

        # Drop groups fully contained in another: their bound is implied.
        maximal = [
            g for g in groups if not any(g < other for other in groups if other != g)
        ]
        return maximal
