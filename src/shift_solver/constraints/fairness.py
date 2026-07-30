"""Fairness constraint - ensures even distribution of undesirable shifts."""

from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker
from shift_solver.utils import get_logger

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables

logger = get_logger("constraints.fairness")


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
        - tolerance: int (default 0) - allowed spread before it counts against
            the constraint. Hard mode enforces spread <= tolerance (an exact
            equal split, tolerance=0, is rarely satisfiable). Soft mode only
            penalizes the portion of the spread that exceeds tolerance.
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
            logger.warning(
                "fairness constraint: only %d worker(s) provided; nothing to "
                "balance (need at least 2)",
                len(workers),
            )
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
            if categories:
                logger.warning(
                    "fairness constraint: no shift types match configured "
                    "categories %s; nothing to balance",
                    categories,
                )
            else:
                logger.warning(
                    "fairness constraint: no shift types are marked "
                    "is_undesirable and no categories filter is configured; "
                    "nothing to balance"
                )
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
            logger.warning(
                "fairness constraint: fewer than 2 workers have a countable "
                "undesirable-shift total (%d); nothing to balance",
                len(worker_totals),
            )
            return

        # Calculate maximum possible undesirable shifts per worker
        max_possible = num_periods * len(undesirable_shift_ids)

        # Create max_undesirable variable (max across all workers)
        # add_max_equality already implies max_undesirable >= total for every
        # worker, so no separate per-worker bound constraints are needed.
        max_undesirable = self.model.new_int_var(
            0, max_possible, "fairness_max_undesirable"
        )
        self.model.add_max_equality(max_undesirable, worker_totals)
        self._constraint_count += 1

        # Create min_undesirable variable (min across all workers)
        # add_min_equality already implies min_undesirable <= total for every
        # worker, so no separate per-worker bound constraints are needed.
        min_undesirable = self.model.new_int_var(
            0, max_possible, "fairness_min_undesirable"
        )
        self.model.add_min_equality(min_undesirable, worker_totals)
        self._constraint_count += 1

        # Create spread variable: the excess of (max - min) above the
        # configured tolerance, clamped at 0. `spread >= raw_spread -
        # tolerance` (plus the domain's implicit `spread >= 0`) is a lower
        # bound rather than an equality; since spread is always either
        # pinned to 0 (hard mode, via the generic soft->hard enforcement)
        # or minimized in the objective (soft mode), the solver drives it
        # down to its tightest feasible value: max(0, raw_spread - tolerance).
        # With the default tolerance=0 this is numerically identical to the
        # raw max - min spread, preserving prior behavior.
        tolerance: int = self.config.get_param("tolerance", 0)
        spread = self.model.new_int_var(0, max_possible, "fairness_spread")
        self.model.add(spread >= max_undesirable - min_undesirable - tolerance)
        self._constraint_count += 1

        # Store spread as the violation variable for objective building
        self._violation_variables["spread"] = spread
        self._violation_variables["max_undesirable"] = max_undesirable
        self._violation_variables["min_undesirable"] = min_undesirable

        # Mark variable types for ObjectiveBuilder
        self._violation_variable_types["spread"] = "objective_target"
        self._violation_variable_types["max_undesirable"] = "auxiliary"
        self._violation_variable_types["min_undesirable"] = "auxiliary"
