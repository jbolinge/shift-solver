"""Solver module for shift-solver."""

from shift_solver.solver.constraint_registry import (
    ConstraintRegistration,
    ConstraintRegistry,
    register_builtin_constraints,
)
from shift_solver.solver.objective_builder import ObjectiveBuilder, ObjectiveTerm
from shift_solver.solver.result import SolverResult
from shift_solver.solver.shift_solver import ShiftSolver
from shift_solver.solver.solution_extractor import SolutionExtractor
from shift_solver.solver.types import SolverVariables
from shift_solver.solver.variable_builder import VariableBuilder

__all__ = [
    "SolverVariables",
    "VariableBuilder",
    "SolutionExtractor",
    "ObjectiveBuilder",
    "ObjectiveTerm",
    "ShiftSolver",
    "SolverResult",
    "ConstraintRegistry",
    "ConstraintRegistration",
    "register_builtin_constraints",
]
