"""Shift frequency constraint - per-worker requirements for shift type groups."""

from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftFrequencyRequirement, ShiftType, Worker

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables


class ShiftFrequencyConstraint(BaseConstraint):
    """
    Constraint for per-worker shift frequency requirements.

    Ensures workers work at least one of a specified set of shift types
    within every N periods using a sliding window approach.

    This differs from FrequencyConstraint which applies uniformly to all
    workers for individual shift types. ShiftFrequencyConstraint allows:
    - Per-worker requirements (different workers can have different requirements)
    - Shift type groups (must work one of [A, B, C], not each individually)

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types
        - num_periods: int - number of scheduling periods
        - shift_frequency_requirements: list[ShiftFrequencyRequirement] - per-worker requirements

    Example config:
        constraints:
          shift_frequency:
            enabled: true
            is_hard: false
            weight: 500
    """

    constraint_id = "shift_frequency"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize shift frequency constraint."""
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply shift frequency constraint to the model.

        For each requirement, creates sliding window constraints that ensure
        the worker works at least one of the specified shift types within
        each window.

        Args:
            **context: Must include workers, shift_types, num_periods,
                       shift_frequency_requirements
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]
        requirements: list[ShiftFrequencyRequirement] = context.get(
            "shift_frequency_requirements", []
        )

        if not requirements:
            return

        # Build lookup maps
        worker_map = {w.id: w for w in workers}
        shift_type_ids = {st.id for st in shift_types}

        for req in requirements:
            self._apply_requirement(
                req, worker_map, shift_type_ids, num_periods
            )

    def _apply_requirement(
        self,
        req: ShiftFrequencyRequirement,
        worker_map: dict[str, Worker],
        shift_type_ids: set[str],
        num_periods: int,
    ) -> None:
        """Apply a single frequency requirement."""
        # Skip if worker doesn't exist
        if req.worker_id not in worker_map:
            return

        # Filter to valid shift types
        valid_shift_types = req.shift_types & shift_type_ids
        if not valid_shift_types:
            return

        # Window size equals max_periods_between
        # e.g., max_periods_between=4 means must work at least once every 4 periods
        window_size = req.max_periods_between

        if window_size > num_periods:
            # Window larger than schedule, only one window covering all periods
            window_size = num_periods

        # Create sliding window constraints
        num_windows = num_periods - window_size + 1

        for window_start in range(num_windows):
            self._create_window_constraint(
                req.worker_id,
                valid_shift_types,
                window_start,
                window_size,
            )

    def _create_window_constraint(
        self,
        worker_id: str,
        shift_types: frozenset[str],
        window_start: int,
        window_size: int,
    ) -> None:
        """Create constraint for a single sliding window."""
        # Collect all assignment variables for this worker in this window
        # for any of the required shift types
        window_assignments: list[cp_model.IntVar] = []

        for period in range(window_start, window_start + window_size):
            for shift_type_id in shift_types:
                try:
                    var = self.variables.get_assignment_var(
                        worker_id, period, shift_type_id
                    )
                    window_assignments.append(var)
                except KeyError:
                    # Variable doesn't exist (worker restricted from shift)
                    continue

        if not window_assignments:
            # No valid assignments possible in this window
            # This is either infeasible (hard) or always violated (soft)
            if self.is_hard:
                # Add infeasible constraint
                self.model.add_bool_or([])  # Always false
            else:
                # Create always-violated variable
                violation_name = f"sf_viol_{worker_id}_w{window_start}"
                violation_var = self.model.new_constant(1)
                self._violation_variables[violation_name] = violation_var
            return

        if self.is_hard:
            # Hard constraint: must have at least one assignment
            self.model.add(sum(window_assignments) >= 1)
            self._constraint_count += 1
        else:
            # Soft constraint: create violation variable
            violation_name = f"sf_viol_{worker_id}_w{window_start}"
            violation_var = self.model.new_bool_var(violation_name)

            # Create indicator: has_assignment = (sum >= 1)
            has_assignment = self.model.new_bool_var(
                f"sf_has_{worker_id}_w{window_start}"
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
            self._constraint_count += 3
