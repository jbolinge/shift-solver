"""Tests for request constraint."""

from datetime import date, time

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.request import RequestConstraint
from shift_solver.models import SchedulingRequest, ShiftType, Worker
from shift_solver.solver.types import SolverVariables
from shift_solver.solver.variable_builder import VariableBuilder


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
def period_dates() -> list[tuple[date, date]]:
    """Create period dates (4 weeks)."""
    return [
        (date(2026, 1, 5), date(2026, 1, 11)),
        (date(2026, 1, 12), date(2026, 1, 18)),
        (date(2026, 1, 19), date(2026, 1, 25)),
        (date(2026, 1, 26), date(2026, 2, 1)),
    ]


@pytest.fixture
def model_and_variables(
    workers: list[Worker], shift_types: list[ShiftType]
) -> tuple[cp_model.CpModel, SolverVariables]:
    """Create model and variables for testing."""
    model = cp_model.CpModel()
    builder = VariableBuilder(model, workers, shift_types, num_periods=4)
    variables = builder.build()
    return model, variables


class TestRequestConstraintInit:
    """Tests for RequestConstraint initialization."""

    def test_init_default_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Test initialization with default config."""
        model, variables = model_and_variables
        constraint = RequestConstraint(model, variables)

        assert constraint.constraint_id == "request"
        assert constraint.is_enabled
        assert not constraint.is_hard
        assert constraint.weight == 100

    def test_init_with_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Test initialization with custom config."""
        model, variables = model_and_variables
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=150,
        )
        constraint = RequestConstraint(model, variables, config)

        assert constraint.weight == 150


