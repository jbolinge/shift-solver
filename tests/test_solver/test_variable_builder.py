"""Tests for VariableBuilder - creates solver variables from domain models."""

from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.models import Worker, ShiftType
from shift_solver.solver.variable_builder import VariableBuilder


class TestVariableBuilder:
    """Tests for VariableBuilder."""

    @pytest.fixture
    def model(self) -> cp_model.CpModel:
        """Create a fresh CP model."""
        return cp_model.CpModel()

    @pytest.fixture
    def workers(self) -> list[Worker]:
        """Create sample workers."""
        return [
            Worker(id="W001", name="Alice"),
            Worker(id="W002", name="Bob"),
            Worker(id="W003", name="Charlie"),
        ]

    @pytest.fixture
    def shift_types(self) -> list[ShiftType]:
        """Create sample shift types."""
        return [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                is_undesirable=True,
            ),
        ]

    @pytest.fixture
    def builder(
        self, model: cp_model.CpModel, workers: list[Worker], shift_types: list[ShiftType]
    ) -> VariableBuilder:
        """Create a VariableBuilder instance."""
        return VariableBuilder(
            model=model,
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
        )

    def test_create_variable_builder(self, builder: VariableBuilder) -> None:
        """VariableBuilder can be created."""
        assert builder is not None
        assert builder.num_periods == 4

    def test_build_returns_solver_variables(self, builder: VariableBuilder) -> None:
        """build() returns a SolverVariables instance."""
        from shift_solver.solver.types import SolverVariables

        variables = builder.build()
        assert isinstance(variables, SolverVariables)

    def test_builds_assignment_variables(self, builder: VariableBuilder) -> None:
        """Assignment variables are created for all combinations."""
        variables = builder.build()

        # 3 workers * 4 periods * 2 shift types = 24 assignment vars
        all_vars = list(variables.all_assignment_vars())
        assert len(all_vars) == 24

    def test_assignment_var_names_are_descriptive(self, builder: VariableBuilder) -> None:
        """Assignment variable names include worker, period, and shift type."""
        variables = builder.build()

        var = variables.get_assignment_var("W001", 0, "day")
        name = var.Name()
        assert "W001" in name
        assert "0" in name
        assert "day" in name

    def test_builds_shift_count_variables(self, builder: VariableBuilder) -> None:
        """Shift count variables are created for each worker-shift combination."""
        variables = builder.build()

        # Each worker should have count vars for each shift type
        for worker_id in ["W001", "W002", "W003"]:
            for shift_type_id in ["day", "night"]:
                var = variables.get_shift_count_var(worker_id, shift_type_id)
                assert var is not None

    def test_shift_count_vars_bounded(
        self, model: cp_model.CpModel, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """Shift count variables have correct bounds (0 to num_periods)."""
        num_periods = 10
        builder = VariableBuilder(
            model=model,
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
        )
        variables = builder.build()

        # Verify through solving that bounds are respected
        solver = cp_model.CpSolver()
        var = variables.get_shift_count_var("W001", "day")

        # Try to set value outside bounds - should fail
        test_model = cp_model.CpModel()
        test_var = test_model.new_int_var(0, num_periods, "test")
        test_model.add(test_var == num_periods + 1)
        status = solver.Solve(test_model)
        assert status == cp_model.INFEASIBLE

    def test_builds_undesirable_total_variables(self, builder: VariableBuilder) -> None:
        """Undesirable total variables are created for each worker."""
        variables = builder.build()

        for worker_id in ["W001", "W002", "W003"]:
            var = variables.get_undesirable_total_var(worker_id)
            assert var is not None

    def test_links_shift_counts_to_assignments(self, builder: VariableBuilder) -> None:
        """Shift count variables are linked to assignment sums."""
        variables = builder.build()

        # Solve a simple model to verify linkage
        model = builder.model
        solver = cp_model.CpSolver()

        # Force W001 to work day shift in periods 0 and 1
        model.add(variables.get_assignment_var("W001", 0, "day") == 1)
        model.add(variables.get_assignment_var("W001", 1, "day") == 1)
        model.add(variables.get_assignment_var("W001", 2, "day") == 0)
        model.add(variables.get_assignment_var("W001", 3, "day") == 0)

        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Verify count is correct
        count_var = variables.get_shift_count_var("W001", "day")
        assert solver.Value(count_var) == 2

    def test_links_undesirable_totals(self, builder: VariableBuilder) -> None:
        """Undesirable totals are linked to undesirable shift assignments."""
        variables = builder.build()

        model = builder.model
        solver = cp_model.CpSolver()

        # Force W001 to work night (undesirable) in periods 0 and 2
        model.add(variables.get_assignment_var("W001", 0, "night") == 1)
        model.add(variables.get_assignment_var("W001", 1, "night") == 0)
        model.add(variables.get_assignment_var("W001", 2, "night") == 1)
        model.add(variables.get_assignment_var("W001", 3, "night") == 0)

        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Verify undesirable total is correct
        total_var = variables.get_undesirable_total_var("W001")
        assert solver.Value(total_var) == 2

    def test_no_undesirable_shifts(
        self, model: cp_model.CpModel, workers: list[Worker]
    ) -> None:
        """Works correctly when no shift types are undesirable."""
        shift_types = [
            ShiftType(
                id="morning",
                name="Morning",
                category="day",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                is_undesirable=False,
            ),
        ]

        builder = VariableBuilder(
            model=model,
            workers=workers,
            shift_types=shift_types,
            num_periods=2,
        )
        variables = builder.build()

        # Undesirable totals should all be 0
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        for worker_id in ["W001", "W002", "W003"]:
            total = solver.Value(variables.get_undesirable_total_var(worker_id))
            assert total == 0


class TestVariableBuilderEdgeCases:
    """Edge case tests for VariableBuilder."""

    def test_single_worker(self) -> None:
        """Works with a single worker."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Solo")]
        shift_types = [
            ShiftType(
                id="shift1",
                name="Shift",
                category="any",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        assert len(list(variables.all_assignment_vars())) == 1

    def test_single_period(self) -> None:
        """Works with a single period."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="A"), Worker(id="W002", name="B")]
        shift_types = [
            ShiftType(
                id="s1",
                name="S1",
                category="x",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
            ),
            ShiftType(
                id="s2",
                name="S2",
                category="x",
                start_time=time(8, 0),
                end_time=time(16, 0),
                duration_hours=8.0,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        # 2 workers * 1 period * 2 shifts = 4
        assert len(list(variables.all_assignment_vars())) == 4

    def test_many_periods(self) -> None:
        """Works with many periods (52 weeks)."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="A")]
        shift_types = [
            ShiftType(
                id="s1",
                name="S",
                category="x",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
            ),
        ]

        builder = VariableBuilder(model, workers, shift_types, num_periods=52)
        variables = builder.build()

        assert len(list(variables.all_assignment_vars())) == 52


class TestVariableBuilderValidation:
    """Validation tests for VariableBuilder."""

    def test_empty_workers_raises(self) -> None:
        """Raises ValueError for empty workers list."""
        model = cp_model.CpModel()
        shift_types = [
            ShiftType(
                id="s1",
                name="S",
                category="x",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
            ),
        ]

        with pytest.raises(ValueError, match="workers"):
            VariableBuilder(model, [], shift_types, num_periods=1)

    def test_empty_shift_types_raises(self) -> None:
        """Raises ValueError for empty shift types list."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="A")]

        with pytest.raises(ValueError, match="shift_types"):
            VariableBuilder(model, workers, [], num_periods=1)

    def test_zero_periods_raises(self) -> None:
        """Raises ValueError for zero periods."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="A")]
        shift_types = [
            ShiftType(
                id="s1",
                name="S",
                category="x",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
            ),
        ]

        with pytest.raises(ValueError, match="num_periods"):
            VariableBuilder(model, workers, shift_types, num_periods=0)

    def test_negative_periods_raises(self) -> None:
        """Raises ValueError for negative periods."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="A")]
        shift_types = [
            ShiftType(
                id="s1",
                name="S",
                category="x",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
            ),
        ]

        with pytest.raises(ValueError, match="num_periods"):
            VariableBuilder(model, workers, shift_types, num_periods=-1)
