"""
Tests for overlapping availability and request constraints (scheduler-73).

Tests edge cases where worker availability periods conflict with scheduling requests.
"""

from datetime import date, time, timedelta

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.availability import AvailabilityConstraint
from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.request import RequestConstraint
from shift_solver.models import (
    Availability,
    SchedulingRequest,
    ShiftType,
    Worker,
)
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
    base = date(2026, 1, 5)  # Monday
    return [
        (base + timedelta(weeks=i), base + timedelta(weeks=i, days=6))
        for i in range(4)
    ]


class TestPositiveRequestDuringUnavailability:
    """Tests for positive request during unavailable period."""

    def test_hard_positive_request_during_hard_unavailability_infeasible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Hard positive request + hard unavailability = infeasible."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # W001 is unavailable in period 1
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                availability_type="unavailable",
            ),
        ]

        # But W001 has a hard positive request to work in period 1
        requests = [
            SchedulingRequest(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                request_type="positive",
                shift_type_id="day",
                priority=1,
            )
        ]

        # Apply availability (hard constraint)
        avail_constraint = AvailabilityConstraint(model, variables)
        avail_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        # Apply hard request constraint
        request_config = ConstraintConfig(enabled=True, is_hard=True, weight=100)
        request_constraint = RequestConstraint(model, variables, request_config)
        request_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        # Should be infeasible: must work AND must not work
        assert status == cp_model.INFEASIBLE

    def test_soft_positive_request_during_hard_unavailability_feasible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Soft positive request + hard unavailability = feasible with violation."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # W001 is unavailable in period 1
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                availability_type="unavailable",
            ),
        ]

        # W001 has a soft positive request to work in period 1
        requests = [
            SchedulingRequest(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                request_type="positive",
                shift_type_id="day",
                priority=1,
            )
        ]

        # Apply availability (hard constraint)
        avail_constraint = AvailabilityConstraint(model, variables)
        avail_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        # Apply SOFT request constraint
        request_config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        request_constraint = RequestConstraint(model, variables, request_config)
        request_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        # Minimize violations
        if request_constraint.violation_variables:
            penalty_terms = []
            for var_name, viol_var in request_constraint.violation_variables.items():
                priority = request_constraint.violation_priorities.get(var_name, 1)
                penalty_terms.append(viol_var * priority * request_config.weight)
            model.minimize(sum(penalty_terms))

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        # Should be feasible (soft request is violated)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # W001 cannot work in period 1 (unavailable)
        assert solver.value(variables.get_assignment_var("W001", 1, "day")) == 0

        # The soft request violation should be 1
        violation_vars = list(request_constraint.violation_variables.values())
        violation_sum = sum(solver.value(v) for v in violation_vars)
        assert violation_sum >= 1  # At least one violation


class TestPartialOverlapScenarios:
    """Tests for partial overlap between availability and requests."""

    def test_request_starts_before_unavailability(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Request spans from available period into unavailable period."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # W001 unavailable in periods 2 and 3
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[2][0],
                end_date=period_dates[3][1],
                availability_type="unavailable",
            ),
        ]

        # Request spans periods 1-2 (partial overlap with unavailability)
        requests = [
            SchedulingRequest(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[2][1],
                request_type="positive",
                shift_type_id="day",
                priority=1,
            )
        ]

        # Apply constraints
        avail_constraint = AvailabilityConstraint(model, variables)
        avail_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        request_config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        request_constraint = RequestConstraint(model, variables, request_config)
        request_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        # Add basic coverage
        for period in range(4):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Minimize violations
        if request_constraint.violation_variables:
            penalty_terms = []
            for var_name, viol_var in request_constraint.violation_variables.items():
                priority = request_constraint.violation_priorities.get(var_name, 1)
                penalty_terms.append(viol_var * priority * request_config.weight)
            model.minimize(sum(penalty_terms))

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # W001 can work in period 1 (available)
        # W001 cannot work in period 2 (unavailable)
        assert solver.value(variables.get_assignment_var("W001", 2, "day")) == 0


class TestNegativeRequestWithUnavailability:
    """Tests for negative requests combined with unavailability."""

    def test_negative_request_with_unavailability_redundant_but_valid(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Negative request + unavailability is redundant but should work."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # W001 unavailable in period 1
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                availability_type="unavailable",
            ),
        ]

        # W001 also has negative request for period 1 (redundant)
        requests = [
            SchedulingRequest(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                request_type="negative",
                shift_type_id="day",
                priority=1,
            )
        ]

        # Apply constraints
        avail_constraint = AvailabilityConstraint(model, variables)
        avail_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        request_config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        request_constraint = RequestConstraint(model, variables, request_config)
        request_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        # Add basic coverage
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

        # W001 not assigned (unavailable) - negative request also satisfied
        assert solver.value(variables.get_assignment_var("W001", 1, "day")) == 0

        # Negative request should have no violation (request honored)
        violation_vars = list(request_constraint.violation_variables.values())
        violation_sum = sum(solver.value(v) for v in violation_vars)
        assert violation_sum == 0


