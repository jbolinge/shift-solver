"""E2E tests for infeasible scheduling scenarios.

scheduler-79: Tests for infeasible coverage + restriction combinations that
may or may not be caught by FeasibilityChecker.
"""

from datetime import time

import pytest

from shift_solver.models import Availability, ShiftType
from shift_solver.solver import ShiftSolver
from shift_solver.validation import FeasibilityChecker

from .conftest import create_period_dates, solve_and_verify


@pytest.mark.e2e
class TestExactInfeasibility:
    """Tests for exact infeasibility detection."""

    def test_three_required_two_eligible_infeasible(self, worker_factory) -> None:
        """3 workers required for shift, only 2 eligible (1 restricted)."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(),
            worker_factory(),
        ]

        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=3,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        # FeasibilityChecker should catch this
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )
        result = checker.check()
        assert not result.is_feasible
        assert any(i["type"] == "restriction" for i in result.issues)

        # Solver should also fail
        solve_result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            expect_feasible=False,
        )
        assert not solve_result.success

    def test_marginal_feasibility_exactly_enough(self, worker_factory) -> None:
        """3 workers required, exactly 3 eligible (tight feasibility)."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(),
            worker_factory(),
            worker_factory(),
        ]

        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=3,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        # Should be exactly feasible
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )
        result = checker.check()
        assert result.is_feasible

        # Solver should succeed
        solve_result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )
        assert solve_result.success


@pytest.mark.e2e
class TestMultipleShiftInfeasibility:
    """Tests for multiple shift type infeasibility combinations."""

    def test_some_shifts_feasible_some_not(self, worker_factory) -> None:
        """Day shift feasible, night shift infeasible."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(),  # Only one can work night
        ]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,  # Feasible - 3 workers can work day
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=2,  # Infeasible - only 1 can work night
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        # Checker should detect night shift infeasibility
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )
        result = checker.check()
        assert not result.is_feasible
        # Check that issue mentions night shift specifically
        restriction_issue = next(
            i for i in result.issues if i["type"] == "restriction"
        )
        assert "night" in restriction_issue["shift_type_id"].lower()

    def test_combined_restrictions_multiple_shifts(self, worker_factory) -> None:
        """Worker restricted from multiple shifts causes infeasibility."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["day", "night"])),
            worker_factory(restricted_shifts=frozenset(["day"])),
            worker_factory(restricted_shifts=frozenset(["night"])),
        ]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,  # Only W003 not restricted - infeasible
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=2,  # Only W002 not restricted - infeasible
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )
        result = checker.check()
        assert not result.is_feasible
        # Both shifts should be flagged
        restriction_issues = [i for i in result.issues if i["type"] == "restriction"]
        assert len(restriction_issues) >= 1


@pytest.mark.e2e
class TestAllWorkersRestricted:
    """Tests for scenarios where no one can work a shift."""

    def test_all_workers_restricted_from_one_shift(self, worker_factory) -> None:
        """All workers restricted from a specific shift type."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["critical"])),
            worker_factory(restricted_shifts=frozenset(["critical"])),
            worker_factory(restricted_shifts=frozenset(["critical"])),
            worker_factory(restricted_shifts=frozenset(["critical"])),
        ]

        shift_types = [
            ShiftType(
                id="normal",
                name="Normal Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="critical",
                name="Critical Shift",
                category="day",
                start_time=time(17, 0),
                end_time=time(1, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )
        result = checker.check()
        assert not result.is_feasible

        # Message should be clear about 0 available
        restriction_issue = next(
            i for i in result.issues if i["type"] == "restriction"
        )
        assert restriction_issue["workers_available"] == 0
        assert restriction_issue["workers_required"] == 1


@pytest.mark.e2e
class TestPartialPeriodInfeasibility:
    """Tests for infeasibility in specific periods."""

    def test_feasible_some_periods_not_others(self, worker_factory) -> None:
        """Some periods feasible, others infeasible due to availability."""
        workers = [
            worker_factory(),
            worker_factory(),
            worker_factory(),
        ]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        periods = create_period_dates(num_periods=3)

        # All workers unavailable for period 1 only
        availabilities = [
            Availability(
                worker_id=w.id,
                start_date=periods[1][0],
                end_date=periods[1][1],
                availability_type="unavailable",
            )
            for w in workers
        ]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            availabilities=availabilities,
        )
        result = checker.check()
        assert not result.is_feasible

        # Issue should mention period 1
        availability_issue = next(
            i for i in result.issues if i["type"] == "availability"
        )
        assert availability_issue["period_index"] == 1

    def test_restriction_plus_availability_per_period(self, worker_factory) -> None:
        """Combined restriction and availability makes specific period infeasible."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(),  # Can work night
            worker_factory(),  # Can work night
        ]

        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=2)

        # Both night-capable workers unavailable for period 0
        availabilities = [
            Availability(
                worker_id=workers[1].id,
                start_date=periods[0][0],
                end_date=periods[0][1],
                availability_type="unavailable",
            ),
            Availability(
                worker_id=workers[2].id,
                start_date=periods[0][0],
                end_date=periods[0][1],
                availability_type="unavailable",
            ),
        ]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            availabilities=availabilities,
        )
        result = checker.check()
        assert not result.is_feasible

        # Should detect combined issue for period 0
        combined_issue = next(
            i for i in result.issues if i["type"] == "combined"
        )
        assert combined_issue["period_index"] == 0


