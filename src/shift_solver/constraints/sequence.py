"""Sequence constraint - discourages consecutive same-category shifts."""

from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables


class SequenceConstraint(BaseConstraint):
    """
    Soft constraint discouraging consecutive same-category shifts.

    Penalizes when a worker is assigned to shifts in the same category
    in consecutive periods. This helps distribute variety in assignments.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types with categories
        - num_periods: int - number of scheduling periods

    Config parameters:
        - categories: list[str] - if set, only apply to these categories
            (default: apply to all categories)
    """

    constraint_id = "sequence"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize sequence constraint."""
        # Default config handled by BaseConstraint
        # Registry provides config when instantiated via solver
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply sequence constraint to the model.

        Creates violation variables for consecutive same-category assignments.

        Args:
            **context: Must include workers, shift_types, num_periods
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]

        if num_periods < 2:
            return

        # Get target categories
        target_categories: list[str] | None = self.config.get_param("categories")

        # Group shift types by category
        shifts_by_category: dict[str, list[ShiftType]] = {}
        for st in shift_types:
            if target_categories is None or st.category in target_categories:
                if st.category not in shifts_by_category:
                    shifts_by_category[st.category] = []
                shifts_by_category[st.category].append(st)

        if not shifts_by_category:
            return

        violation_count = 0

        for worker in workers:
            for category, category_shifts in shifts_by_category.items():
                # Check consecutive periods
                for period in range(num_periods - 1):
                    next_period = period + 1

                    # Get all assignments for this category in both periods
                    current_vars = []
                    next_vars = []

                    for st in category_shifts:
                        try:
                            current_var = self.variables.get_assignment_var(
                                worker.id, period, st.id
                            )
                            current_vars.append(current_var)
                        except KeyError:
                            continue

                        try:
                            next_var = self.variables.get_assignment_var(
                                worker.id, next_period, st.id
                            )
                            next_vars.append(next_var)
                        except KeyError:
                            continue

                    if not current_vars or not next_vars:
                        continue

                    # Create indicator for "assigned in current period"
                    assigned_current = self.model.new_bool_var(
                        f"seq_curr_{worker.id}_{category}_p{period}"
                    )
                    # assigned_current = 1 iff sum(current_vars) >= 1
                    self.model.add(sum(current_vars) >= 1).only_enforce_if(
                        assigned_current
                    )
                    self.model.add(sum(current_vars) == 0).only_enforce_if(
                        assigned_current.negated()
                    )

                    # Create indicator for "assigned in next period"
                    assigned_next = self.model.new_bool_var(
                        f"seq_next_{worker.id}_{category}_p{next_period}"
                    )
                    self.model.add(sum(next_vars) >= 1).only_enforce_if(assigned_next)
                    self.model.add(sum(next_vars) == 0).only_enforce_if(
                        assigned_next.negated()
                    )

                    # Violation = both are assigned (consecutive)
                    violation_name = f"seq_viol_{worker.id}_{category}_p{period}"
                    violation_var = self.model.new_bool_var(violation_name)

                    # violation = assigned_current AND assigned_next
                    self.model.add_bool_and(
                        [assigned_current, assigned_next]
                    ).only_enforce_if(violation_var)
                    self.model.add_bool_or(
                        [assigned_current.negated(), assigned_next.negated()]
                    ).only_enforce_if(violation_var.negated())

                    self._violation_variables[violation_name] = violation_var
                    violation_count += 1
                    self._constraint_count += 6  # Multiple constraints per pair

        # Store total for debugging
        if violation_count > 0:
            total_var = self.model.new_int_var(
                0, violation_count, "sequence_total_violations"
            )
            viol_vars = [
                v
                for k, v in self._violation_variables.items()
                if k.startswith("seq_viol_")
            ]
            self.model.add(total_var == sum(viol_vars))
            self._violation_variables["total"] = total_var
