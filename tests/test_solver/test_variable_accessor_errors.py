"""Tests for SolverVariables accessor error handling.

scheduler-68: Tests for SolverVariables accessor methods that may silently
fail with KeyError in constraint apply() methods.
"""

from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.models import ShiftType, Worker
from shift_solver.solver.types import SolverVariables
from shift_solver.solver.variable_builder import VariableBuilder


@pytest.fixture
def model() -> cp_model.CpModel:
    """Fresh CP model for each test."""
    return cp_model.CpModel()


@pytest.fixture
def workers() -> list[Worker]:
    """Sample workers."""
    return [
        Worker(id="W001", name="Alice"),
        Worker(id="W002", name="Bob"),
    ]


@pytest.fixture
def shift_types() -> list[ShiftType]:
    """Sample shift types."""
    return [
        ShiftType(
            id="day",
            name="Day Shift",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            workers_required=1,
        ),
        ShiftType(
            id="night",
            name="Night Shift",
            category="night",
            start_time=time(21, 0),
            end_time=time(5, 0),
            duration_hours=8.0,
            workers_required=1,
            is_undesirable=True,
        ),
    ]


@pytest.fixture
def variables(
    model: cp_model.CpModel,
    workers: list[Worker],
    shift_types: list[ShiftType],
) -> SolverVariables:
    """Build solver variables."""
    builder = VariableBuilder(model, workers, shift_types, num_periods=4)
    return builder.build()


class TestGetAssignmentVar:
    """Tests for get_assignment_var accessor."""

    def test_valid_access(self, variables: SolverVariables) -> None:
        """Valid accessor call returns IntVar."""
        var = variables.get_assignment_var("W001", 0, "day")
        assert var is not None
        assert isinstance(var, cp_model.IntVar)

    def test_invalid_worker_id_raises_keyerror(
        self, variables: SolverVariables
    ) -> None:
        """Invalid worker ID raises KeyError."""
        with pytest.raises(KeyError):
            variables.get_assignment_var("INVALID", 0, "day")

    def test_invalid_period_raises_keyerror(self, variables: SolverVariables) -> None:
        """Invalid period index raises KeyError."""
        with pytest.raises(KeyError):
            variables.get_assignment_var("W001", 999, "day")

    def test_invalid_shift_type_raises_keyerror(
        self, variables: SolverVariables
    ) -> None:
        """Invalid shift type ID raises KeyError."""
        with pytest.raises(KeyError):
            variables.get_assignment_var("W001", 0, "nonexistent")

    def test_negative_period_raises_keyerror(self, variables: SolverVariables) -> None:
        """Negative period index raises KeyError."""
        with pytest.raises(KeyError):
            variables.get_assignment_var("W001", -1, "day")

    def test_empty_worker_id_raises_keyerror(self, variables: SolverVariables) -> None:
        """Empty string worker ID raises KeyError."""
        with pytest.raises(KeyError):
            variables.get_assignment_var("", 0, "day")


class TestGetShiftCountVar:
    """Tests for get_shift_count_var accessor."""

    def test_valid_access(self, variables: SolverVariables) -> None:
        """Valid accessor call returns IntVar."""
        var = variables.get_shift_count_var("W001", "day")
        assert var is not None
        assert isinstance(var, cp_model.IntVar)

    def test_invalid_worker_id_raises_keyerror(
        self, variables: SolverVariables
    ) -> None:
        """Invalid worker ID raises KeyError."""
        with pytest.raises(KeyError):
            variables.get_shift_count_var("INVALID", "day")

    def test_invalid_shift_type_raises_keyerror(
        self, variables: SolverVariables
    ) -> None:
        """Invalid shift type ID raises KeyError."""
        with pytest.raises(KeyError):
            variables.get_shift_count_var("W001", "nonexistent")


class TestGetUndesirableTotalVar:
    """Tests for get_undesirable_total_var accessor."""

    def test_valid_access(self, variables: SolverVariables) -> None:
        """Valid accessor call returns IntVar."""
        var = variables.get_undesirable_total_var("W001")
        assert var is not None
        assert isinstance(var, cp_model.IntVar)

    def test_invalid_worker_id_raises_keyerror(
        self, variables: SolverVariables
    ) -> None:
        """Invalid worker ID raises KeyError."""
        with pytest.raises(KeyError):
            variables.get_undesirable_total_var("INVALID")


