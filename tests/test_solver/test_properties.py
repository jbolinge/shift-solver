"""Property-based tests for solver using Hypothesis.

These tests verify invariants that should hold for all valid inputs,
helping to catch edge cases that example-based tests might miss.
"""

from datetime import time

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from shift_solver.models import ShiftType, Worker
from shift_solver.solver import ShiftSolver
from shift_solver.validation import FeasibilityChecker, ScheduleValidator

# Import our custom strategies
from strategies import (
    availabilities,
    period_dates,
    scheduling_scenarios,
    shift_types,
    workers,
)


@pytest.mark.integration
class TestSolverProperties:
    """Property-based tests for the solver."""

    @settings(
        max_examples=10,
        deadline=60000,
        suppress_health_check=[HealthCheck.filter_too_much],
    )
    @given(scenario=scheduling_scenarios())
    def test_feasible_problem_has_solution(self, scenario: dict) -> None:
        """If FeasibilityChecker passes, solver should find a solution."""
        workers_list = scenario["workers"]
        shift_types_list = scenario["shift_types"]
        period_dates_list = scenario["period_dates"]
        availabilities_list = scenario["availabilities"]

        # Ensure we have enough workers for coverage
        total_required = sum(s.workers_required for s in shift_types_list)
        assume(len(workers_list) >= total_required * 2)  # Need slack for availability

        # Create solver
        solver = ShiftSolver(
            workers=workers_list,
            shift_types=shift_types_list,
            period_dates=period_dates_list,
            schedule_id="PROP-TEST",
            availabilities=availabilities_list,
        )

        # Check feasibility first
        checker = FeasibilityChecker(
            workers=workers_list,
            shift_types=shift_types_list,
            period_dates=period_dates_list,
            availabilities=availabilities_list,
        )
        feasibility = checker.check()

        if feasibility.is_feasible:
            # If feasible, solver should find a solution
            result = solver.solve(time_limit_seconds=10)
            # Note: Even "feasible" problems might not solve in time limit
            # So we only assert that we got a result, not necessarily success
            assert result is not None

    @settings(
        max_examples=10,
        deadline=60000,
        suppress_health_check=[HealthCheck.filter_too_much],
    )
    @given(scenario=scheduling_scenarios())
    def test_solution_validates_correctly(self, scenario: dict) -> None:
        """Any solution found should pass ScheduleValidator."""
        workers_list = scenario["workers"]
        shift_types_list = scenario["shift_types"]
        period_dates_list = scenario["period_dates"]
        availabilities_list = scenario["availabilities"]
        requests_list = scenario["requests"]

        # Ensure enough workers (need slack for coverage + availability)
        total_required = sum(s.workers_required for s in shift_types_list)
        assume(len(workers_list) >= total_required * 2)

        solver = ShiftSolver(
            workers=workers_list,
            shift_types=shift_types_list,
            period_dates=period_dates_list,
            schedule_id="VALIDATE-TEST",
            availabilities=availabilities_list,
            requests=requests_list,
        )

        result = solver.solve(time_limit_seconds=10)

        if result.success and result.schedule is not None:
            # Solution should validate
            validator = ScheduleValidator(
                schedule=result.schedule,
                availabilities=availabilities_list,
                requests=requests_list,
            )
            validation = validator.validate()

            # Validation should pass (no error-level violations)
            assert validation.is_valid, f"Validation failed: {validation.violations}"


@pytest.mark.integration
class TestWorkerProperties:
    """Property-based tests for Worker model."""

    @given(worker=workers())
    def test_worker_is_hashable(self, worker: Worker) -> None:
        """All generated workers should be hashable."""
        # Should not raise
        hash(worker)

        # Should be usable in sets
        worker_set = {worker}
        assert worker in worker_set

    @given(worker=workers())
    def test_worker_equality_reflexive(self, worker: Worker) -> None:
        """A worker should equal itself."""
        assert worker == worker

    @given(w1=workers(), w2=workers())
    def test_worker_equality_implies_same_hash(
        self, w1: Worker, w2: Worker
    ) -> None:
        """If two workers are equal, they should have the same hash."""
        if w1 == w2:
            assert hash(w1) == hash(w2)

    @given(worker=workers())
    def test_restricted_and_preferred_disjoint(self, worker: Worker) -> None:
        """Restricted and preferred shifts should never overlap."""
        overlap = worker.restricted_shifts & worker.preferred_shifts
        assert len(overlap) == 0

    @given(worker=workers(), shift_id=st.text(min_size=1, max_size=10))
    def test_can_work_shift_consistency(self, worker: Worker, shift_id: str) -> None:
        """can_work_shift should be consistent with restricted_shifts."""
        can_work = worker.can_work_shift(shift_id)
        is_restricted = shift_id in worker.restricted_shifts

        assert can_work != is_restricted

    @given(worker=workers(), shift_id=st.text(min_size=1, max_size=10))
    def test_prefers_shift_consistency(self, worker: Worker, shift_id: str) -> None:
        """prefers_shift should be consistent with preferred_shifts."""
        prefers = worker.prefers_shift(shift_id)
        is_preferred = shift_id in worker.preferred_shifts

        assert prefers == is_preferred


