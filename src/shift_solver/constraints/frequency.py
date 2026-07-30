"""Frequency constraint - ensures workers work shifts at regular intervals."""

from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints import _windows
from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker
from shift_solver.utils import get_logger

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables

logger = get_logger("constraints.frequency")


class FrequencyConstraint(BaseConstraint):
    """
    Soft constraint ensuring workers work shifts at regular intervals.

    For each sliding window of N periods, a worker should have at least
    one assignment (across the filtered shift types, combined). This
    prevents workers from being absent from certain shifts for too long.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types
        - num_periods: int - number of scheduling periods

    Config parameters:
        - max_periods_between: int - maximum periods between assignments
            (default: 4, meaning every sliding window of 4 consecutive
            periods must contain at least one assignment)
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
        """Initialize frequency constraint."""
        # Default config handled by BaseConstraint
        # Registry provides config when instantiated via solver
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply frequency constraint to the model.

        Creates one violation variable per (worker, window) that is true
        iff the worker has zero assignments across all filtered shift
        types anywhere in that window.

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

        # A window of N consecutive periods must contain at least one
        # assignment, so window_size == max_periods_between.
        window_size = max_periods_between

        # NOTE: this constraint is pinned by tests to "skip entirely" when
        # window_size > num_periods (zero windows, zero violation
        # variables), which is stricter than _windows.iter_windows's
        # default "clamp to the full horizon" policy. That guard is
        # therefore performed here, before delegating to iter_windows,
        # which as a result never sees an oversized window from this
        # caller. See _windows.py's module docstring for the full
        # rationale.
        if window_size > num_periods:
            # Window larger than schedule, nothing to constrain
            logger.warning(
                "frequency constraint: max_periods_between=%d (window_size=%d) "
                "exceeds horizon of num_periods=%d periods; constraint has no "
                "effect",
                max_periods_between,
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
            for window_start, window_end in _windows.iter_windows(
                num_periods, window_size
            ):
                # Collect all assignments across all filtered shift types
                # in this window (union across shift types, not one set
                # of violations per shift type).
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

                # Create violation variable for this window: violation =
                # 1 iff no assignment anywhere in the window, 0 otherwise.
                # Empty window_assignments (e.g. worker restricted from
                # every candidate shift type) is logged and skipped by
                # the shared helper.
                violation_var = _windows.build_absence_violation(
                    self.model,
                    window_assignments,
                    f"freq_viol_{worker.id}_w{window_start}",
                    f"freq_has_{worker.id}_w{window_start}",
                    logger=logger,
                    context="frequency constraint",
                )
                if violation_var is None:
                    continue

                self._violation_variables[f"freq_viol_{worker.id}_w{window_start}"] = (
                    violation_var
                )
                violation_count += 1
                self._constraint_count += 3  # 3 constraints per window

        # Also store total violation count for debugging. Registered as
        # "auxiliary" so ObjectiveBuilder skips it -- it is a derived sum
        # of the freq_viol_* variables above, not an independent penalty,
        # and would otherwise double the effective weight of this
        # constraint in the objective.
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
            self._violation_variable_types["total"] = "auxiliary"