class TestGetWorkerPeriodVars:
    """Tests for get_worker_period_vars accessor."""

    def test_valid_access(self, variables: SolverVariables) -> None:
        """Valid accessor returns dict of shift_type -> IntVar."""
        vars_dict = variables.get_worker_period_vars("W001", 0)
        assert isinstance(vars_dict, dict)
        assert "day" in vars_dict
        assert "night" in vars_dict

    def test_invalid_worker_id_returns_empty_or_raises(
        self, variables: SolverVariables
    ) -> None:
        """Invalid worker ID behavior - may return empty or raise."""
        # This tests the current behavior
        try:
            result = variables.get_worker_period_vars("INVALID", 0)
            # If it doesn't raise, should return empty dict
            assert result == {}
        except KeyError:
            # Also acceptable behavior
            pass

    def test_invalid_period_returns_empty_or_raises(
        self, variables: SolverVariables
    ) -> None:
        """Invalid period behavior - may return empty or raise."""
        try:
            result = variables.get_worker_period_vars("W001", 999)
            assert result == {}
        except KeyError:
            pass


class TestAllAssignmentVars:
    """Tests for all_assignment_vars iterator."""

    def test_iterates_all_combinations(self, variables: SolverVariables) -> None:
        """Iterator yields all worker-period-shift combinations."""
        all_vars = list(variables.all_assignment_vars())

        # Should have 2 workers * 4 periods * 2 shift types = 16
        assert len(all_vars) == 16

        # Each should be a 4-tuple
        for item in all_vars:
            assert len(item) == 4
            worker_id, period, shift_type_id, var = item
            assert isinstance(worker_id, str)
            assert isinstance(period, int)
            assert isinstance(shift_type_id, str)
            assert isinstance(var, cp_model.IntVar)

    def test_empty_variables_yields_nothing(self) -> None:
        """Empty variables structure yields nothing."""
        empty_vars = SolverVariables(
            assignment={},
            shift_counts={},
            undesirable_totals={},
        )
        all_vars = list(empty_vars.all_assignment_vars())
        assert len(all_vars) == 0


class TestVariableBuilderIntegration:
    """Integration tests for VariableBuilder with edge cases."""

    def test_single_worker_single_shift_single_period(
        self, model: cp_model.CpModel
    ) -> None:
        """Minimal variable setup works correctly."""
        workers = [Worker(id="W001", name="Solo")]
        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        # Should have exactly 1 assignment variable
        all_vars = list(variables.all_assignment_vars())
        assert len(all_vars) == 1

        # Should be accessible
        var = variables.get_assignment_var("W001", 0, "shift")
        assert var is not None

    def test_no_undesirable_shifts_still_creates_totals(
        self, model: cp_model.CpModel
    ) -> None:
        """Workers get undesirable_total vars even with no undesirable shifts."""
        workers = [Worker(id="W001", name="Alice")]
        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=False,  # Not undesirable
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        # Should still have undesirable_total var (even if always 0)
        var = variables.get_undesirable_total_var("W001")
        assert var is not None


class TestConstraintSafeAccess:
    """Tests for safe access patterns used in constraints."""

    def test_try_except_pattern_for_missing_key(
        self, variables: SolverVariables
    ) -> None:
        """Constraints should use try-except for missing keys."""
        # Simulate what constraint code should do
        collected_vars = []
        for worker_id in ["W001", "W002", "INVALID"]:
            try:
                var = variables.get_assignment_var(worker_id, 0, "day")
                collected_vars.append(var)
            except KeyError:
                continue

        # Should only collect valid ones
        assert len(collected_vars) == 2

    def test_get_with_default_pattern(self, variables: SolverVariables) -> None:
        """Alternative: use .get() on underlying dicts with default."""
        # Direct dict access (not recommended but possible)
        result = variables.assignment.get("INVALID", {})
        assert result == {}
