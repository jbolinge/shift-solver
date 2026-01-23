"""Type definitions for the solver module."""

from dataclasses import dataclass
from typing import Iterator

from ortools.sat.python import cp_model


@dataclass
class SolverVariables:
    """
    Strongly-typed container for all solver variables.

    This provides type-safe access to OR-Tools variables with proper
    error handling and iteration support.

    Attributes:
        assignment: Binary variables for worker-period-shift assignments
            Structure: worker_id -> period_index -> shift_type_id -> IntVar
        shift_counts: Integer variables counting shifts per worker per type
            Structure: worker_id -> shift_type_id -> IntVar
        undesirable_totals: Integer variables for total undesirable shifts per worker
            Structure: worker_id -> IntVar
    """

    assignment: dict[str, dict[int, dict[str, cp_model.IntVar]]]
    shift_counts: dict[str, dict[str, cp_model.IntVar]]
    undesirable_totals: dict[str, cp_model.IntVar]

    def get_assignment_var(
        self, worker_id: str, period: int, shift_type_id: str
    ) -> cp_model.IntVar:
        """
        Type-safe accessor for assignment variables.

        Args:
            worker_id: Worker identifier
            period: Period index (0-indexed)
            shift_type_id: Shift type identifier

        Returns:
            OR-Tools integer variable for the assignment

        Raises:
            KeyError: If variable doesn't exist for the given parameters
        """
        try:
            return self.assignment[worker_id][period][shift_type_id]
        except KeyError as e:
            if worker_id not in self.assignment:
                raise KeyError(f"Worker {worker_id} not found in assignment variables") from e
            if period not in self.assignment[worker_id]:
                raise KeyError(
                    f"Assignment variable not found for worker {worker_id}, period {period}"
                ) from e
            raise KeyError(
                f"Assignment variable not found for worker {worker_id}, "
                f"period {period}, shift type {shift_type_id}"
            ) from e

    def get_shift_count_var(self, worker_id: str, shift_type_id: str) -> cp_model.IntVar:
        """
        Type-safe accessor for shift count variables.

        Args:
            worker_id: Worker identifier
            shift_type_id: Shift type identifier

        Returns:
            OR-Tools integer variable for shift count

        Raises:
            KeyError: If variable doesn't exist
        """
        try:
            return self.shift_counts[worker_id][shift_type_id]
        except KeyError as e:
            if worker_id not in self.shift_counts:
                raise KeyError(f"Worker {worker_id} not found in shift count variables") from e
            raise KeyError(
                f"Shift count variable not found for worker {worker_id}, "
                f"shift type {shift_type_id}"
            ) from e

    def get_undesirable_total_var(self, worker_id: str) -> cp_model.IntVar:
        """
        Type-safe accessor for undesirable shift total variables.

        Args:
            worker_id: Worker identifier

        Returns:
            OR-Tools integer variable for undesirable total

        Raises:
            KeyError: If variable doesn't exist
        """
        try:
            return self.undesirable_totals[worker_id]
        except KeyError as e:
            raise KeyError(
                f"Undesirable total variable not found for worker {worker_id}"
            ) from e

    def all_assignment_vars(
        self,
    ) -> Iterator[tuple[str, int, str, cp_model.IntVar]]:
        """
        Iterate over all assignment variables.

        Yields:
            Tuples of (worker_id, period, shift_type_id, variable)
        """
        for worker_id, periods in self.assignment.items():
            for period, shift_types in periods.items():
                for shift_type_id, var in shift_types.items():
                    yield worker_id, period, shift_type_id, var

    def get_worker_period_vars(
        self, worker_id: str, period: int
    ) -> dict[str, cp_model.IntVar]:
        """
        Get all shift type variables for a worker in a specific period.

        Args:
            worker_id: Worker identifier
            period: Period index

        Returns:
            Dictionary mapping shift_type_id to IntVar

        Raises:
            KeyError: If worker or period doesn't exist
        """
        try:
            return self.assignment[worker_id][period]
        except KeyError as e:
            if worker_id not in self.assignment:
                raise KeyError(f"Worker {worker_id} not found in assignment variables") from e
            raise KeyError(
                f"Period {period} not found for worker {worker_id}"
            ) from e
