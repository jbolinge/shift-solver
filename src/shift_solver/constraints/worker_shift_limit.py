"""Worker shift limit constraint - caps assignments per worker per period."""

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
    evening, and night shifts (24h/day) in the same period. This constraint
    bounds the sum of a worker's assignment variables across all shift types
    in a period to at most max_shifts_per_period.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types
        - num_periods: int - number of scheduling periods

    Config parameters:
        - max_shifts_per_period: int - maximum shift assignments a worker may
            hold in a single period (default: 1, i.e. mutually exclusive
            shifts)
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
            **context: Must include workers, shift_types, num_periods
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]

        max_shifts_per_period: int = self.config.get_param(
            "max_shifts_per_period", 1
        )

        for worker in workers:
            for period in range(num_periods):
                assignment_vars = [
                    self.variables.get_assignment_var(
                        worker.id, period, shift_type.id
                    )
                    for shift_type in shift_types
                ]
                self.model.add(sum(assignment_vars) <= max_shifts_per_period)
                self._constraint_count += 1
