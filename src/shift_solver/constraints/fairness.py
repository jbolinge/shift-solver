"""Fairness constraint - ensures even distribution of undesirable shifts."""

from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables


class FairnessConstraint(BaseConstraint):
    """
    Soft constraint for fair distribution of undesirable shifts.

    Minimizes the spread (max - min) of undesirable shift assignments
    across all workers. This encourages an even distribution of less
    desirable shifts like nights and weekends.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types (checks is_undesirable)
        - num_periods: int - number of scheduling periods

    Config parameters:
        - categories: list[str] - if set, only count shifts in these categories
            (default: use is_undesirable flag on shift types)
    """

    constraint_id = "fairness"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize fairness constraint."""
        # Default config handled by BaseConstraint
        # Registry provides config when instantiated via solver
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply fairness constraint to the model.

        Creates variables to track the maximum and minimum undesirable
        shift counts across workers, and a spread variable representing
        their difference.

        Args:
            **context: Must include workers, shift_types, num_periods
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]

        if len(workers) < 2:
            # No fairness to balance with 0 or 1 workers
            return

        # Get configured categories (if any)
        categories: list[str] | None = self.config.get_param("categories")

        # Identify which shift types to count for fairness
        if categories:
            undesirable_shift_ids = {
                st.id for st in shift_types if st.category in categories
            }
        else:
            undesirable_shift_ids = {st.id for st in shift_types if st.is_undesirable}

        if not undesirable_shift_ids:
            # No undesirable shifts to balance
            return

        # Calculate the total number of undesirable shifts per worker
        # Using custom count if categories filter is applied, otherwise use pre-built totals
        worker_totals: list[cp_model.IntVar] = []

        if categories:
            # Need to compute custom totals for the filtered categories
            for worker in workers:
                assignments = []
                for period in range(num_periods):
                    for shift_id in undesirable_shift_ids:
                        try:
                            var = self.variables.get_assignment_var(
                                worker.id, period, shift_id
                            )
                            assignments.append(var)
                        except KeyError:
                            continue

                if assignments:
                    total_var = self.model.new_int_var(
                        0,
                        len(assignments),
                        f"fairness_total_{worker.id}",
                    )
                    self.model.add(total_var == sum(assignments))
                    worker_totals.append(total_var)
        else:
            # Use the pre-computed undesirable_totals from VariableBuilder
            for worker in workers:
                try:
                    total_var = self.variables.get_undesirable_total_var(worker.id)
                    worker_totals.append(total_var)
                except KeyError:
                    continue

        if len(worker_totals) < 2:
            return

        # Calculate maximum possible undesirable shifts per worker
        max_possible = num_periods * len(undesirable_shift_ids)

        # Create max_undesirable variable (max across all workers)
        max_undesirable = self.model.new_int_var(
            0, max_possible, "fairness_max_undesirable"
        )
        for total in worker_totals:
            self.model.add(max_undesirable >= total)
        self.model.add_max_equality(max_undesirable, worker_totals)
        self._constraint_count += len(worker_totals) + 1

        # Create min_undesirable variable (min across all workers)
        min_undesirable = self.model.new_int_var(
            0, max_possible, "fairness_min_undesirable"
        )
        for total in worker_totals:
            self.model.add(min_undesirable <= total)
        self.model.add_min_equality(min_undesirable, worker_totals)
        self._constraint_count += len(worker_totals) + 1

        # Create spread variable (max - min)
        spread = self.model.new_int_var(0, max_possible, "fairness_spread")
        self.model.add(spread == max_undesirable - min_undesirable)
        self._constraint_count += 1

        # Store spread as the violation variable for objective building
        self._violation_variables["spread"] = spread
        self._violation_variables["max_undesirable"] = max_undesirable
        self._violation_variables["min_undesirable"] = min_undesirable