class TestRequestConstraintApply:
    """Tests for RequestConstraint.apply()."""

    def test_apply_with_positive_request(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Test that positive requests create violation for not working."""
        model, variables = model_and_variables

        # Worker 1 wants to work day shift in period 1
        requests = [
            SchedulingRequest(
                worker_id="W001",
                start_date=date(2026, 1, 12),
                end_date=date(2026, 1, 18),
                request_type="positive",
                shift_type_id="day",
                priority=1,
            )
        ]

        constraint = RequestConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        # Should have violation variable for unfulfilled positive request
        assert len(constraint.violation_variables) > 0

    def test_apply_with_negative_request(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Test that negative requests create violation for working."""
        model, variables = model_and_variables

        # Worker 1 wants to avoid night shift in period 2
        requests = [
            SchedulingRequest(
                worker_id="W001",
                start_date=date(2026, 1, 19),
                end_date=date(2026, 1, 25),
                request_type="negative",
                shift_type_id="night",
                priority=1,
            )
        ]

        constraint = RequestConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        assert len(constraint.violation_variables) > 0

    def test_apply_disabled_does_nothing(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Test that disabled constraint adds no constraints."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=False)
        constraint = RequestConstraint(model, variables, config)

        requests = [
            SchedulingRequest(
                worker_id="W001",
                start_date=date(2026, 1, 12),
                end_date=date(2026, 1, 18),
                request_type="positive",
                shift_type_id="day",
                priority=1,
            )
        ]

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        assert len(constraint.violation_variables) == 0

    def test_apply_with_no_requests(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Test that empty requests list adds no constraints."""
        model, variables = model_and_variables
        constraint = RequestConstraint(model, variables)

        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=[],
            period_dates=period_dates,
        )

        assert len(constraint.violation_variables) == 0


class TestRequestConstraintSolve:
    """Integration tests that solve with request constraint."""

    def test_positive_request_honored_when_possible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Test that positive requests are honored when feasible."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # Worker 1 wants day shift in period 0
        requests = [
            SchedulingRequest(
                worker_id="W001",
                start_date=date(2026, 1, 5),
                end_date=date(2026, 1, 11),
                request_type="positive",
                shift_type_id="day",
                priority=1,
            )
        ]

        config = ConstraintConfig(enabled=True, is_hard=False, weight=1000)
        constraint = RequestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        # Add coverage constraint
        for period in range(4):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Minimize violations
        if constraint.violation_variables:
            total = sum(constraint.violation_variables.values())
            model.minimize(total * constraint.weight)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # Check if W001 got day shift in period 0
        w001_day_p0 = solver.value(variables.get_assignment_var("W001", 0, "day"))
        # With high weight, should honor the request
        assert w001_day_p0 == 1

    def test_negative_request_honored_when_possible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Test that negative requests are honored when feasible."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # Worker 1 wants to avoid night shift in period 0
        requests = [
            SchedulingRequest(
                worker_id="W001",
                start_date=date(2026, 1, 5),
                end_date=date(2026, 1, 11),
                request_type="negative",
                shift_type_id="night",
                priority=1,
            )
        ]

        config = ConstraintConfig(enabled=True, is_hard=False, weight=1000)
        constraint = RequestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        # Add coverage constraint
        for period in range(4):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Minimize violations
        if constraint.violation_variables:
            total = sum(constraint.violation_variables.values())
            model.minimize(total * constraint.weight)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # Check that W001 did NOT get night shift in period 0
        w001_night_p0 = solver.value(variables.get_assignment_var("W001", 0, "night"))
        assert w001_night_p0 == 0

    def test_priority_affects_violation_weight(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Test that higher priority requests have higher violation cost."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # Two conflicting requests with different priorities
        requests = [
            SchedulingRequest(
                worker_id="W001",
                start_date=date(2026, 1, 5),
                end_date=date(2026, 1, 11),
                request_type="positive",
                shift_type_id="day",
                priority=1,  # Lower priority
            ),
            SchedulingRequest(
                worker_id="W001",
                start_date=date(2026, 1, 5),
                end_date=date(2026, 1, 11),
                request_type="positive",
                shift_type_id="night",
                priority=3,  # Higher priority
            ),
        ]

        config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        constraint = RequestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        # Add coverage - only 1 worker per shift, so W001 can only have one
        for period in range(4):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Should have violation variables
        assert len(constraint.violation_variables) >= 2

        # Solve
        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


class TestRequestConstraintPriorityMetadata:
    """Tests for priority metadata storage (scheduler-54)."""

    def test_priority_stored_in_metadata_not_name(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Test that priority is stored in violation_priorities dict."""
        model, variables = model_and_variables

        requests = [
            SchedulingRequest(
                worker_id="W001",
                start_date=date(2026, 1, 5),
                end_date=date(2026, 1, 11),
                request_type="positive",
                shift_type_id="day",
                priority=3,
            )
        ]

        constraint = RequestConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        # Should have violation priorities dict with entries
        assert hasattr(constraint, "violation_priorities")
        assert len(constraint.violation_priorities) > 0

        # Variable names should NOT contain _prio suffix
        for var_name in constraint.violation_variables:
            assert "_prio" not in var_name

        # Priorities should be stored in the dict
        for var_name in constraint.violation_variables:
            assert var_name in constraint.violation_priorities
            assert constraint.violation_priorities[var_name] == 3

    def test_different_priorities_stored_correctly(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Test that different priorities are stored correctly."""
        model, variables = model_and_variables

        requests = [
            SchedulingRequest(
                worker_id="W001",
                start_date=date(2026, 1, 5),
                end_date=date(2026, 1, 11),
                request_type="positive",
                shift_type_id="day",
                priority=1,
            ),
            SchedulingRequest(
                worker_id="W002",
                start_date=date(2026, 1, 5),
                end_date=date(2026, 1, 11),
                request_type="positive",
                shift_type_id="night",
                priority=5,
            ),
        ]

        constraint = RequestConstraint(model, variables)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        # Check that we have both priorities
        priorities = set(constraint.violation_priorities.values())
        assert 1 in priorities
        assert 5 in priorities
