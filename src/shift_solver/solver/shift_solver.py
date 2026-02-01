"""ShiftSolver - main orchestrator for shift scheduling optimization."""

import time as time_module
from datetime import date
from typing import Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import (
    Availability,
    SchedulingRequest,
    ShiftType,
    Worker,
)
from shift_solver.solver.constraint_registry import (
    ConstraintRegistry,
    register_builtin_constraints,
)
from shift_solver.solver.objective_builder import ObjectiveBuilder
from shift_solver.solver.result import SolverResult
from shift_solver.solver.solution_extractor import SolutionExtractor
from shift_solver.solver.types import SolverVariables
from shift_solver.solver.variable_builder import VariableBuilder
from shift_solver.validation.feasibility import FeasibilityChecker, FeasibilityResult


class ShiftSolver:
    """
    Main orchestrator for shift scheduling optimization.

    This class coordinates:
    - Variable creation via VariableBuilder
    - Constraint application via constraint classes
    - Solution extraction via SolutionExtractor

    Constraints are loaded from the ConstraintRegistry, allowing
    for dynamic constraint discovery and configuration.

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

        # Ensure constraints are registered
        register_builtin_constraints()

    def solve(self, time_limit_seconds: int = 300) -> SolverResult:
        """
        Solve the shift scheduling problem.

        Args:
            time_limit_seconds: Maximum time for solving in seconds

        Returns:
            SolverResult with success status, schedule, and statistics
        """
        start_time = time_module.time()

        # Run pre-solve feasibility check
        feasibility_result = self._check_feasibility()
        if not feasibility_result.is_feasible:
            return SolverResult(
                success=False,
                schedule=None,
                status=-1,  # Custom status for pre-solve failure
                status_name="INFEASIBLE_PRE_SOLVE",
                solve_time_seconds=time_module.time() - start_time,
                feasibility_issues=feasibility_result.issues,
            )

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

        # Apply hard constraints from registry
        self._apply_hard_constraints(constraints_context)

        # Apply soft constraints from registry
        self._apply_soft_constraints(constraints_context)

        # Build the objective function
        self._objective_builder.build()

    def _get_constraint_config(
        self, constraint_id: str, default: ConstraintConfig
    ) -> ConstraintConfig:
        """Get config for a constraint, using default if not specified."""
        return self.constraint_configs.get(constraint_id, default)

    def _apply_hard_constraints(self, context: dict[str, Any]) -> None:
        """Apply hard constraints from registry."""
        assert self._model is not None
        assert self._variables is not None

        for constraint_id, registration in ConstraintRegistry.get_hard_constraints().items():
            config = self._get_constraint_config(
                constraint_id, registration.default_config
            )
            if not config.enabled:
                continue

            constraint = registration.constraint_class(
                self._model,
                self._variables,
                config,
            )
            constraint.apply(**context)

    def _apply_soft_constraints(self, context: dict[str, Any]) -> None:
        """Apply soft constraints from registry and add them to objective builder."""
        assert self._model is not None
        assert self._variables is not None
        assert self._objective_builder is not None

        for constraint_id, registration in ConstraintRegistry.get_soft_constraints().items():
            # Get config with special handling for request constraint
            default_config = registration.default_config
            if constraint_id == "request" and not default_config.enabled:
                # Enable request constraint by default if there are requests
                default_config = ConstraintConfig(
                    enabled=bool(self.requests),
                    is_hard=False,
                    weight=default_config.weight,
                )

            config = self._get_constraint_config(constraint_id, default_config)
            if not config.enabled:
                continue

            constraint = registration.constraint_class(
                self._model,
                self._variables,
                config,
            )
            constraint.apply(**context)
            self._objective_builder.add_constraint(constraint)

    def _check_feasibility(self) -> FeasibilityResult:
        """Run pre-solve feasibility check."""
        checker = FeasibilityChecker(
            workers=self.workers,
            shift_types=self.shift_types,
            period_dates=self.period_dates,
            availabilities=self.availabilities,
        )
        return checker.check()