class TestBoundaryDateScenarios:
    """Tests for boundary conditions between availability and requests."""

    def test_request_ends_when_unavailability_starts(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Request end == availability start (edge touching)."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # W001 unavailable starting period 2
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[2][0],
                end_date=period_dates[3][1],
                availability_type="unavailable",
            ),
        ]

        # Request ends at period 1 (just before unavailability)
        requests = [
            SchedulingRequest(
                worker_id="W001",
                start_date=period_dates[0][0],
                end_date=period_dates[1][1],  # Ends where unavailability starts
                request_type="positive",
                shift_type_id="day",
                priority=1,
            )
        ]

        avail_constraint = AvailabilityConstraint(model, variables)
        avail_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        request_config = ConstraintConfig(enabled=True, is_hard=True, weight=100)
        request_constraint = RequestConstraint(model, variables, request_config)
        request_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        # Should be feasible - no overlap
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # W001 must work in period 0 and 1 (hard request)
        assert solver.value(variables.get_assignment_var("W001", 0, "day")) == 1
        assert solver.value(variables.get_assignment_var("W001", 1, "day")) == 1


class TestMultipleOverlappingConstraints:
    """Tests for complex scenarios with multiple overlapping constraints."""

    def test_multiple_workers_with_overlapping_constraints(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Multiple workers with various availability/request combinations."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # W001 unavailable period 1, W002 unavailable period 2
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                availability_type="unavailable",
            ),
            Availability(
                worker_id="W002",
                start_date=period_dates[2][0],
                end_date=period_dates[2][1],
                availability_type="unavailable",
            ),
        ]

        # W001 wants period 0, W002 wants period 0 (conflict)
        # W001 wants period 1 (overlaps unavailability - soft request)
        requests = [
            SchedulingRequest(
                worker_id="W001",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="positive",
                shift_type_id="day",
                priority=2,
            ),
            SchedulingRequest(
                worker_id="W002",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="positive",
                shift_type_id="day",
                priority=1,  # Lower priority
            ),
            SchedulingRequest(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                request_type="positive",
                shift_type_id="day",
                priority=3,  # High priority but unavailable
            ),
        ]

        avail_constraint = AvailabilityConstraint(model, variables)
        avail_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        request_config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
        request_constraint = RequestConstraint(model, variables, request_config)
        request_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        # Add coverage
        for period in range(4):
            for shift_type in shift_types:
                vars_for_shift = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(vars_for_shift) == shift_type.workers_required)

        # Minimize violations with priority weighting
        if request_constraint.violation_variables:
            penalty_terms = []
            for var_name, viol_var in request_constraint.violation_variables.items():
                priority = request_constraint.violation_priorities.get(var_name, 1)
                penalty_terms.append(viol_var * priority * request_config.weight)
            model.minimize(sum(penalty_terms))

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # W001 unavailable in period 1
        assert solver.value(variables.get_assignment_var("W001", 1, "day")) == 0
        # W002 unavailable in period 2
        assert solver.value(variables.get_assignment_var("W002", 2, "day")) == 0

    def test_shift_specific_unavailability_with_request_for_other_shift(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Worker unavailable for night shift can still fulfill day shift request."""
        model = cp_model.CpModel()
        builder = VariableBuilder(model, workers, shift_types, num_periods=4)
        variables = builder.build()

        # W001 unavailable for night shifts only in period 1
        availabilities = [
            Availability(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                availability_type="unavailable",
                shift_type_id="night",  # Only night shifts blocked
            ),
        ]

        # W001 has hard positive request for DAY shift in period 1
        requests = [
            SchedulingRequest(
                worker_id="W001",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                request_type="positive",
                shift_type_id="day",  # Different shift type
                priority=1,
            )
        ]

        avail_constraint = AvailabilityConstraint(model, variables)
        avail_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            availabilities=availabilities,
            period_dates=period_dates,
        )

        request_config = ConstraintConfig(enabled=True, is_hard=True, weight=100)
        request_constraint = RequestConstraint(model, variables, request_config)
        request_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=4,
            requests=requests,
            period_dates=period_dates,
        )

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        # Should be feasible - unavailability is for night, request is for day
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # W001 can work day shift (hard request satisfied)
        assert solver.value(variables.get_assignment_var("W001", 1, "day")) == 1
        # W001 cannot work night shift (unavailable)
        assert solver.value(variables.get_assignment_var("W001", 1, "night")) == 0
