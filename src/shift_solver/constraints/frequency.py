"""Frequency constraint - ensures workers work shifts at regular intervals."""

from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables


class FrequencyConstraint(BaseConstraint):
    """
    Soft constraint ensuring workers work shifts at regular intervals.

    For each sliding window of N periods, a worker should have at least
    one assignment. This prevents workers from being absent from certain
    shifts for too long.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types
        - num_periods: int - number of scheduling periods

    Config parameters:
        - max_periods_between: int - maximum periods between assignments
            (default: 4, meaning check windows of size 5)
        - shift_types: list[str] - if set, only apply to these shift types
            (default: apply to all shift types)
    """

    constraint_id = "frequency"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize frequency constraint with soft default."""
        if config is None:
            config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply frequency constraint to the model.

        Creates violation variables for each worker-window combination
        where no assignment exists.

        Args:
            **context: Must include workers, shift_types, num_periods
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]

        # Get parameters
        max_periods_between: int = self.config.get_param("max_periods_between", 4)
        target_shift_types: list[str] | None = self.config.get_param("shift_types")

        # Window size is max_periods_between + 1
        # (e.g., max 3 periods between = window of 4 periods)
        window_size = max_periods_between + 1

        if window_size > num_periods:
            # Window larger than schedule, nothing to constrain
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
            for shift_type in filtered_shifts:
                # Check each sliding window
                for window_start in range(num_periods - window_size + 1):
                    window_end = window_start + window_size

                    # Collect all assignments in this window
                    window_assignments = []
                    for period in range(window_start, window_end):
                        try:
                            var = self.variables.get_assignment_var(
                                worker.id, period, shift_type.id
                            )
                            window_assignments.append(var)
                        except KeyError:
                            continue

                    if not window_assignments:
                        continue

                    # Create violation variable for this window
                    # violation = 1 if no assignment in window, 0 otherwise
                    violation_name = (
                        f"freq_viol_{worker.id}_{shift_type.id}_w{window_start}"
                    )
                    violation_var = self.model.new_bool_var(violation_name)

                    # at_least_one = sum(assignments) >= 1
                    # violation = (sum(assignments) == 0)
                    # We use: sum(assignments) >= 1 - violation
                    # If violation=0, sum >= 1 (must have assignment)
                    # If violation=1, sum >= 0 (no requirement)
                    # And we want to minimize violations

                    # Create indicator: has_assignment = (sum >= 1)
                    has_assignment = self.model.new_bool_var(
                        f"freq_has_{worker.id}_{shift_type.id}_w{window_start}"
                    )

                    # has_assignment is true iff sum(window_assignments) >= 1
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
                    self._constraint_count += 3  # 3 constraints per window

        # Also store total violation count for debugging
        if violation_count > 0:
            total_var = self.model.new_int_var(
                0, violation_count, "frequency_total_violations"
            )
            self.model.add(
                total_var
                == sum(
                    v
                    for k, v in self._violation_variables.items()
                    if k.startswith("freq_viol_")
                )
            )
            self._violation_variables["total"] = total_var
