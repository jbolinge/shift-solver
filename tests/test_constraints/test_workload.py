"""Tests for workload constraint."""

import logging
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


class TestWorkloadConstraintUnitHours:
    """Tests for unit='hours' (minutes-scaled) totals."""

    @pytest.fixture
    def hour_shift_types(self) -> list[ShiftType]:
        """Shift types with distinct durations for minute-scaling tests."""
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
                duration_hours=10.5,
                workers_required=1,
            ),
        ]

    def test_total_var_sums_minutes_not_shift_counts(
        self, hour_shift_types: list[ShiftType]
    ) -> None:
        """total_{worker} is the coefficient-weighted (minutes) sum, not a count."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Worker 1")]
        builder = VariableBuilder(model, workers, hour_shift_types, num_periods=2)
        variables = builder.build()

        # Pin a specific assignment pattern: day shift period 0, night shift
        # period 1.
        model.add(variables.get_assignment_var("W001", 0, "day") == 1)
        model.add(variables.get_assignment_var("W001", 0, "night") == 0)
        model.add(variables.get_assignment_var("W001", 1, "day") == 0)
        model.add(variables.get_assignment_var("W001", 1, "night") == 1)

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"unit": "hours"},
        )
        constraint = WorkloadConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=hour_shift_types, num_periods=2)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        total_var = constraint.violation_variables["total_W001"]
        # 8.0h -> 480 min, 10.5h -> 630 min; total = 1110 minutes.
        assert solver.Value(total_var) == 1110

    def test_hard_max_total_hours_caps_total_minutes(self) -> None:
        """Hard max_total_hours caps a worker's horizon total, in minutes."""
        model = cp_model.CpModel()
        workers = [
            Worker(id="W001", name="Worker 1"),
            Worker(id="W002", name="Worker 2"),
            Worker(id="W003", name="Worker 3"),
        ]
        single_shift_type = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=5.0,
                workers_required=1,
            ),
        ]
        builder = VariableBuilder(model, workers, single_shift_type, num_periods=6)
        variables = builder.build()

        coverage = CoverageConstraint(model, variables)
        coverage.apply(workers=workers, shift_types=single_shift_type, num_periods=6)

        config = ConstraintConfig(
            enabled=True,
            is_hard=True,
            weight=100,
            # 10.0 hours == 2 shifts worth (2 * 5.0h) == 600 minutes.
            parameters={"unit": "hours", "max_total_hours": 10.0},
        )
        constraint = WorkloadConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=single_shift_type, num_periods=6)

        for name, var in constraint.violation_variables.items():
            if constraint.violation_variable_types.get(name, "violation") == (
                "violation"
            ):
                model.add(var == 0)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        max_minutes = round(10.0 * 60)
        for w in workers:
            total_minutes = sum(
                solver.Value(variables.get_assignment_var(w.id, p, "shift")) * 300
                for p in range(6)
            )
            assert total_minutes <= max_minutes, (
                f"{w.id} total {total_minutes} minutes exceeds cap {max_minutes}"
            )

    def test_soft_min_total_hours_penalizes_shortfall(
        self, hour_shift_types: list[ShiftType]
    ) -> None:
        """Soft min_total_hours creates a shortfall measured in minutes."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Solo")]
        builder = VariableBuilder(model, workers, hour_shift_types, num_periods=1)
        variables = builder.build()

        coverage = CoverageConstraint(model, variables)
        coverage.apply(workers=workers, shift_types=hour_shift_types, num_periods=1)

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"unit": "hours", "min_total_hours": 100.0},
        )
        constraint = WorkloadConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=hour_shift_types, num_periods=1)

        viol_vars = [
            v
            for name, v in constraint.violation_variables.items()
            if constraint.violation_variable_types.get(name, "violation") == "violation"
        ]
        model.minimize(sum(viol_vars) * constraint.weight)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        shortfall_var = constraint.violation_variables["shortfall_W001"]
        # No worker_shift_limit constraint is applied here, so the best
        # possible in a single period is both shifts at once (480 + 630 =
        # 1110 min); the 6000-minute minimum (100h) can never be reached.
        assert solver.Value(shortfall_var) == round(100.0 * 60) - 1110

    def test_unit_hours_ignores_shift_count_params_with_warning(
        self,
        hour_shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Setting max_total_shifts alongside unit='hours' warns and is ignored."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Worker 1")]
        builder = VariableBuilder(model, workers, hour_shift_types, num_periods=2)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"unit": "hours", "max_total_shifts": 1},
        )
        constraint = WorkloadConstraint(model, variables, config)
        with caplog.at_level(logging.WARNING):
            constraint.apply(
                workers=workers, shift_types=hour_shift_types, num_periods=2
            )

        # max_total_shifts=1 must NOT be applied as an hours excess bound.
        assert "excess_W001" not in constraint.violation_variables
        assert "workload" in caplog.text.lower()
        assert "ignored" in caplog.text.lower()

    def test_unknown_unit_falls_back_to_shifts_with_warning(
        self,
        shift_types: list[ShiftType],
        workers: list[Worker],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An invalid unit value warns and falls back to 'shifts' semantics."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=3)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"unit": "days", "max_total_shifts": 2},
        )
        constraint = WorkloadConstraint(model, variables, config)
        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        assert "excess_W001" in constraint.violation_variables
        assert "unit" in caplog.text.lower()


class TestWorkloadConstraintWindowPeriods:
    """Tests for window_periods (rolling-window bounds)."""

    def test_creates_variables_per_window_with_suffix(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """window_periods > 0 creates one total per worker per sliding window."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"window_periods": 3},
        )
        constraint = WorkloadConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        # 6 periods, window size 3 -> windows starting at 0, 1, 2, 3.
        expected_starts = [0, 1, 2, 3]
        for w in workers:
            for start in expected_starts:
                name = f"total_{w.id}_w{start}"
                assert name in constraint.violation_variables
                assert constraint.violation_variable_types[name] == "auxiliary"
            # The whole-horizon (unwindowed) name must NOT be present.
            assert f"total_{w.id}" not in constraint.violation_variables

    def test_hard_window_max_caps_every_window(self) -> None:
        """Hard max_total_shifts with window_periods caps every rolling window."""
        model = cp_model.CpModel()
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
        num_periods = 6
        builder = VariableBuilder(model, workers, shift_types, num_periods=num_periods)
        variables = builder.build()

        # No coverage constraint: leave assignment free, and maximize total
        # assignments so the window cap is what actually binds (otherwise
        # the trivial all-zero solution would vacuously satisfy any cap).
        assignment_vars = [
            variables.get_assignment_var("W001", p, "shift") for p in range(num_periods)
        ]
        model.maximize(sum(assignment_vars))

        config = ConstraintConfig(
            enabled=True,
            is_hard=True,
            weight=100,
            parameters={"max_total_shifts": 1, "window_periods": 2},
        )
        constraint = WorkloadConstraint(model, variables, config)
        constraint.apply(
            workers=workers, shift_types=shift_types, num_periods=num_periods
        )

        for name, var in constraint.violation_variables.items():
            if constraint.violation_variable_types.get(name, "violation") == (
                "violation"
            ):
                model.add(var == 0)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        values = [solver.Value(v) for v in assignment_vars]
        # Every rolling window of 2 consecutive periods has at most 1
        # assignment (max_total_shifts=1 within window_periods=2).
        for i in range(num_periods - 1):
            assert values[i] + values[i + 1] <= 1
        # Maximizing under a 1-per-2-periods cap over 6 periods tops out at
        # 3 assignments (e.g. periods 0, 2, 4).
        assert sum(values) == 3


