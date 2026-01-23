"""ShiftSolver - main orchestrator for shift scheduling optimization."""

import time as time_module
from dataclasses import dataclass
from datetime import date

from ortools.sat.python import cp_model

from shift_solver.models import Worker, ShiftType, Availability, Schedule
from shift_solver.solver.types import SolverVariables
from shift_solver.solver.variable_builder import VariableBuilder
from shift_solver.solver.solution_extractor import SolutionExtractor
from shift_solver.constraints.coverage import CoverageConstraint
from shift_solver.constraints.restriction import RestrictionConstraint
from shift_solver.constraints.availability import AvailabilityConstraint


@dataclass
class SolverResult:
    """Result from the solver."""

    success: bool
    schedule: Schedule | None
    status: int
    status_name: str
    solve_time_seconds: float
    objective_value: float | None = None


class ShiftSolver:
    """
    Main orchestrator for shift scheduling optimization.

    This class coordinates:
    - Variable creation via VariableBuilder
    - Constraint application via constraint classes
    - Solution extraction via SolutionExtractor

    Usage:
        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="SCH-001",
        )
        result = solver.solve(time_limit_seconds=300)
        if result.success:
            schedule = result.schedule
    """

    def __init__(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
        schedule_id: str,
        availabilities: list[Availability] | None = None,
    ) -> None:
        """
        Initialize the ShiftSolver.

        Args:
            workers: List of workers to schedule
            shift_types: List of shift types with requirements
            period_dates: List of (start_date, end_date) for each period
            schedule_id: Identifier for the generated schedule
            availabilities: Optional list of availability records

        Raises:
            ValueError: If required parameters are invalid
        """
        if not workers:
            raise ValueError("workers list cannot be empty")
        if not shift_types:
            raise ValueError("shift_types list cannot be empty")
        if not period_dates:
            raise ValueError("period_dates list cannot be empty")

        self.workers = workers
        self.shift_types = shift_types
        self.period_dates = period_dates
        self.schedule_id = schedule_id
        self.availabilities = availabilities or []
        self.num_periods = len(period_dates)

        # These are set during solve
        self._model: cp_model.CpModel | None = None
        self._variables: SolverVariables | None = None
        self._solver: cp_model.CpSolver | None = None

    def solve(self, time_limit_seconds: int = 300) -> SolverResult:
        """
        Solve the shift scheduling problem.

        Args:
            time_limit_seconds: Maximum time for solving in seconds

        Returns:
            SolverResult with success status, schedule, and statistics
        """
        start_time = time_module.time()

        # Create model and variables
        self._model = cp_model.CpModel()
        builder = VariableBuilder(
            model=self._model,
            workers=self.workers,
            shift_types=self.shift_types,
            num_periods=self.num_periods,
        )
        self._variables = builder.build()

        # Apply constraints
        self._apply_constraints()

        # Create and configure solver
        self._solver = cp_model.CpSolver()
        self._solver.parameters.max_time_in_seconds = time_limit_seconds

        # Solve
        status = self._solver.Solve(self._model)
        solve_time = time_module.time() - start_time

        # Check result
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            # Extract schedule
            extractor = SolutionExtractor(
                solver=self._solver,
                variables=self._variables,
                workers=self.workers,
                shift_types=self.shift_types,
                period_dates=self.period_dates,
                schedule_id=self.schedule_id,
            )
            schedule = extractor.extract()

            return SolverResult(
                success=True,
                schedule=schedule,
                status=status,
                status_name=self._solver.StatusName(status),
                solve_time_seconds=solve_time,
                objective_value=self._solver.ObjectiveValue() if hasattr(self._solver, 'ObjectiveValue') else None,
            )
        else:
            return SolverResult(
                success=False,
                schedule=None,
                status=status,
                status_name=self._solver.StatusName(status),
                solve_time_seconds=solve_time,
            )

    def _apply_constraints(self) -> None:
        """Apply all constraints to the model."""
        assert self._model is not None
        assert self._variables is not None

        # Hard constraints
        constraints_context = {
            "workers": self.workers,
            "shift_types": self.shift_types,
            "num_periods": self.num_periods,
            "availabilities": self.availabilities,
            "period_dates": self.period_dates,
        }

        # Coverage constraint
        coverage = CoverageConstraint(self._model, self._variables)
        coverage.apply(**constraints_context)

        # Restriction constraint
        restriction = RestrictionConstraint(self._model, self._variables)
        restriction.apply(**constraints_context)

        # Availability constraint
        availability = AvailabilityConstraint(self._model, self._variables)
        availability.apply(**constraints_context)