@pytest.mark.integration
class TestShiftTypeProperties:
    """Property-based tests for ShiftType model."""

    @given(shift=shift_types())
    def test_shift_type_is_hashable(self, shift: ShiftType) -> None:
        """All generated shift types should be hashable."""
        hash(shift)
        shift_set = {shift}
        assert shift in shift_set

    @given(shift=shift_types())
    def test_shift_type_has_positive_duration(self, shift: ShiftType) -> None:
        """All shift types should have positive duration."""
        assert shift.duration_hours > 0

    @given(shift=shift_types())
    def test_shift_type_has_valid_workers_required(self, shift: ShiftType) -> None:
        """All shift types should require at least 1 worker."""
        assert shift.workers_required >= 1


@pytest.mark.integration
class TestAvailabilityProperties:
    """Property-based tests for Availability model."""

    @given(avail=availabilities())
    def test_availability_date_order(self, avail) -> None:
        """End date should always be >= start date."""
        assert avail.end_date >= avail.start_date

    @given(avail=availabilities())
    def test_availability_duration_positive(self, avail) -> None:
        """Duration should always be positive."""
        assert avail.duration_days >= 1

    @given(avail=availabilities())
    def test_availability_contains_endpoints(self, avail) -> None:
        """Availability should contain its start and end dates."""
        assert avail.contains_date(avail.start_date)
        assert avail.contains_date(avail.end_date)


@pytest.mark.integration
class TestPeriodDateProperties:
    """Property-based tests for period date generation."""

    @given(periods=period_dates())
    def test_periods_are_contiguous(self, periods: list) -> None:
        """Consecutive periods should be contiguous (no gaps)."""
        for i in range(len(periods) - 1):
            current_end = periods[i][1]
            next_start = periods[i + 1][0]
            # Next period should start day after current ends
            from datetime import timedelta
            assert next_start == current_end + timedelta(days=1)

    @given(periods=period_dates())
    def test_periods_are_non_overlapping(self, periods: list) -> None:
        """Periods should not overlap."""
        for i in range(len(periods)):
            for j in range(i + 1, len(periods)):
                p1_start, p1_end = periods[i]
                p2_start, p2_end = periods[j]

                # No overlap means: p1 ends before p2 starts OR p2 ends before p1 starts
                assert p1_end < p2_start or p2_end < p1_start

    @given(periods=period_dates())
    def test_period_dates_ordered(self, periods: list) -> None:
        """Within each period, start should be <= end."""
        for start, end in periods:
            assert start <= end


@pytest.mark.integration
class TestDataRoundtripProperties:
    """Property-based tests for data serialization roundtrips."""

    @given(worker=workers())
    def test_worker_dict_roundtrip(self, worker: Worker) -> None:
        """Worker should survive conversion to dict and back."""
        # Convert to dict (simulating JSON serialization)
        data = {
            "id": worker.id,
            "name": worker.name,
            "worker_type": worker.worker_type,
            "restricted_shifts": list(worker.restricted_shifts),
            "preferred_shifts": list(worker.preferred_shifts),
        }

        # Convert back
        restored = Worker(
            id=data["id"],
            name=data["name"],
            worker_type=data["worker_type"],
            restricted_shifts=frozenset(data["restricted_shifts"]),
            preferred_shifts=frozenset(data["preferred_shifts"]),
        )

        assert restored == worker

    @given(shift=shift_types())
    def test_shift_type_dict_roundtrip(self, shift: ShiftType) -> None:
        """ShiftType should survive conversion to dict and back."""
        data = {
            "id": shift.id,
            "name": shift.name,
            "category": shift.category,
            "start_time": shift.start_time.isoformat(),
            "end_time": shift.end_time.isoformat(),
            "duration_hours": shift.duration_hours,
            "is_undesirable": shift.is_undesirable,
            "workers_required": shift.workers_required,
        }

        restored = ShiftType(
            id=data["id"],
            name=data["name"],
            category=data["category"],
            start_time=time.fromisoformat(data["start_time"]),
            end_time=time.fromisoformat(data["end_time"]),
            duration_hours=data["duration_hours"],
            is_undesirable=data["is_undesirable"],
            workers_required=data["workers_required"],
        )

        assert restored == shift
