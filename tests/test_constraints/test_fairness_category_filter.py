"""Tests for fairness constraint category filter validation.

scheduler-66: Tests for fairness constraint category filter that may silently
ignore invalid categories without warning or error.
"""

from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.fairness import FairnessConstraint
from shift_solver.models import ShiftType, Worker
from shift_solver.solver.types import SolverVariables
from shift_solver.solver.variable_builder import VariableBuilder


@pytest.fixture
def model() -> cp_model.CpModel:
    """Fresh CP model for each test."""
    return cp_model.CpModel()


@pytest.fixture
def workers() -> list[Worker]:
    """Sample workers for testing."""
    return [
        Worker(id="W001", name="Alice"),
        Worker(id="W002", name="Bob"),
        Worker(id="W003", name="Charlie"),
        Worker(id="W004", name="Diana"),
    ]


@pytest.fixture
def shift_types() -> list[ShiftType]:
    """Sample shift types with different categories."""
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
        ShiftType(
            id="weekend",
            name="Weekend Shift",
            category="weekend",
            start_time=time(10, 0),
            end_time=time(18, 0),
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


class TestValidCategoryFilter:
    """Tests for valid category filter configurations."""

    def test_single_valid_category_applied(
        self, model: cp_model.CpModel, variables: SolverVariables, workers, shift_types
    ) -> None:
        """Fairness applies only to specified valid category."""
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"categories": ["night"]},
        )

        constraint = FairnessConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Constraint should have been applied
        assert constraint.constraint_count > 0
        # Should have created violation variables
        assert len(constraint._violation_variables) > 0

    def test_multiple_valid_categories_applied(
        self, model: cp_model.CpModel, variables: SolverVariables, workers, shift_types
    ) -> None:
        """Fairness applies to multiple specified categories."""
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"categories": ["night", "weekend"]},
        )

        constraint = FairnessConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Should have constraints
        assert constraint.constraint_count > 0

    def test_no_categories_uses_is_undesirable(
        self, model: cp_model.CpModel, variables: SolverVariables, workers, shift_types
    ) -> None:
        """Without categories, uses is_undesirable flag."""
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            # No categories parameter
        )

        constraint = FairnessConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Should have constraints based on is_undesirable
        assert constraint.constraint_count > 0


class TestInvalidCategoryFilter:
    """Tests for invalid category filter handling."""

    def test_invalid_category_name_no_error(
        self, model: cp_model.CpModel, variables: SolverVariables, workers, shift_types
    ) -> None:
        """Invalid category name doesn't raise error but may produce no effect."""
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"categories": ["nonexistent_category"]},
        )

        constraint = FairnessConstraint(model, variables, config)
        # Should not raise
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # With invalid category, no shifts match - no constraints added
        # This documents current behavior: silent skip
        # Ideally should warn or error
        assert constraint.constraint_count == 0

    def test_mixed_valid_invalid_categories(
        self, model: cp_model.CpModel, variables: SolverVariables, workers, shift_types
    ) -> None:
        """Mix of valid and invalid categories - valid ones work."""
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"categories": ["night", "invalid_category"]},
        )

        constraint = FairnessConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Should have constraints for the valid "night" category
        assert constraint.constraint_count > 0

    def test_empty_categories_list_falls_back_to_undesirable(
        self, model: cp_model.CpModel, variables: SolverVariables, workers, shift_types
    ) -> None:
        """Empty categories list falls back to is_undesirable behavior."""
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"categories": []},
        )

        constraint = FairnessConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Empty categories list is truthy but empty, so falls back to is_undesirable
        # This documents current behavior - empty list is treated as "no filter"
        # and uses is_undesirable instead
        assert constraint.constraint_count > 0  # Uses is_undesirable fallback


class TestCategoryCaseSensitivity:
    """Tests for category name case sensitivity."""

    def test_category_is_case_sensitive(
        self, model: cp_model.CpModel, variables: SolverVariables, workers, shift_types
    ) -> None:
        """Category matching is case-sensitive."""
        # Shift type has category "night" (lowercase)
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"categories": ["Night"]},  # Capital N
        )

        constraint = FairnessConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Should not match due to case difference
        # This documents current behavior
        assert constraint.constraint_count == 0

    def test_exact_case_matches(
        self, model: cp_model.CpModel, variables: SolverVariables, workers, shift_types
    ) -> None:
        """Exact case matching works correctly."""
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"categories": ["night"]},  # lowercase
        )

        constraint = FairnessConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Should match with exact case
        assert constraint.constraint_count > 0


class TestCategoryWithSingleWorker:
    """Tests for category filter with single worker edge case."""

    def test_single_worker_skips_fairness(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """Single worker means no fairness to balance."""
        workers = [Worker(id="W001", name="Solo")]
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"categories": ["night"]},
        )

        constraint = FairnessConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=4)

        # Should return early - no fairness with single worker
        assert constraint.constraint_count == 0


class TestCategorySolverIntegration:
    """Integration tests with actual solving."""

    def test_category_filter_affects_solution(
        self, model: cp_model.CpModel, workers, shift_types
    ) -> None:
        """Category filter should affect the optimization objective."""
        builder = VariableBuilder(model, workers, shift_types, num_periods=2)
        variables = builder.build()

        # Only balance "weekend" shifts
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"categories": ["weekend"]},
        )

        constraint = FairnessConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=2)

        # Add coverage constraints
        for period in range(2):
            for st in shift_types:
                assignment_vars = [
                    variables.get_assignment_var(w.id, period, st.id)
                    for w in workers
                ]
                model.add(sum(assignment_vars) == st.workers_required)

        # Minimize spread (from violation variables)
        if constraint._violation_variables:
            spread = constraint._violation_variables.get("spread")
            if spread is not None:
                model.minimize(spread)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
