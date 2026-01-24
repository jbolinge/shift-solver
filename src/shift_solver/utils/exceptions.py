"""Custom exception hierarchy for shift-solver."""

from typing import Any


class ShiftSolverError(Exception):
    """Base exception for all shift-solver errors."""

    pass


class ConfigurationError(ShiftSolverError):
    """Error in configuration file or settings."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class ValidationError(ShiftSolverError):
    """Error during data validation."""

    def __init__(self, message: str, details: list[str] | None = None) -> None:
        super().__init__(message)
        self.details = details or []


class FeasibilityError(ValidationError):
    """Error indicating an infeasible scheduling problem."""

    def __init__(
        self, message: str, issues: list[dict[str, Any]] | None = None
    ) -> None:
        super().__init__(message)
        self.issues = issues or []


class SolverError(ShiftSolverError):
    """Error during solver execution."""

    def __init__(
        self,
        message: str,
        status: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.status_code = status_code


class DataImportError(ShiftSolverError):
    """Error during data import from external files."""

    def __init__(
        self,
        message: str,
        source: str | None = None,
        line: int | None = None,
    ) -> None:
        super().__init__(message)
        self.source = source
        self.line = line