class TestWorkloadConstraintFilters:
    """Tests for shift_types/categories filters."""

    def test_shift_types_filter_restricts_total(
        self, shift_types: list[ShiftType]
    ) -> None:
        """Only assignments to filtered shift types count toward the total."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Worker 1")]
        builder = VariableBuilder(model, workers, shift_types, num_periods=2)
        variables = builder.build()

        model.add(variables.get_assignment_var("W001", 0, "day") == 1)
        model.add(variables.get_assignment_var("W001", 1, "day") == 1)
        model.add(variables.get_assignment_var("W001", 0, "night") == 1)
        model.add(variables.get_assignment_var("W001", 1, "night") == 1)

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"shift_types": ["day"]},
        )
        constraint = WorkloadConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=2)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        total_var = constraint.violation_variables["total_W001"]
        # Only the 2 "day" assignments count, not the 2 "night" ones.
        assert solver.Value(total_var) == 2

    def test_categories_filter_restricts_total(
        self, shift_types: list[ShiftType]
    ) -> None:
        """Only assignments to shift types in the filtered categories count."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Worker 1")]
        builder = VariableBuilder(model, workers, shift_types, num_periods=2)
        variables = builder.build()

        model.add(variables.get_assignment_var("W001", 0, "day") == 1)
        model.add(variables.get_assignment_var("W001", 1, "day") == 1)
        model.add(variables.get_assignment_var("W001", 0, "night") == 1)
        model.add(variables.get_assignment_var("W001", 1, "night") == 1)

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"categories": ["night"]},
        )
        constraint = WorkloadConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=2)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        total_var = constraint.violation_variables["total_W001"]
        assert solver.Value(total_var) == 2

    def test_unmatched_shift_types_filter_warns_and_noops(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """shift_types filter matching nothing warns and creates no variables."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"shift_types": ["nonexistent_shift"]},
        )
        constraint = WorkloadConstraint(model, variables, config)
        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        assert len(constraint.violation_variables) == 0
        assert constraint.constraint_count == 0
        assert "workload" in caplog.text.lower()

    def test_shift_types_and_categories_combine_with_and(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """shift_types and categories combine as an intersection (AND)."""
        model, variables = model_and_variables
        # "day" shift type is never in the "night" category, so the
        # intersection is empty.
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"shift_types": ["day"], "categories": ["night"]},
        )
        constraint = WorkloadConstraint(model, variables, config)
        with caplog.at_level(logging.WARNING):
            constraint.apply(workers=workers, shift_types=shift_types, num_periods=6)

        assert len(constraint.violation_variables) == 0


class TestWorkloadConstraintEdgeCases:
    """Miscellaneous edge cases."""

    def test_single_period_whole_horizon_does_not_crash(
        self, shift_types: list[ShiftType]
    ) -> None:
        """A single-period horizon is handled without error."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Worker 1")]
        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"min_total_shifts": 1, "max_total_shifts": 1},
        )
        constraint = WorkloadConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=1)

        assert "total_W001" in constraint.violation_variables
        assert "shortfall_W001" in constraint.violation_variables
        assert "excess_W001" in constraint.violation_variables

    def test_single_period_window_of_one(self, shift_types: list[ShiftType]) -> None:
        """window_periods=1 (per-period bound) does not crash and windows each period."""
        model = cp_model.CpModel()
        workers = [Worker(id="W001", name="Worker 1")]
        builder = VariableBuilder(model, workers, shift_types, num_periods=3)
        variables = builder.build()

        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"max_total_shifts": 1, "window_periods": 1},
        )
        constraint = WorkloadConstraint(model, variables, config)
        constraint.apply(workers=workers, shift_types=shift_types, num_periods=3)

        for start in (0, 1, 2):
            assert f"total_W001_w{start}" in constraint.violation_variables
            assert f"excess_W001_w{start}" in constraint.violation_variables
