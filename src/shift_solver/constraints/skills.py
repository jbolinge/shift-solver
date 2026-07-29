"""Skills constraint - restricts shifts to workers with matching attributes."""

from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables


class SkillsConstraint(BaseConstraint):
    """
    Hard constraint restricting shift types to workers with matching skills.

    ShiftType.required_attributes defines key/value pairs a worker must carry
    in Worker.attributes to be eligible for that shift type. A shift type
    with empty required_attributes is unconstrained -- any worker may work
    it. A worker qualifies for a shift only if every required key/value pair
    is present in their attributes.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types (checks required_attributes)
        - num_periods: int - number of scheduling periods

    No config parameters.
    """

    constraint_id = "skills"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize skills constraint."""
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply skill-matching constraints to the model.

        For every shift type with non-empty required_attributes, forces the
        assignment variable to 0 for every period for any worker whose
        attributes do not satisfy all required key/value pairs.

        Args:
            **context: Must include workers, shift_types, num_periods
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]

        for shift_type in shift_types:
            if not shift_type.required_attributes:
                # Unconstrained - any worker may work this shift type
                continue

            for worker in workers:
                if self._worker_qualifies(worker, shift_type):
                    continue

                for period in range(num_periods):
                    var = self.variables.get_assignment_var(
                        worker.id, period, shift_type.id
                    )
                    self.model.add(var == 0)
                    self._constraint_count += 1

    def _worker_qualifies(self, worker: Worker, shift_type: ShiftType) -> bool:
        """Check whether a worker's attributes satisfy a shift's requirements."""
        return all(
            worker.attributes.get(key) == value
            for key, value in shift_type.required_attributes.items()
        )
