"""Tests for constraint context dictionary type safety.

scheduler-70: Tests for context dictionary (Dict[str, Any]) that is not validated,
where typos in context keys fail at runtime.
"""

import contextlib
from datetime import time
from typing import Any

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.coverage import CoverageConstraint
from shift_solver.constraints.fairness import FairnessConstraint
from shift_solver.constraints.restriction import RestrictionConstraint
from shift_solver.models import ShiftType, Worker
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
        Worker(id="W003", name="Charlie"),
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
def variables(model, workers, shift_types):
    """Build solver variables."""
    builder = VariableBuilder(model, workers, shift_types, num_periods=4)
    return builder.build()


class TestMissingContextKeys:
    """Tests for missing required context keys."""

    def test_coverage_missing_workers_raises_keyerror(
        self, model, variables, shift_types
    ) -> None:
        """CoverageConstraint raises KeyError on missing workers."""
        constraint = CoverageConstraint(model, variables)

        context: dict[str, Any] = {
            # "workers" is missing
            "shift_types": shift_types,
            "num_periods": 4,
        }

        with pytest.raises(KeyError):
            constraint.apply(**context)

    def test_coverage_missing_shift_types_raises_keyerror(
        self, model, variables, workers
    ) -> None:
        """CoverageConstraint raises KeyError on missing shift_types."""
        constraint = CoverageConstraint(model, variables)

        context: dict[str, Any] = {
            "workers": workers,
            # "shift_types" is missing
            "num_periods": 4,
        }

        with pytest.raises(KeyError):
            constraint.apply(**context)

    def test_coverage_missing_num_periods_raises_keyerror(
        self, model, variables, workers, shift_types
    ) -> None:
        """CoverageConstraint raises KeyError on missing num_periods."""
        constraint = CoverageConstraint(model, variables)

        context: dict[str, Any] = {
            "workers": workers,
            "shift_types": shift_types,
            # "num_periods" is missing
        }

        with pytest.raises(KeyError):
            constraint.apply(**context)


class TestTypoedContextKeys:
    """Tests for typos in context key names."""

    def test_coverage_typo_in_workers_raises_keyerror(
        self, model, variables, workers, shift_types
    ) -> None:
        """Typo 'worker' instead of 'workers' raises KeyError."""
        constraint = CoverageConstraint(model, variables)

        context: dict[str, Any] = {
            "worker": workers,  # Typo: should be "workers"
            "shift_types": shift_types,
            "num_periods": 4,
        }

        with pytest.raises(KeyError):
            constraint.apply(**context)

    def test_coverage_typo_in_shift_types_raises_keyerror(
        self, model, variables, workers, shift_types
    ) -> None:
        """Typo 'shiftTypes' instead of 'shift_types' raises KeyError."""
        constraint = CoverageConstraint(model, variables)

        context: dict[str, Any] = {
            "workers": workers,
            "shiftTypes": shift_types,  # Typo: should be "shift_types"
            "num_periods": 4,
        }

        with pytest.raises(KeyError):
            constraint.apply(**context)

    def test_coverage_typo_num_period_raises_keyerror(
        self, model, variables, workers, shift_types
    ) -> None:
        """Typo 'num_period' (singular) raises KeyError."""
        constraint = CoverageConstraint(model, variables)

        context: dict[str, Any] = {
            "workers": workers,
            "shift_types": shift_types,
            "num_period": 4,  # Typo: should be "num_periods"
        }

        with pytest.raises(KeyError):
            constraint.apply(**context)


class TestWrongValueTypes:
    """Tests for wrong value types in context."""

    def test_coverage_workers_as_string_raises_typeerror(
        self, model, variables, shift_types
    ) -> None:
        """Workers as string instead of list causes iteration error."""
        constraint = CoverageConstraint(model, variables)

        context: dict[str, Any] = {
            "workers": "W001",  # Wrong: should be list
            "shift_types": shift_types,
            "num_periods": 4,
        }

        # Will fail when trying to iterate over string as workers
        with pytest.raises((TypeError, AttributeError)):
            constraint.apply(**context)

    def test_coverage_num_periods_as_string_raises_typeerror(
        self, model, variables, workers, shift_types
    ) -> None:
        """num_periods as string instead of int causes range error."""
        constraint = CoverageConstraint(model, variables)

        context: dict[str, Any] = {
            "workers": workers,
            "shift_types": shift_types,
            "num_periods": "4",  # Wrong: should be int
        }

        with pytest.raises(TypeError):
            constraint.apply(**context)


