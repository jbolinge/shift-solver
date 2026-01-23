"""VariableBuilder - creates OR-Tools variables from domain models."""

from ortools.sat.python import cp_model

from shift_solver.models import Worker, ShiftType
from shift_solver.solver.types import SolverVariables


class VariableBuilder:
    """
    Builds OR-Tools solver variables from domain models.

    This class encapsulates the creation of all decision variables needed
    for the shift scheduling optimization problem. It creates:
    - Assignment variables (binary): worker assigned to shift in period
    - Shift count variables (integer): total shifts per worker per type
    - Undesirable total variables (integer): total undesirable shifts per worker

    The builder also adds linking constraints to ensure count variables
    correctly sum up the assignment variables.
    """

    def __init__(
        self,
        model: cp_model.CpModel,
        workers: list[Worker],
        shift_types: list[ShiftType],
        num_periods: int,
    ) -> None:
        """
        Initialize the VariableBuilder.

        Args:
            model: OR-Tools CP model to add variables to
            workers: List of workers to schedule
            shift_types: List of shift types available
            num_periods: Number of scheduling periods

        Raises:
            ValueError: If workers, shift_types is empty, or num_periods <= 0
        """
        if not workers:
            raise ValueError("workers list cannot be empty")
        if not shift_types:
            raise ValueError("shift_types list cannot be empty")
        if num_periods <= 0:
            raise ValueError("num_periods must be positive")

        self.model = model
        self.workers = workers
        self.shift_types = shift_types
        self.num_periods = num_periods

        # Build lookup for undesirable shift types
        self._undesirable_shift_ids = frozenset(
            st.id for st in shift_types if st.is_undesirable
        )

    def build(self) -> SolverVariables:
        """
        Build all solver variables and linking constraints.

        Returns:
            SolverVariables container with all created variables
        """
        # Create assignment variables
        assignment = self._build_assignment_variables()

        # Create shift count variables and linking constraints
        shift_counts = self._build_shift_count_variables(assignment)

        # Create undesirable total variables and linking constraints
        undesirable_totals = self._build_undesirable_total_variables(assignment)

        return SolverVariables(
            assignment=assignment,
            shift_counts=shift_counts,
            undesirable_totals=undesirable_totals,
        )

    def _build_assignment_variables(
        self,
    ) -> dict[str, dict[int, dict[str, cp_model.IntVar]]]:
        """
        Create binary assignment variables for worker-period-shift combinations.

        Returns:
            Nested dict: worker_id -> period -> shift_type_id -> IntVar
        """
        assignment: dict[str, dict[int, dict[str, cp_model.IntVar]]] = {}

        for worker in self.workers:
            assignment[worker.id] = {}
            for period in range(self.num_periods):
                assignment[worker.id][period] = {}
                for shift_type in self.shift_types:
                    var_name = f"assign_{worker.id}_p{period}_{shift_type.id}"
                    assignment[worker.id][period][shift_type.id] = (
                        self.model.new_bool_var(var_name)
                    )

        return assignment

    def _build_shift_count_variables(
        self,
        assignment: dict[str, dict[int, dict[str, cp_model.IntVar]]],
    ) -> dict[str, dict[str, cp_model.IntVar]]:
        """
        Create shift count variables and link them to assignments.

        Args:
            assignment: The assignment variables to link to

        Returns:
            Nested dict: worker_id -> shift_type_id -> IntVar
        """
        shift_counts: dict[str, dict[str, cp_model.IntVar]] = {}

        for worker in self.workers:
            shift_counts[worker.id] = {}
            for shift_type in self.shift_types:
                var_name = f"count_{worker.id}_{shift_type.id}"
                count_var = self.model.new_int_var(0, self.num_periods, var_name)
                shift_counts[worker.id][shift_type.id] = count_var

                # Link count to sum of assignments
                assignment_vars = [
                    assignment[worker.id][period][shift_type.id]
                    for period in range(self.num_periods)
                ]
                self.model.add(count_var == sum(assignment_vars))

        return shift_counts

    def _build_undesirable_total_variables(
        self,
        assignment: dict[str, dict[int, dict[str, cp_model.IntVar]]],
    ) -> dict[str, cp_model.IntVar]:
        """
        Create undesirable shift total variables and link them to assignments.

        Args:
            assignment: The assignment variables to link to

        Returns:
            Dict: worker_id -> IntVar
        """
        undesirable_totals: dict[str, cp_model.IntVar] = {}

        # Calculate max possible undesirable shifts
        num_undesirable_types = len(self._undesirable_shift_ids)
        max_undesirable = self.num_periods * max(1, num_undesirable_types)

        for worker in self.workers:
            var_name = f"undesirable_total_{worker.id}"
            total_var = self.model.new_int_var(0, max_undesirable, var_name)
            undesirable_totals[worker.id] = total_var

            # Link to sum of undesirable shift assignments
            undesirable_vars = []
            for period in range(self.num_periods):
                for shift_type_id in self._undesirable_shift_ids:
                    undesirable_vars.append(assignment[worker.id][period][shift_type_id])

            if undesirable_vars:
                self.model.add(total_var == sum(undesirable_vars))
            else:
                # No undesirable shifts - force total to 0
                self.model.add(total_var == 0)

        return undesirable_totals
