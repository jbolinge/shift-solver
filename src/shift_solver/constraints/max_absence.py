"""Max absence constraint - penalizes long gaps without a shift type."""

from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker
from shift_solver.utils import get_logger

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables

logger = get_logger("constraints.max_absence")


class MaxAbsenceConstraint(BaseConstraint):
    """
    Soft constraint penalizing long absences from shift types.

    Penalizes when a worker goes an entire window of N consecutive
    periods without being assigned to any of the filtered shift types.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types
        - num_periods: int - number of scheduling periods

    Config parameters:
        - max_periods_absent: int - maximum consecutive periods without
            assignment before violation (default: 8, meaning every sliding
            window of 8 consecutive periods must contain at least one
            assignment)
        - shift_types: list[str] - if set, only apply to these shift types
            (default: apply to all shift types)
    """

    constraint_id = "max_absence"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize max absence constraint."""
        # Default config handled by BaseConstraint
        # Registry provides config when instantiated via solver
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply max absence constraint to the model.

        For each window of max_periods_absent periods, creates one
        violation variable per (worker, window) that is true iff the
        worker has zero assignments across all filtered shift types
        anywhere in that window.

        Args:
            **context: Must include workers, shift_types, num_periods
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]

        # Get parameters
        max_periods_absent: int = self.config.get_param("max_periods_absent", 8)
        target_shift_types: list[str] | None = self.config.get_param("shift_types")

        # A window of N consecutive periods must contain at least one
        # assignment, so window_size == max_periods_absent.
        window_size = max_periods_absent

        if window_size > num_periods:
            logger.warning(
                "max_absence constraint: max_periods_absent=%d (window_size=%d) "
                "exceeds horizon of num_periods=%d periods; constraint has no "
                "effect",
                max_periods_absent,
                window_size,
                num_periods,
            )
            return

        # Filter shift types if specified
        if target_shift_types:
            filtered_shifts = [st for st in shift_types if st.id in target_shift_types]
        else:
            filtered_shifts = shift_types

        if not filtered_shifts:
            return

        violation_count = 0

        for worker in workers:
            # Check each sliding window
            for window_start in range(num_periods - window_size + 1):
                window_end = window_start + window_size

                # Collect assignments across all filtered shift types in
                # this window (union across shift types, not one set of
                # violations per shift type).
                window_assignments = []
                for period in range(window_start, window_end):
                    for shift_type in filtered_shifts:
                        try:
                            var = self.variables.get_assignment_var(
                                worker.id, period, shift_type.id
                            )
                            window_assignments.append(var)
                        except KeyError:
                            continue

                if not window_assignments:
                    continue

                # Violation if no assignment in window
                violation_name = f"abs_viol_{worker.id}_w{window_start}"
                violation_var = self.model.new_bool_var(violation_name)

                # Create indicator: has_assignment = (sum >= 1)
                has_assignment = self.model.new_bool_var(
                    f"abs_has_{worker.id}_w{window_start}"
                )

                self.model.add(sum(window_assignments) >= 1).only_enforce_if(
                    has_assignment
                )
                self.model.add(sum(window_assignments) == 0).only_enforce_if(
                    has_assignment.negated()
                )

                # violation = NOT has_assignment
                self.model.add(violation_var == has_assignment.negated())

                self._violation_variables[violation_name] = violation_var
                violation_count += 1
                self._constraint_count += 3

        # Store total for debugging. Registered as "auxiliary" so
        # ObjectiveBuilder skips it -- it is a derived sum of the
        # abs_viol_* variables above, not an independent penalty, and
        # would otherwise double the effective weight of this constraint
        # in the objective.
        if violation_count > 0:
            total_var = self.model.new_int_var(
                0, violation_count, "max_absence_total_violations"
            )
            viol_vars = [
                v
                for k, v in self._violation_variables.items()
                if k.startswith("abs_viol_")
            ]
            self.model.add(total_var == sum(viol_vars))
            self._violation_variables["total"] = total_var
            self._violation_variable_types["total"] = "auxiliary"
