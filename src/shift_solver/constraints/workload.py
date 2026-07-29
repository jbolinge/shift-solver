"""Workload constraint - bounds total shifts per worker over the horizon."""

from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables


class WorkloadConstraint(BaseConstraint):
    """
    Soft constraint bounding each worker's total shift count over the horizon.

    Reads the shift_counts variables already built by VariableBuilder (never
    otherwise consumed by any constraint) and penalizes per-worker totals
    that fall outside [min_total_shifts, max_total_shifts]. Shortfall and
    excess are tracked as separate integer violation amounts so
    ObjectiveBuilder can weight them by however many shifts a worker is
    over/under. In hard mode, the generic is_hard enforcement in ShiftSolver
    forces both violation variables to zero, which pins each worker's total
    into the configured range.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types
        - num_periods: int - number of scheduling periods

    Config parameters:
        - min_total_shifts: int - minimum shifts a worker should be assigned
            across the whole horizon (default: 0)
        - max_total_shifts: int | None - maximum shifts a worker should be
            assigned across the whole horizon (default: None, unbounded)
    """

    constraint_id = "workload"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize workload constraint."""
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply per-worker workload bounds to the model.

        Creates a per-worker total variable (auxiliary, not penalized
        directly) plus shortfall/excess violation variables measuring how
        far the total strays outside [min_total_shifts, max_total_shifts].

        Args:
            **context: Must include workers, shift_types, num_periods
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]

        if not workers or not shift_types:
            return

        min_total_shifts: int = self.config.get_param("min_total_shifts", 0)
        max_total_shifts: int | None = self.config.get_param("max_total_shifts")

        max_possible = num_periods * len(shift_types)

        for worker in workers:
            count_vars = [
                self.variables.get_shift_count_var(worker.id, shift_type.id)
                for shift_type in shift_types
            ]

            total_var = self.model.new_int_var(
                0, max_possible, f"workload_total_{worker.id}"
            )
            self.model.add(total_var == sum(count_vars))
            self._constraint_count += 1

            # Auxiliary total - not itself a penalty, excluded from objective
            total_name = f"total_{worker.id}"
            self._violation_variables[total_name] = total_var
            self._violation_variable_types[total_name] = "auxiliary"

            if min_total_shifts > 0:
                shortfall_name = f"shortfall_{worker.id}"
                shortfall_var = self.model.new_int_var(
                    0, min_total_shifts, f"workload_{shortfall_name}"
                )
                # shortfall >= min_total_shifts - total (and >= 0), minimized
                # to its tightest feasible value by the objective/hard mode.
                self.model.add(shortfall_var >= min_total_shifts - total_var)
                self._constraint_count += 1
                self._violation_variables[shortfall_name] = shortfall_var

            if max_total_shifts is not None:
                excess_name = f"excess_{worker.id}"
                excess_var = self.model.new_int_var(
                    0, max_possible, f"workload_{excess_name}"
                )
                # excess >= total - max_total_shifts (and >= 0)
                self.model.add(excess_var >= total_var - max_total_shifts)
                self._constraint_count += 1
                self._violation_variables[excess_name] = excess_var