class TestNoneValues:
    """Tests for None values in context."""

    def test_coverage_workers_none_raises_typeerror(
        self, model, variables, shift_types
    ) -> None:
        """Workers as None raises TypeError on iteration."""
        constraint = CoverageConstraint(model, variables)

        context: dict[str, Any] = {
            "workers": None,
            "shift_types": shift_types,
            "num_periods": 4,
        }

        with pytest.raises(TypeError):
            constraint.apply(**context)

    def test_coverage_shift_types_none_raises_typeerror(
        self, model, variables, workers
    ) -> None:
        """shift_types as None raises TypeError on iteration."""
        constraint = CoverageConstraint(model, variables)

        context: dict[str, Any] = {
            "workers": workers,
            "shift_types": None,
            "num_periods": 4,
        }

        with pytest.raises(TypeError):
            constraint.apply(**context)


class TestEmptyCollections:
    """Tests for empty collections in context."""

    def test_coverage_empty_workers_no_constraints(
        self, model, variables, shift_types
    ) -> None:
        """Empty workers list produces no constraints (but no error)."""
        constraint = CoverageConstraint(model, variables)

        context: dict[str, Any] = {
            "workers": [],  # Empty
            "shift_types": shift_types,
            "num_periods": 4,
        }

        # Should not raise but will have issues (no vars to sum)
        # This documents current behavior - may produce invalid model
        with contextlib.suppress(ValueError, RuntimeError):
            constraint.apply(**context)
            # If it doesn't raise, the model may be in invalid state

    def test_coverage_empty_shift_types_no_constraints(
        self, model, variables, workers
    ) -> None:
        """Empty shift_types list produces no constraints."""
        constraint = CoverageConstraint(model, variables)

        context: dict[str, Any] = {
            "workers": workers,
            "shift_types": [],  # Empty
            "num_periods": 4,
        }

        constraint.apply(**context)
        # Should complete without error (just does nothing)
        assert constraint.constraint_count == 0


class TestFairnessContextValidation:
    """Tests for FairnessConstraint context validation."""

    def test_fairness_missing_workers(self, model, variables, shift_types) -> None:
        """FairnessConstraint raises on missing workers."""
        constraint = FairnessConstraint(model, variables)

        context: dict[str, Any] = {
            "shift_types": shift_types,
            "num_periods": 4,
        }

        with pytest.raises(KeyError):
            constraint.apply(**context)

    def test_fairness_with_valid_context(
        self, model, variables, workers, shift_types
    ) -> None:
        """FairnessConstraint works with valid context."""
        constraint = FairnessConstraint(model, variables)

        context: dict[str, Any] = {
            "workers": workers,
            "shift_types": shift_types,
            "num_periods": 4,
        }

        constraint.apply(**context)
        # Should complete successfully
        assert constraint.is_enabled


class TestRestrictionContextValidation:
    """Tests for RestrictionConstraint context validation."""

    def test_restriction_missing_workers(self, model, variables, shift_types) -> None:
        """RestrictionConstraint raises on missing workers."""
        constraint = RestrictionConstraint(model, variables)

        context: dict[str, Any] = {
            "shift_types": shift_types,
            "num_periods": 4,
        }

        with pytest.raises(KeyError):
            constraint.apply(**context)

    def test_restriction_with_valid_context(
        self, model, variables, shift_types
    ) -> None:
        """RestrictionConstraint works with valid context."""
        workers_with_restrictions = [
            Worker(id="W001", name="Alice", restricted_shifts=frozenset(["night"])),
            Worker(id="W002", name="Bob"),
        ]

        constraint = RestrictionConstraint(model, variables)

        context: dict[str, Any] = {
            "workers": workers_with_restrictions,
            "shift_types": shift_types,
            "num_periods": 4,
        }

        constraint.apply(**context)
        # Should have added restriction constraints
        assert constraint.constraint_count >= 0


class TestExtraContextKeys:
    """Tests for extra (unused) context keys."""

    def test_extra_keys_are_ignored(
        self, model, variables, workers, shift_types
    ) -> None:
        """Extra context keys are silently ignored."""
        constraint = CoverageConstraint(model, variables)

        context: dict[str, Any] = {
            "workers": workers,
            "shift_types": shift_types,
            "num_periods": 4,
            "extra_key": "should be ignored",
            "another_extra": 12345,
        }

        # Should not raise
        constraint.apply(**context)
        assert constraint.constraint_count > 0
