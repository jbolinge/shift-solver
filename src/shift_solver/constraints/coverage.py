"""Coverage constraint - ensures required workers for each shift type."""

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

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types with workers_required
        - num_periods: int - number of scheduling periods
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
            **context: Must include workers, shift_types, num_periods
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]

        for period in range(num_periods):
            for shift_type in shift_types:
                self._add_coverage_for_shift(
                    workers=workers,
                    shift_type=shift_type,
                    period=period,
                )

    def _add_coverage_for_shift(
        self,
        workers: list[Worker],
        shift_type: ShiftType,
        period: int,
    ) -> None:
        """
        Add coverage constraint for a specific shift type in a period.

        Args:
            workers: Available workers
            shift_type: Shift type requiring coverage
            period: Period index
        """
        # Collect assignment variables for all workers for this shift
        assignment_vars = [
            self.variables.get_assignment_var(worker.id, period, shift_type.id)
            for worker in workers
        ]

        # Sum of assignments must equal workers_required
        self.model.add(sum(assignment_vars) == shift_type.workers_required)
        self._constraint_count += 1