@pytest.mark.e2e
class TestErrorMessageQuality:
    """Tests for clear and helpful error messages."""

    def test_error_message_lists_shift_name(self, worker_factory) -> None:
        """Error message should include human-readable shift name."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["night_shift"])),
            worker_factory(restricted_shifts=frozenset(["night_shift"])),
        ]

        shift_types = [
            ShiftType(
                id="night_shift",
                name="Night Shift (8pm-4am)",
                category="night",
                start_time=time(20, 0),
                end_time=time(4, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )
        result = checker.check()
        assert not result.is_feasible

        restriction_issue = next(
            i for i in result.issues if i["type"] == "restriction"
        )
        # Message should contain the human-readable name
        assert "Night Shift" in restriction_issue["message"]

    def test_error_message_shows_counts(self, worker_factory) -> None:
        """Error message should show available vs required counts."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["special"])),
            worker_factory(restricted_shifts=frozenset(["special"])),
            worker_factory(restricted_shifts=frozenset(["special"])),
            worker_factory(),  # One available
        ]

        shift_types = [
            ShiftType(
                id="special",
                name="Special Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )
        result = checker.check()
        assert not result.is_feasible

        restriction_issue = next(
            i for i in result.issues if i["type"] == "restriction"
        )
        # Message should show "1 available, 3 required"
        assert "1 available" in restriction_issue["message"]
        assert "3 required" in restriction_issue["message"]


@pytest.mark.e2e
class TestFeasibilityCheckerVsSolver:
    """Tests comparing FeasibilityChecker and solver results."""

    def test_checker_and_solver_agree_on_infeasible(self, worker_factory) -> None:
        """Both checker and solver should agree on infeasibility."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(restricted_shifts=frozenset(["night"])),
        ]

        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        # Check with FeasibilityChecker
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )
        checker_result = checker.check()

        # Check with solver
        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            schedule_id="INFEASIBLE-TEST",
        )
        solver_result = solver.solve(time_limit_seconds=30)

        # Both should agree
        assert not checker_result.is_feasible
        assert not solver_result.success

    def test_checker_and_solver_agree_on_feasible(self, worker_factory) -> None:
        """Both checker and solver should agree on feasibility."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(),
            worker_factory(),
        ]

        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,  # 2 workers can work night
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=1)

        # Check with FeasibilityChecker
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )
        checker_result = checker.check()

        # Check with solver
        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            schedule_id="FEASIBLE-TEST",
        )
        solver_result = solver.solve(time_limit_seconds=30)

        # Both should agree
        assert checker_result.is_feasible
        assert solver_result.success


@pytest.mark.e2e
class TestEdgeCaseInfeasibility:
    """Edge cases for infeasibility detection."""

    def test_minimal_workers_required_one(self, worker_factory) -> None:
        """Shift requiring 1 worker with 1 unrestricted worker is feasible."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["any"])),
            worker_factory(),  # One unrestricted worker
        ]

        shift_types = [
            ShiftType(
                id="any",
                name="Any Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,  # Minimum required
            ),
        ]

        periods = create_period_dates(num_periods=1)

        # Should be feasible with one unrestricted worker
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )
        result = checker.check()
        assert result.is_feasible

    def test_empty_shift_types_raises_or_handles(self, worker_factory) -> None:
        """No shift types triggers error in FeasibilityChecker."""
        workers = [worker_factory() for _ in range(3)]
        periods = create_period_dates(num_periods=1)

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=[],
            period_dates=periods,
        )
        # Current behavior: raises ValueError on empty shift_types
        # This documents the current behavior - may want to handle gracefully
        with pytest.raises(ValueError):
            checker.check()
