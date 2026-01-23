"""Worker restriction constraint - prevents workers from working restricted shifts."""

from typing import Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import Worker, ShiftType
from shift_solver.solver.types import SolverVariables


class RestrictionConstraint(BaseConstraint):
    """
    Hard constraint preventing workers from being assigned to restricted shifts.

    Workers may have restricted_shifts defined, which lists shift type IDs
    they cannot work. This constraint ensures those restrictions are honored.

    Required context:
        - workers: list[Worker] - workers with potential restrictions
        - shift_types: list[ShiftType] - available shift types
        - num_periods: int - number of scheduling periods
    """

    constraint_id = "restriction"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: SolverVariables,
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize restriction constraint."""
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply restriction constraints to the model.

        Args:
            **context: Must include workers, shift_types, num_periods
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]

        # Build set of valid shift type IDs for quick lookup
        valid_shift_ids = {st.id for st in shift_types}

        for worker in workers:
            for restricted_shift_id in worker.restricted_shifts:
                # Skip if restriction references a shift type that doesn't exist
                if restricted_shift_id not in valid_shift_ids:
                    continue

                # Add constraint for each period
                for period in range(num_periods):
                    self._add_restriction(
                        worker_id=worker.id,
                        shift_type_id=restricted_shift_id,
                        period=period,
                    )

    def _add_restriction(
        self,
        worker_id: str,
        shift_type_id: str,
        period: int,
    ) -> None:
        """
        Add restriction constraint for a specific worker-shift-period combination.

        Args:
            worker_id: Worker identifier
            shift_type_id: Restricted shift type identifier
            period: Period index
        """
        assignment_var = self.variables.get_assignment_var(
            worker_id, period, shift_type_id
        )
        self.model.add(assignment_var == 0)
        self._constraint_count += 1
