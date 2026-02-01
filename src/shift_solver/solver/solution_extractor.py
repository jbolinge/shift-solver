"""SolutionExtractor - extracts schedules from solver solutions."""

from datetime import date
from typing import Any

from ortools.sat.python import cp_model

from shift_solver.models import (
    PeriodAssignment,
    Schedule,
    ShiftInstance,
    ShiftType,
    Worker,
)
from shift_solver.solver.types import SolverVariables


def _derive_period_type(period_dates: list[tuple[date, date]]) -> str:
    """
    Derive period type from the duration of periods.

    Args:
        period_dates: List of (start_date, end_date) tuples for each period

    Returns:
        Period type string: "day", "week", "biweek", "month", or "custom"
    """
    if not period_dates:
        return "week"  # Default fallback

    # Calculate the duration of the first period
    start, end = period_dates[0]
    duration = (end - start).days + 1  # +1 to include both start and end

    # Map duration to period type
    if duration == 1:
        return "day"
    elif duration == 7:
        return "week"
    elif duration == 14:
        return "biweek"
    elif 28 <= duration <= 31:
        return "month"
    else:
        return "custom"


class SolutionExtractor:
    """
    Extracts complete schedules from OR-Tools CP-SAT solver solutions.

    This class handles extraction of assignments from the solver and
    constructs the domain model objects (Schedule, PeriodAssignment, ShiftInstance).
    """

    def __init__(
        self,
        solver: cp_model.CpSolver,
        variables: SolverVariables,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
        schedule_id: str,
    ) -> None:
        """
        Initialize the solution extractor.

        Args:
            solver: OR-Tools CP-SAT solver with solution
            variables: SolverVariables containing all solver variables
            workers: List of workers
            shift_types: List of shift types
            period_dates: List of (start_date, end_date) for each period
            schedule_id: Identifier for the schedule

        Raises:
            ValueError: If required parameters are missing
        """
        if solver is None:
            raise ValueError("solver cannot be None")
        if variables is None:
            raise ValueError("variables cannot be None")

        self.solver = solver
        self.variables = variables
        self.workers = workers
        self.shift_types = shift_types
        self.period_dates = period_dates
        self.schedule_id = schedule_id

        # Build lookup maps
        self._worker_map = {w.id: w for w in workers}
        self._shift_type_map = {st.id: st for st in shift_types}

    def extract(self) -> Schedule:
        """
        Extract complete schedule from solver solution.

        Returns:
            Schedule object with all assignments and statistics
        """
        num_periods = len(self.period_dates)

        # Extract period assignments
        periods: list[PeriodAssignment] = []
        for period_idx in range(num_periods):
            period_start, period_end = self.period_dates[period_idx]
            period_assignment = self._extract_period(
                period_idx, period_start, period_end
            )
            periods.append(period_assignment)

        # Create schedule with derived period type
        period_type = _derive_period_type(self.period_dates)
        schedule = Schedule(
            schedule_id=self.schedule_id,
            start_date=self.period_dates[0][0],
            end_date=self.period_dates[-1][1],
            period_type=period_type,
            periods=periods,
            workers=self.workers,
            shift_types=self.shift_types,
        )

        # Calculate and add statistics
        self._add_statistics(schedule)

        return schedule

    def _extract_period(
        self,
        period_idx: int,
        period_start: date,
        period_end: date,
    ) -> PeriodAssignment:
        """
        Extract assignments for a single period.

        Args:
            period_idx: Period index
            period_start: Start date of period
            period_end: End date of period

        Returns:
            PeriodAssignment with all worker assignments
        """
        period_assignment = PeriodAssignment(
            period_index=period_idx,
            period_start=period_start,
            period_end=period_end,
        )

        # Extract assignments for each worker
        for worker in self.workers:
            worker_shifts = self._extract_worker_shifts(
                worker.id, period_idx, period_start
            )
            if worker_shifts:
                period_assignment.assignments[worker.id] = worker_shifts

        return period_assignment

    def _extract_worker_shifts(
        self,
        worker_id: str,
        period_idx: int,
        period_start: date,
    ) -> list[ShiftInstance]:
        """
        Extract all shift assignments for a worker in a period.

        Args:
            worker_id: Worker identifier
            period_idx: Period index
            period_start: Start date of period

        Returns:
            List of ShiftInstance objects for assigned shifts
        """
        shifts: list[ShiftInstance] = []

        for shift_type in self.shift_types:
            try:
                var = self.variables.get_assignment_var(
                    worker_id, period_idx, shift_type.id
                )
                if self.solver.Value(var) == 1:
                    shift_instance = ShiftInstance(
                        shift_type_id=shift_type.id,
                        period_index=period_idx,
                        date=period_start,
                        worker_id=worker_id,
                    )
                    shifts.append(shift_instance)
            except KeyError:
                # Variable doesn't exist - skip
                continue

        return shifts

    def _add_statistics(self, schedule: Schedule) -> None:
        """
        Calculate and add statistics to the schedule.

        Args:
            schedule: Schedule to add statistics to
        """
        statistics: dict[str, dict[str, Any]] = {}

        for worker in self.workers:
            worker_stats: dict[str, Any] = {
                "total_shifts": 0,
                "periods_worked": 0,
            }

            # Add counter for each shift type
            for shift_type in self.shift_types:
                worker_stats[shift_type.id] = 0

            # Count assignments across all periods
            for period in schedule.periods:
                worker_shifts = period.get_worker_shifts(worker.id)
                if worker_shifts:
                    worker_stats["periods_worked"] += 1
                    worker_stats["total_shifts"] += len(worker_shifts)

                    for shift in worker_shifts:
                        if shift.shift_type_id in worker_stats:
                            worker_stats[shift.shift_type_id] += 1

            statistics[worker.id] = worker_stats

        schedule.statistics = statistics
