"""ShiftSolver - main orchestrator for shift scheduling optimization."""

import time as time_module
from dataclasses import dataclass
from datetime import date
from typing import Any

from ortools.sat.python import cp_model

from shift_solver.constraints.availability import AvailabilityConstraint
from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.coverage import CoverageConstraint
from shift_solver.constraints.fairness import FairnessConstraint
from shift_solver.constraints.frequency import FrequencyConstraint
from shift_solver.constraints.max_absence import MaxAbsenceConstraint
from shift_solver.constraints.request import RequestConstraint
from shift_solver.constraints.restriction import RestrictionConstraint
from shift_solver.constraints.sequence import SequenceConstraint
from shift_solver.models import (
    Availability,
    Schedule,
    SchedulingRequest,
    ShiftType,
    Worker,
)
from shift_solver.solver.objective_builder import ObjectiveBuilder
from shift_solver.solver.solution_extractor import SolutionExtractor
from shift_solver.solver.types import SolverVariables
from shift_solver.solver.variable_builder import VariableBuilder


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
        requests: list[SchedulingRequest] | None = None,
        constraint_configs: dict[str, ConstraintConfig] | None = None,
    ) -> None:
        """
        Initialize the ShiftSolver.

        Args:
            workers: List of workers to schedule
            shift_types: List of shift types with requirements
            period_dates: List of (start_date, end_date) for each period
            schedule_id: Identifier for the generated schedule
            availabilities: Optional list of availability records
            requests: Optional list of scheduling requests (preferences)
            constraint_configs: Optional dict mapping constraint_id to config

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
        self.requests = requests or []
        self.constraint_configs = constraint_configs or {}
        self.num_periods = len(period_dates)

        # These are set during solve
        self._model: cp_model.CpModel | None = None
        self._variables: SolverVariables | None = None
        self._solver: cp_model.CpSolver | None = None
        self._objective_builder: ObjectiveBuilder | None = None

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
                objective_value=self._solver.ObjectiveValue()
                if hasattr(self._solver, "ObjectiveValue")
                else None,
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

        # Context for all constraints
        constraints_context: dict[str, Any] = {
            "workers": self.workers,
            "shift_types": self.shift_types,
            "num_periods": self.num_periods,
            "availabilities": self.availabilities,
            "period_dates": self.period_dates,
            "requests": self.requests,
        }

        # Initialize objective builder for soft constraints
        self._objective_builder = ObjectiveBuilder(self._model)

        # Hard constraints (always enabled)
        self._apply_hard_constraints(constraints_context)

        # Soft constraints (configurable)
        self._apply_soft_constraints(constraints_context)

        # Build the objective function
        self._objective_builder.build()

    def _get_constraint_config(self, constraint_id: str) -> ConstraintConfig | None:
        """Get config for a constraint, or None for default."""
        return self.constraint_configs.get(constraint_id)

    def _apply_hard_constraints(self, context: dict[str, Any]) -> None:
        """Apply hard constraints."""
        assert self._model is not None
        assert self._variables is not None

        # Coverage constraint
        coverage = CoverageConstraint(
            self._model,
            self._variables,
            self._get_constraint_config("coverage"),
        )
        coverage.apply(**context)

        # Restriction constraint
        restriction = RestrictionConstraint(
            self._model,
            self._variables,
            self._get_constraint_config("restriction"),
        )
        restriction.apply(**context)

        # Availability constraint
        availability = AvailabilityConstraint(
            self._model,
            self._variables,
            self._get_constraint_config("availability"),
        )
        availability.apply(**context)

    def _apply_soft_constraints(self, context: dict[str, Any]) -> None:
        """Apply soft constraints and add them to objective builder."""
        assert self._model is not None
        assert self._variables is not None
        assert self._objective_builder is not None

        # Fairness constraint
        fairness_config = self._get_constraint_config("fairness")
        if fairness_config is None:
            # Default: enabled with weight 1000
            fairness_config = ConstraintConfig(enabled=True, is_hard=False, weight=1000)
        fairness = FairnessConstraint(self._model, self._variables, fairness_config)
        fairness.apply(**context)
        self._objective_builder.add_constraint(fairness)

        # Frequency constraint
        frequency_config = self._get_constraint_config("frequency")
        if frequency_config is None:
            # Default: disabled
            frequency_config = ConstraintConfig(enabled=False)
        frequency = FrequencyConstraint(self._model, self._variables, frequency_config)
        frequency.apply(**context)
        self._objective_builder.add_constraint(frequency)

        # Request constraint
        request_config = self._get_constraint_config("request")
        if request_config is None:
            # Default: enabled if there are requests
            request_config = ConstraintConfig(
                enabled=bool(self.requests), is_hard=False, weight=150
            )
        request_constraint = RequestConstraint(
            self._model, self._variables, request_config
        )
        request_constraint.apply(**context)
        self._objective_builder.add_constraint(request_constraint)

        # Sequence constraint
        sequence_config = self._get_constraint_config("sequence")
        if sequence_config is None:
            # Default: disabled
            sequence_config = ConstraintConfig(enabled=False)
        sequence = SequenceConstraint(self._model, self._variables, sequence_config)
        sequence.apply(**context)
        self._objective_builder.add_constraint(sequence)

        # Max absence constraint
        max_absence_config = self._get_constraint_config("max_absence")
        if max_absence_config is None:
            # Default: disabled
            max_absence_config = ConstraintConfig(enabled=False)
        max_absence = MaxAbsenceConstraint(
            self._model, self._variables, max_absence_config
        )
        max_absence.apply(**context)
        self._objective_builder.add_constraint(max_absence)
