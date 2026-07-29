"""Tests for workload constraint."""

from datetime import time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.coverage import CoverageConstraint
from shift_solver.constraints.workload import WorkloadConstraint
from shift_solver.models import ShiftType, Worker
from shift_solver.solver import VariableBuilder
from shift_solver.solver.types import SolverVariables


@pytest.fixture
def workers() -> list[Worker]:
    """Create test workers."""
    return [
        Worker(id="W001", name="Worker 1"),
        Worker(id="W002", name="Worker 2"),
    ]


@pytest.fixture
def shift_types() -> list[ShiftType]:
    """Create shift types."""
    return [
        ShiftType(
            id="day",
            name="Day Shift",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=1,
        ),
        ShiftType(
            id="night",
            name="Night Shift",
            category="night",
            start_time=time(23, 0),
            end_time=time(7, 0),
            duration_hours=8.0,
            workers_required=1,
        ),
    ]


@pytest.fixture
def model_and_variables(
    workers: list[Worker], shift_types: list[ShiftType]
) -> tuple[cp_model.CpModel, SolverVariables]:
    """Create model and variables for testing."""
    model = cp_model.CpModel()
    builder = VariableBuilder(model, workers, shift_types, num_periods=6)
    variables = builder.build()
    return model, variables


class TestWorkloadConstraintInit:
    """Tests for WorkloadConstraint initialization."""

    def test_init_default_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Default config uses BaseConstraint defaults."""
        model, variables = model_and_variables
        constraint = WorkloadConstraint(model, variables)

        assert constraint.constraint_id == "workload"
        assert constraint.is_enabled
        assert constraint.is_hard
        assert constraint.weight == 100

    def test_init_with_params(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Custom parameters are readable via get_param."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"min_total_shifts": 2, "max_total_shifts": 4},
        )
        constraint = WorkloadConstraint(model, variables, config)

        assert constraint.config.get_param("min_total_shifts") == 2
        assert constraint.config.get_param("max_total_shifts") == 4


class TestWorkloadConstraintApply:
    """Tests for WorkloadConstraint.apply()."""

    def test_creates_auxiliary_total_per_worker(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """A total variable is created for every worker, marked auxiliary."""
        model, variables = model_and_variables
        constraint = WorkloadConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        for w in workers:
            total_name = f"total_{w.id}"
            assert total_name in constraint.violation_variables
            assert constraint.violation_variable_types[total_name] == "auxiliary"

    def test_no_shortfall_var_when_min_is_zero(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Default min_total_shifts=0 creates no shortfall variables."""
        model, variables = model_and_variables
        constraint = WorkloadConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        for w in workers:
            assert f"shortfall_{w.id}" not in constraint.violation_variables

    def test_no_excess_var_when_max_is_none(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Default max_total_shifts=None creates no excess variables."""
        model, variables = model_and_variables
        constraint = WorkloadConstraint(model, variables)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        for w in workers:
            assert f"excess_{w.id}" not in constraint.violation_variables

    def test_shortfall_var_created_when_min_positive(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """min_total_shifts > 0 creates a shortfall violation variable."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"min_total_shifts": 3},
        )
        constraint = WorkloadConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        for w in workers:
            name = f"shortfall_{w.id}"
            assert name in constraint.violation_variables
            assert constraint.violation_variable_types.get(name, "violation") == (
                "violation"
            )

    def test_excess_var_created_when_max_set(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """max_total_shifts set creates an excess violation variable."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_total_shifts": 4},
        )
        constraint = WorkloadConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        for w in workers:
            name = f"excess_{w.id}"
            assert name in constraint.violation_variables
            assert constraint.violation_variable_types.get(name, "violation") == (
                "violation"
            )

    def test_disabled_does_nothing(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Disabled constraint creates no variables and adds no constraints."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=False)
        constraint = WorkloadConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0

    def test_empty_workers_is_noop(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """No workers means no variables are created."""
        model, variables = model_and_variables
        constraint = WorkloadConstraint(model, variables)
        constraint.apply(workers=[], shift_types=[], num_periods=6)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0


class TestWorkloadConstraintSolveMinimum:
    """Integration tests enforcing minimum workload."""

    def test_hard_minimum_forces_enough_shifts(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Hard min_total_shifts forces every worker up to that many shifts."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=6)
        variables = builder.build()

        coverage = CoverageConstraint(model, variables)
        coverage.apply(workers=workers, shift_types=shift_types, num_periods=6)

        config = ConstraintConfig(
            enabled=True,
            is_hard=True,
            weight=100,
            parameters={"min_total_shifts": 3},
        )
        constraint = WorkloadConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        # Emulate the generic hard-mode enforcement: force "violation" typed
        # variables (shortfall/excess) to zero, leave auxiliary totals alone.
        for name, var in constraint.violation_variables.items():
            if constraint.violation_variable_types.get(name, "violation") == (
                "violation"
            ):
                model.add(var == 0)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        for w in workers:
            total = sum(
                solver.Value(variables.get_shift_count_var(w.id, st.id))
                for st in shift_types
            )
            assert total >= 3, f"{w.id} total {total} below minimum of 3"

    def test_soft_minimum_allows_shortfall(
        self,
        shift_types: list[ShiftType],
    ) -> None:
        """Soft workload allows totals below minimum when unavoidable."""
        model = cp_model.CpModel()
        # 1 worker, 6 periods, 2 shift types => at most 12 possible shifts,
        # but coverage only requires 1 assignment per period across 2 shifts
        # so 1 worker naturally gets more than enough; use a high minimum
        # instead to force an unavoidable shortfall with limited periods.
        workers = [Worker(id="W001", name="Solo")]
        builder = VariableBuilder(model, workers, shift_types, num_periods=2)
        variables = builder.build()

        coverage = CoverageConstraint(model, variables)
        coverage.apply(workers=workers, shift_types=shift_types, num_periods=2)

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"min_total_shifts": 10},
        )
        constraint = WorkloadConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=2)

        if constraint.violation_variables:
            viol_vars = [
                v
                for name, v in constraint.violation_variables.items()
                if constraint.violation_variable_types.get(name, "violation")
                == "violation"
            ]
            if viol_vars:
                model.minimize(sum(viol_vars) * constraint.weight)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        # Should still find a solution even though the minimum is unreachable
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        shortfall_var = constraint.violation_variables["shortfall_W001"]
        # Solo worker can be assigned at most 2 periods * 2 shift types = 4
        # (bounded by coverage needing only 1 assignment per period though).
        assert solver.Value(shortfall_var) > 0


class TestWorkloadConstraintSolveMaximum:
    """Integration tests enforcing maximum workload."""

    def test_hard_maximum_caps_total_shifts(self) -> None:
        """Hard max_total_shifts caps a worker's horizon total."""
        model = cp_model.CpModel()
        workers = [
            Worker(id="W001", name="Alice"),
            Worker(id="W002", name="Bob"),
            Worker(id="W003", name="Charlie"),
        ]
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
        builder = VariableBuilder(model, workers, shift_types, num_periods=6)
        variables = builder.build()

        coverage = CoverageConstraint(model, variables)
        coverage.apply(workers=workers, shift_types=shift_types, num_periods=6)

        config = ConstraintConfig(
            enabled=True,
            is_hard=True,
            weight=100,
            parameters={"max_total_shifts": 2},
        )
        constraint = WorkloadConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        for name, var in constraint.violation_variables.items():
            if constraint.violation_variable_types.get(name, "violation") == (
                "violation"
            ):
                model.add(var == 0)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        for w in workers:
            total = solver.Value(variables.get_shift_count_var(w.id, "shift"))
            assert total <= 2, f"{w.id} total {total} exceeds maximum of 2"

    def test_hard_maximum_infeasible_when_coverage_demands_more(self) -> None:
        """Hard max_total_shifts can make coverage infeasible if too tight."""
        model = cp_model.CpModel()
        # 1 worker must cover 6 periods but is capped at 2 total shifts
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
        builder = VariableBuilder(model, workers, shift_types, num_periods=6)
        variables = builder.build()

        coverage = CoverageConstraint(model, variables)
        coverage.apply(workers=workers, shift_types=shift_types, num_periods=6)

        config = ConstraintConfig(
            enabled=True,
            is_hard=True,
            weight=100,
            parameters={"max_total_shifts": 2},
        )
        constraint = WorkloadConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        for name, var in constraint.violation_variables.items():
            if constraint.violation_variable_types.get(name, "violation") == (
                "violation"
            ):
                model.add(var == 0)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        assert status == cp_model.INFEASIBLE
