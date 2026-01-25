"""SolverResult dataclass for solver outcomes."""

from dataclasses import dataclass

from shift_solver.models import Schedule


@dataclass
class SolverResult:
    """Result from the solver."""

    success: bool
    schedule: Schedule | None
    status: int
    status_name: str
    solve_time_seconds: float
    objective_value: float | None = None
