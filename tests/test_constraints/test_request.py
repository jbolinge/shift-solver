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
        """Test initialization with default config uses BaseConstraint defaults."""
        model, variables = model_and_variables
        constraint = RequestConstraint(model, variables)

        assert constraint.constraint_id == "request"
        # BaseConstraint defaults: enabled=True, is_hard=True, weight=100
        assert constraint.is_enabled
        assert constraint.is_hard
        assert constraint.weight == 100

    def test_init_soft_config(
        self, model_and_variables: tuple[cp_model.CpModel, SolverVariables]
    ) -> None:
        """Test initialization with explicit soft config."""
        model, variables = model_and_variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        constraint = RequestConstraint(model, variables, config)

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

        # Use soft config to create violation variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        constraint = RequestConstraint(model, variables, config)
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

        # Use soft config to create violation variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        constraint = RequestConstraint(model, variables, config)
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

        # Use soft config to create violation variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        constraint = RequestConstraint(model, variables, config)
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

        # Use soft config to create violation variables
        config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        constraint = RequestConstraint(model, variables, config)
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


class TestRequestConstraintViolationVariableCoupling:
    """
    Tests for violation variable coupling (scheduler-67).

    The request constraint uses `only_enforce_if` to create bidirectional
    indicator constraints. These tests verify that violation variables
    accurately reflect the actual assignment state in the solution.
    """

    def test_positive_request_honored_violation_is_zero(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Verify violation_var=0 when positive request IS satisfied (worker assigned)."""
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

        # Force the assignment to be made (satisfying the request)
        assignment_var = variables.get_assignment_var("W001", 0, "day")
        model.add(assignment_var == 1)

        # Minimize violations
        violation_vars = list(constraint.violation_variables.values())
        model.minimize(sum(violation_vars))

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert solver.value(assignment_var) == 1

        # Violation should be 0 because request is satisfied
        for viol_var in violation_vars:
            assert solver.value(viol_var) == 0

    def test_positive_request_violated_violation_is_one(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Verify violation_var=1 when positive request is NOT satisfied (no assignment)."""
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

        # Force the assignment to NOT be made (violating the request)
        assignment_var = variables.get_assignment_var("W001", 0, "day")
        model.add(assignment_var == 0)

        # No objective - just solve to check violation state
        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert solver.value(assignment_var) == 0

        # Violation should be 1 because positive request is NOT satisfied
        violation_vars = list(constraint.violation_variables.values())
        assert len(violation_vars) == 1
        assert solver.value(violation_vars[0]) == 1

    def test_negative_request_honored_violation_is_zero(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Verify violation_var=0 when negative request IS honored (worker NOT assigned)."""
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

        # Force NO assignment (honoring the negative request)
        assignment_var = variables.get_assignment_var("W001", 0, "night")
        model.add(assignment_var == 0)

        # Minimize violations
        violation_vars = list(constraint.violation_variables.values())
        model.minimize(sum(violation_vars))

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert solver.value(assignment_var) == 0

        # Violation should be 0 because negative request is honored
        for viol_var in violation_vars:
            assert solver.value(viol_var) == 0

    def test_negative_request_violated_violation_is_one(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Verify violation_var=1 when negative request is violated (worker IS assigned)."""
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

        # Force assignment (violating the negative request)
        assignment_var = variables.get_assignment_var("W001", 0, "night")
        model.add(assignment_var == 1)

        # No objective - just solve to check violation state
        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert solver.value(assignment_var) == 1

        # Violation should be 1 because negative request is violated
        violation_vars = list(constraint.violation_variables.values())
        assert len(violation_vars) == 1
        assert solver.value(violation_vars[0]) == 1

    def test_multiple_conflicting_requests_same_period(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Test worker with both positive and negative requests for same period."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # Worker 1 wants day shift but NOT night shift in period 0
        requests = [
            SchedulingRequest(
                worker_id="W001",
                start_date=date(2026, 1, 5),
                end_date=date(2026, 1, 11),
                request_type="positive",
                shift_type_id="day",
                priority=2,
            ),
            SchedulingRequest(
                worker_id="W001",
                start_date=date(2026, 1, 5),
                end_date=date(2026, 1, 11),
                request_type="negative",
                shift_type_id="night",
                priority=1,
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

        # Should have 2 violation variables (one per request)
        assert len(constraint.violation_variables) == 2

        # Force: day=1 (positive satisfied), night=0 (negative honored)
        model.add(variables.get_assignment_var("W001", 0, "day") == 1)
        model.add(variables.get_assignment_var("W001", 0, "night") == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # Both requests should be satisfied - both violations should be 0
        for viol_var in constraint.violation_variables.values():
            assert solver.value(viol_var) == 0

    def test_post_solve_violation_vars_match_assignments(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Post-solve validation: extract violation vars and verify they match assignments."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # Multiple requests across different periods
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
                worker_id="W001",
                start_date=date(2026, 1, 12),
                end_date=date(2026, 1, 18),
                request_type="negative",
                shift_type_id="night",
                priority=2,
            ),
            SchedulingRequest(
                worker_id="W002",
                start_date=date(2026, 1, 5),
                end_date=date(2026, 1, 11),
                request_type="positive",
                shift_type_id="night",
                priority=3,
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

        # Add basic coverage to make it a real scheduling problem
        for period in range(4):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Minimize violations with priority weighting
        if constraint.violation_variables:
            penalty_terms = []
            for var_name, viol_var in constraint.violation_variables.items():
                priority = constraint.violation_priorities.get(var_name, 1)
                penalty_terms.append(viol_var * priority * config.weight)
            model.minimize(sum(penalty_terms))

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # Post-solve validation: manually check each violation matches assignment
        for var_name, viol_var in constraint.violation_variables.items():
            viol_value = solver.value(viol_var)

            # Parse the variable name to extract worker, shift_type, period
            # Format: req_viol_{worker_id}_{shift_type_id}_p{period}_r{idx}
            parts = var_name.replace("req_viol_", "").split("_")
            worker_id = parts[0]
            shift_type_id = parts[1]
            period = int(parts[2][1:])  # Remove 'p' prefix
            request_idx = int(parts[3][1:])  # Remove 'r' prefix

            assignment_var = variables.get_assignment_var(
                worker_id, period, shift_type_id
            )
            assignment_value = solver.value(assignment_var)

            # Determine expected violation based on request type
            request = requests[request_idx]
            if request.is_positive:
                # Positive: violation=1 if NOT assigned
                expected_viol = 0 if assignment_value >= 1 else 1
            else:
                # Negative: violation=1 if assigned
                expected_viol = 1 if assignment_value >= 1 else 0

            assert viol_value == expected_viol, (
                f"Violation mismatch for {var_name}: "
                f"expected={expected_viol}, actual={viol_value}, "
                f"assignment={assignment_value}, is_positive={request.is_positive}"
            )

    def test_violation_coupling_bidirectional_soundness(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """
        Test that bidirectional implications are sound.

        The only_enforce_if pattern creates:
        - violation_var=1 => assignment_var=0 (for positive requests)
        - violation_var=0 => assignment_var>=1 (for positive requests)

        This test verifies that solver doesn't relax these implications.
        """
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=1)
        variables = builder.build()

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

        config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        constraint = RequestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            requests=requests,
            period_dates=period_dates[:1],
        )

        _violation_var = list(constraint.violation_variables.values())[0]
        _assignment_var = variables.get_assignment_var("W001", 0, "day")

        # Test case 1: Force violation=1, verify assignment=0
        model_test1 = cp_model.CpModel()
        builder1 = VariableBuilder(model_test1, workers, shift_types, num_periods=1)
        vars1 = builder1.build()
        constraint1 = RequestConstraint(model_test1, vars1, config)
        constraint1.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            requests=requests,
            period_dates=period_dates[:1],
        )
        viol1 = list(constraint1.violation_variables.values())[0]
        model_test1.add(viol1 == 1)

        solver1 = cp_model.CpSolver()
        status1 = solver1.solve(model_test1)
        assert status1 in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert solver1.value(vars1.get_assignment_var("W001", 0, "day")) == 0

        # Test case 2: Force violation=0, verify assignment>=1
        model_test2 = cp_model.CpModel()
        builder2 = VariableBuilder(model_test2, workers, shift_types, num_periods=1)
        vars2 = builder2.build()
        constraint2 = RequestConstraint(model_test2, vars2, config)
        constraint2.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            requests=requests,
            period_dates=period_dates[:1],
        )
        viol2 = list(constraint2.violation_variables.values())[0]
        model_test2.add(viol2 == 0)

        solver2 = cp_model.CpSolver()
        status2 = solver2.solve(model_test2)
        assert status2 in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert solver2.value(vars2.get_assignment_var("W001", 0, "day")) >= 1


class TestHardVsSoftRequestSemantics:
    """
    Tests for hard vs soft request constraint enforcement semantics (scheduler-69).

    Tests verify interactions between hard requests and coverage constraints,
    and compare hard vs soft behavior.
    """

    def test_hard_positive_request_with_coverage(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Test that hard positive request works with coverage constraint."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # Worker 1 must work day shift in period 0 (hard constraint)
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

        # Use hard config
        config = ConstraintConfig(enabled=True, is_hard=True, weight=100)
        constraint = RequestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        # Add coverage constraint (exactly 1 worker per shift)
        for period in range(4):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        # W001 must be assigned to day shift in period 0
        assert solver.value(variables.get_assignment_var("W001", 0, "day")) == 1

    def test_multiple_hard_positive_requests_same_period(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Test multiple workers with hard positive requests for same shift."""
        model = cp_model.CpModel()
        # Need more workers to test this scenario (not using fixture)
        more_workers = [
            Worker(id="W001", name="Worker 1"),
            Worker(id="W002", name="Worker 2"),
            Worker(id="W003", name="Worker 3"),
        ]
        builder = VariableBuilder(model, more_workers, shift_types, num_periods=4)
        variables = builder.build()

        # Both W001 and W002 must work day shift in period 0 (hard constraints)
        # But coverage only needs 1 worker
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
                shift_type_id="day",
                priority=1,
            ),
        ]

        config = ConstraintConfig(enabled=True, is_hard=True, weight=100)
        constraint = RequestConstraint(model, variables, config)
        constraint.apply(
            workers=more_workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        # Add coverage constraint (exactly 1 worker per shift)
        for period in range(4):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in more_workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        # This should be INFEASIBLE because both must work but only 1 slot available
        assert status == cp_model.INFEASIBLE

    def test_hard_positive_coverage_limited_slots(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Test hard positive request when coverage has limited slots."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # W001 must work day shift (but coverage only allows 1 worker)
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

        config = ConstraintConfig(enabled=True, is_hard=True, weight=100)
        constraint = RequestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        # Coverage: exactly 1 worker per shift
        for period in range(4):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        # W001 gets the day shift, W002 must get the night shift
        assert solver.value(variables.get_assignment_var("W001", 0, "day")) == 1

    def test_hard_negative_with_coverage(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Test hard negative request excludes worker while maintaining coverage."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # W001 must NOT work night shift in period 0 (hard constraint)
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

        config = ConstraintConfig(enabled=True, is_hard=True, weight=100)
        constraint = RequestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        # Coverage: exactly 1 worker per shift
        for period in range(4):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        # W001 must NOT have night shift in period 0
        assert solver.value(variables.get_assignment_var("W001", 0, "night")) == 0
        # W002 must take the night shift instead
        assert solver.value(variables.get_assignment_var("W002", 0, "night")) == 1

    def test_hard_negative_infeasible_when_only_option(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Test that hard negative makes problem infeasible when worker is only option."""
        model = cp_model.CpModel()
        # Only 1 worker available
        single_worker = [Worker(id="W001", name="Worker 1")]
        builder = VariableBuilder(model, single_worker, shift_types, num_periods=1)
        variables = builder.build()

        # W001 must NOT work day shift, but they're the only worker
        requests = [
            SchedulingRequest(
                worker_id="W001",
                start_date=date(2026, 1, 5),
                end_date=date(2026, 1, 11),
                request_type="negative",
                shift_type_id="day",
                priority=1,
            )
        ]

        config = ConstraintConfig(enabled=True, is_hard=True, weight=100)
        constraint = RequestConstraint(model, variables, config)
        constraint.apply(
            workers=single_worker,
            shift_types=shift_types,
            num_periods=1,
            requests=requests,
            period_dates=period_dates[:1],
        )

        # Coverage: exactly 1 worker for day shift
        vars_for_day = [
            variables.get_assignment_var(w.id, 0, "day") for w in single_worker
        ]
        model.add(sum(vars_for_day) == 1)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        # Should be infeasible: can't satisfy both coverage and negative request
        assert status == cp_model.INFEASIBLE

    def test_compare_hard_vs_soft_same_scenario(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Compare hard vs soft semantics with same scenario."""
        # Scenario: W001 wants day shift, W002 also wants day shift (only 1 slot)

        # Test 1: With SOFT constraints - should be feasible, one will be violated
        model_soft = cp_model.CpModel()
        builder_soft = VariableBuilder(model_soft, workers, shift_types, num_periods=1)
        vars_soft = builder_soft.build()

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
                shift_type_id="day",
                priority=2,  # Higher priority
            ),
        ]

        config_soft = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        constraint_soft = RequestConstraint(model_soft, vars_soft, config_soft)
        constraint_soft.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            requests=requests,
            period_dates=period_dates[:1],
        )

        # Coverage: exactly 1 worker for day shift
        vars_day_soft = [
            vars_soft.get_assignment_var(w.id, 0, "day") for w in workers
        ]
        model_soft.add(sum(vars_day_soft) == 1)

        # Minimize violations with priority weighting
        if constraint_soft.violation_variables:
            penalty_terms = []
            for var_name, viol_var in constraint_soft.violation_variables.items():
                priority = constraint_soft.violation_priorities.get(var_name, 1)
                penalty_terms.append(viol_var * priority * config_soft.weight)
            model_soft.minimize(sum(penalty_terms))

        solver_soft = cp_model.CpSolver()
        status_soft = solver_soft.solve(model_soft)

        assert status_soft in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # With soft constraints, W002 should get the shift (higher priority)
        # So W001's request is violated
        w001_day = solver_soft.value(vars_soft.get_assignment_var("W001", 0, "day"))
        w002_day = solver_soft.value(vars_soft.get_assignment_var("W002", 0, "day"))

        # One must be assigned, one must not
        assert w001_day + w002_day == 1
        # W002 has higher priority, so should get the shift
        assert w002_day == 1
        assert w001_day == 0

        # Test 2: With HARD constraints - should be INFEASIBLE
        model_hard = cp_model.CpModel()
        builder_hard = VariableBuilder(model_hard, workers, shift_types, num_periods=1)
        vars_hard = builder_hard.build()

        config_hard = ConstraintConfig(enabled=True, is_hard=True, weight=100)
        constraint_hard = RequestConstraint(model_hard, vars_hard, config_hard)
        constraint_hard.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=1,
            requests=requests,
            period_dates=period_dates[:1],
        )

        # Coverage: exactly 1 worker for day shift
        vars_day_hard = [
            vars_hard.get_assignment_var(w.id, 0, "day") for w in workers
        ]
        model_hard.add(sum(vars_day_hard) == 1)

        solver_hard = cp_model.CpSolver()
        status_hard = solver_hard.solve(model_hard)

        # With hard constraints, both must be assigned but only 1 slot - infeasible
        assert status_hard == cp_model.INFEASIBLE

    def test_hard_request_does_not_create_violation_vars(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Verify that hard requests don't create violation variables."""
        model, variables = model_and_variables

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

        # Hard config
        config = ConstraintConfig(enabled=True, is_hard=True, weight=100)
        constraint = RequestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        # Hard constraints should not create violation variables
        assert len(constraint.violation_variables) == 0
        assert len(constraint.violation_priorities) == 0

    def test_soft_request_creates_violation_vars(
        self,
        model_and_variables: tuple[cp_model.CpModel, SolverVariables],
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Verify that soft requests DO create violation variables."""
        model, variables = model_and_variables

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

        # Soft config
        config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        constraint = RequestConstraint(model, variables, config)
        constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        # Soft constraints SHOULD create violation variables
        assert len(constraint.violation_variables) > 0
        assert len(constraint.violation_priorities) > 0
