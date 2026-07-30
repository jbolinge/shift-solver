"""Tests for skills constraint."""

from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.coverage import CoverageConstraint
from shift_solver.constraints.skills import SkillsConstraint
from shift_solver.models import ShiftType, Worker
from shift_solver.solver import VariableBuilder


class TestSkillsConstraint:
    """Tests for SkillsConstraint."""

    @pytest.fixture
    def model(self) -> cp_model.CpModel:
        """Create a fresh CP model."""
        return cp_model.CpModel()

    @pytest.fixture
    def shift_types(self) -> list[ShiftType]:
        """Create shift types, one requiring a skill and one that doesn't."""
        return [
            ShiftType(
                id="icu",
                name="ICU Shift",
                category="specialty",
                start_time=time(7, 0),
                end_time=time(19, 0),
                duration_hours=12.0,
                workers_required=1,
                required_attributes={"certified": "icu"},
            ),
            ShiftType(
                id="general",
                name="General Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

    def test_unqualified_worker_blocked(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """Worker without required attribute cannot be assigned to skilled shift."""
        workers = [
            Worker(id="W001", name="Alice", attributes={}),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = SkillsConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        assert solver.Value(variables.get_assignment_var("W001", 0, "icu")) == 0

    def test_qualified_worker_allowed(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """Worker with matching attribute may be assigned to skilled shift."""
        workers = [
            Worker(id="W001", name="Alice", attributes={"certified": "icu"}),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = SkillsConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        model.add(variables.get_assignment_var("W001", 0, "icu") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        assert solver.Value(variables.get_assignment_var("W001", 0, "icu")) == 1

    def test_mismatched_attribute_value_blocked(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """Worker with the key but wrong value still does not qualify."""
        workers = [
            Worker(id="W001", name="Alice", attributes={"certified": "ward"}),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = SkillsConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        assert solver.Value(variables.get_assignment_var("W001", 0, "icu")) == 0

    def test_unconstrained_shift_type_allows_any_worker(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """Shift types with empty required_attributes are unconstrained."""
        workers = [
            Worker(id="W001", name="Alice", attributes={}),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = SkillsConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        model.add(variables.get_assignment_var("W001", 0, "general") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        assert solver.Value(variables.get_assignment_var("W001", 0, "general")) == 1

    def test_multiple_required_attributes_all_must_match(
        self, model: cp_model.CpModel
    ) -> None:
        """A worker must satisfy ALL required key/value pairs, not just some."""
        shift_types = [
            ShiftType(
                id="specialty",
                name="Specialty Shift",
                category="specialty",
                start_time=time(7, 0),
                end_time=time(19, 0),
                duration_hours=12.0,
                workers_required=1,
                required_attributes={"certified": "icu", "language": "es"},
            ),
        ]
        workers = [
            # Has one but not the other required attribute
            Worker(id="W001", name="Alice", attributes={"certified": "icu"}),
            # Has both
            Worker(
                id="W002",
                name="Bob",
                attributes={"certified": "icu", "language": "es"},
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = SkillsConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        assert solver.Value(variables.get_assignment_var("W001", 0, "specialty")) == 0
        # W002 is not forced on, but should be allowed if we try
        model.add(variables.get_assignment_var("W002", 0, "specialty") == 1)
        solver2 = cp_model.CpSolver()
        status2 = solver2.Solve(model)
        assert status2 in [cp_model.OPTIMAL, cp_model.FEASIBLE]

    def test_extra_worker_attributes_do_not_matter(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """Extra worker attributes beyond what's required don't block eligibility."""
        workers = [
            Worker(
                id="W001",
                name="Alice",
                attributes={"certified": "icu", "seniority": "junior"},
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = SkillsConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        model.add(variables.get_assignment_var("W001", 0, "icu") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

    def test_disabled_allows_unqualified_assignment(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """Disabled skills constraint does not block unqualified assignment."""
        workers = [
            Worker(id="W001", name="Alice", attributes={}),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(enabled=False)
        constraint = SkillsConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        model.add(variables.get_assignment_var("W001", 0, "icu") == 1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        assert constraint.constraint_count == 0

    def test_constraint_count_across_periods(
        self, model: cp_model.CpModel, shift_types: list[ShiftType]
    ) -> None:
        """One constraint per unqualified worker per period for skilled shifts."""
        workers = [
            Worker(id="W001", name="Alice", attributes={}),
            Worker(id="W002", name="Bob", attributes={"certified": "icu"}),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=3)
        variables = builder.build()

        constraint = SkillsConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        # Only W001 is unqualified for "icu"; general shift has no requirements
        # 1 unqualified worker * 3 periods = 3 constraints
        assert constraint.constraint_count == 3

    def test_interaction_with_coverage_infeasible_when_no_qualified_worker(
        self, model: cp_model.CpModel
    ) -> None:
        """Coverage is infeasible if no worker qualifies for a required skill shift."""
        shift_types = [
            ShiftType(
                id="icu",
                name="ICU Shift",
                category="specialty",
                start_time=time(7, 0),
                end_time=time(19, 0),
                duration_hours=12.0,
                workers_required=1,
                required_attributes={"certified": "icu"},
            ),
        ]
        workers = [
            Worker(id="W001", name="Alice", attributes={}),
            Worker(id="W002", name="Bob", attributes={}),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        coverage = CoverageConstraint(model, variables)
        coverage.apply(workers=workers, shift_types=shift_types, num_periods=1)

        constraint = SkillsConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.INFEASIBLE

    def test_interaction_with_coverage_feasible_when_qualified_worker_exists(
        self, model: cp_model.CpModel
    ) -> None:
        """Coverage is satisfiable when at least one worker qualifies."""
        shift_types = [
            ShiftType(
                id="icu",
                name="ICU Shift",
                category="specialty",
                start_time=time(7, 0),
                end_time=time(19, 0),
                duration_hours=12.0,
                workers_required=1,
                required_attributes={"certified": "icu"},
            ),
        ]
        workers = [
            Worker(id="W001", name="Alice", attributes={}),
            Worker(id="W002", name="Bob", attributes={"certified": "icu"}),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        coverage = CoverageConstraint(model, variables)
        coverage.apply(workers=workers, shift_types=shift_types, num_periods=1)

        constraint = SkillsConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        assert solver.Value(variables.get_assignment_var("W002", 0, "icu")) == 1
        assert solver.Value(variables.get_assignment_var("W001", 0, "icu")) == 0


class TestSkillsConstraintEdgeCases:
    """Edge case tests for SkillsConstraint."""

    def test_no_shift_types_have_requirements(self) -> None:
        """No constraints added when no shift type declares required_attributes."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Alice")]
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

        constraint = SkillsConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        assert constraint.constraint_count == 0

    def test_all_workers_qualified_adds_no_constraints(self) -> None:
        """No constraints added when every worker already qualifies."""
        model = cp_model.CpModel()
        shift_types = [
            ShiftType(
                id="icu",
                name="ICU",
                category="specialty",
                start_time=time(7, 0),
                end_time=time(19, 0),
                duration_hours=12.0,
                workers_required=1,
                required_attributes={"certified": "icu"},
            ),
        ]
        workers = [
            Worker(id="W001", name="Alice", attributes={"certified": "icu"}),
            Worker(id="W002", name="Bob", attributes={"certified": "icu"}),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        constraint = SkillsConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        assert constraint.constraint_count == 0

    def test_no_workers_qualified_blocks_all(self) -> None:
        """When no worker qualifies, the shift variable is forced to 0 for all."""
        model = cp_model.CpModel()
        shift_types = [
            ShiftType(
                id="icu",
                name="ICU",
                category="specialty",
                start_time=time(7, 0),
                end_time=time(19, 0),
                duration_hours=12.0,
                workers_required=1,
                required_attributes={"certified": "icu"},
            ),
        ]
        workers = [
            Worker(id="W001", name="Alice"),
            Worker(id="W002", name="Bob"),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=2)
        variables = builder.build()

        constraint = SkillsConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=2)

        # 2 workers * 2 periods = 4 constraints
        assert constraint.constraint_count == 4

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]
        for period in range(2):
            for w in workers:
                assert (
                    solver.Value(variables.get_assignment_var(w.id, period, "icu")) == 0
                )

    def test_init_default_config(self) -> None:
        """Default config uses BaseConstraint defaults (hard, enabled)."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Alice")]
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

        constraint = SkillsConstraint(model, variables)

        assert constraint.constraint_id == "skills"
        assert constraint.is_enabled
        assert constraint.is_hard
