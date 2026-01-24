"""Tests for custom exception hierarchy."""

import pytest

from shift_solver.utils.exceptions import (
    ShiftSolverError,
    ConfigurationError,
    ValidationError,
    FeasibilityError,
    SolverError,
    DataImportError,
)


class TestExceptionHierarchy:
    """Test exception hierarchy structure."""

    def test_shift_solver_error_is_base_exception(self) -> None:
        """ShiftSolverError should be the base exception."""
        with pytest.raises(ShiftSolverError):
            raise ShiftSolverError("test error")

    def test_configuration_error_inherits_from_base(self) -> None:
        """ConfigurationError should inherit from ShiftSolverError."""
        with pytest.raises(ShiftSolverError):
            raise ConfigurationError("config error")

    def test_validation_error_inherits_from_base(self) -> None:
        """ValidationError should inherit from ShiftSolverError."""
        with pytest.raises(ShiftSolverError):
            raise ValidationError("validation error")

    def test_feasibility_error_inherits_from_validation(self) -> None:
        """FeasibilityError should inherit from ValidationError."""
        with pytest.raises(ValidationError):
            raise FeasibilityError("feasibility error")
        with pytest.raises(ShiftSolverError):
            raise FeasibilityError("feasibility error")

    def test_solver_error_inherits_from_base(self) -> None:
        """SolverError should inherit from ShiftSolverError."""
        with pytest.raises(ShiftSolverError):
            raise SolverError("solver error")

    def test_data_import_error_inherits_from_base(self) -> None:
        """DataImportError should inherit from ShiftSolverError."""
        with pytest.raises(ShiftSolverError):
            raise DataImportError("import error")


class TestExceptionMessages:
    """Test exception message handling."""

    def test_error_message_preserved(self) -> None:
        """Exception message should be preserved."""
        msg = "Something went wrong"
        error = ShiftSolverError(msg)
        assert str(error) == msg

    def test_configuration_error_with_field(self) -> None:
        """ConfigurationError can include field name."""
        error = ConfigurationError("Invalid value", field="max_time_seconds")
        assert error.field == "max_time_seconds"
        assert "Invalid value" in str(error)

    def test_validation_error_with_details(self) -> None:
        """ValidationError can include details list."""
        details = ["Issue 1", "Issue 2"]
        error = ValidationError("Multiple issues found", details=details)
        assert error.details == details
        assert len(error.details) == 2

    def test_feasibility_error_with_issues(self) -> None:
        """FeasibilityError can include feasibility issues."""
        issues = [
            {"type": "coverage", "message": "Not enough workers"},
            {"type": "availability", "message": "All workers unavailable"},
        ]
        error = FeasibilityError("Infeasible problem", issues=issues)
        assert error.issues == issues

    def test_solver_error_with_status(self) -> None:
        """SolverError can include solver status."""
        error = SolverError("No solution", status="INFEASIBLE", status_code=3)
        assert error.status == "INFEASIBLE"
        assert error.status_code == 3

    def test_data_import_error_with_source(self) -> None:
        """DataImportError can include source info."""
        error = DataImportError("Parse error", source="workers.csv", line=42)
        assert error.source == "workers.csv"
        assert error.line == 42
