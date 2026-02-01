"""E2E tests for worker restriction complexity.

scheduler-45: Tests complex worker restriction scenarios including multiple
restrictions per worker, bottlenecks, and pyramid patterns.
"""

from datetime import time

import pytest

from shift_solver.models import Availability, ShiftType
from shift_solver.validation import FeasibilityChecker

from .conftest import create_period_dates, solve_and_verify


@pytest.mark.e2e
class TestMultipleRestrictionsPerWorker:
    """Tests for workers with 5+ restricted shift types."""

    def test_worker_with_five_restrictions(self, worker_factory, periods_4) -> None:
        """Worker restricted from 5 different shift types."""
        workers = [
            worker_factory(
                restricted_shifts=frozenset(
                    ["shift_a", "shift_b", "shift_c", "shift_d", "shift_e"]
                )
            ),
            worker_factory(),
            worker_factory(),
            worker_factory(),
            worker_factory(),
            worker_factory(),
        ]

        shift_types = [
            ShiftType(
                id=f"shift_{chr(97+i)}",  # a through f
                name=f"Shift {chr(65+i)}",
                category="day" if i < 3 else "night",
                start_time=time(6 + i * 2, 0),
                end_time=time((14 + i * 2) % 24, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=i >= 3,
            )
            for i in range(6)
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
        )

        assert result.success
        # Worker 0 can only work shift_f
        for period in result.schedule.periods:
            if workers[0].id in period.assignments:
                for shift in period.assignments[workers[0].id]:
                    assert shift.shift_type_id == "shift_f"

    def test_multiple_workers_with_heavy_restrictions(
        self, worker_factory, periods_4
    ) -> None:
        """Multiple workers each with many restrictions."""
        workers = [
            worker_factory(
                restricted_shifts=frozenset(["night", "evening", "weekend"])
            ),
            worker_factory(
                restricted_shifts=frozenset(["morning", "night", "weekend"])
            ),
            worker_factory(
                restricted_shifts=frozenset(["morning", "evening", "night"])
            ),
            worker_factory(),  # Unrestricted
            worker_factory(),  # Unrestricted
            worker_factory(),  # Unrestricted
        ]

        shift_types = [
            ShiftType(
                id="morning",
                name="Morning",
                category="day",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="evening",
                name="Evening",
                category="evening",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
            ShiftType(
                id="weekend",
                name="Weekend",
                category="weekend",
                start_time=time(8, 0),
                end_time=time(16, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
        )

        assert result.success


@pytest.mark.e2e
class TestRestrictionBottlenecks:
    """Tests for single worker bottlenecks on critical shifts."""

    def test_single_worker_for_critical_shift(self, worker_factory, periods_4) -> None:
        """Only one worker can work a critical shift."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["critical"])),
            worker_factory(restricted_shifts=frozenset(["critical"])),
            worker_factory(restricted_shifts=frozenset(["critical"])),
            worker_factory(),  # The only one who can do critical
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
                category="critical",
                start_time=time(17, 0),
                end_time=time(1, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
        )

        assert result.success
        # Worker 3 must work critical in every period
        for period in result.schedule.periods:
            critical_assigned = False
            for worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    if shift.shift_type_id == "critical":
                        assert worker_id == workers[3].id
                        critical_assigned = True
            assert critical_assigned

    def test_two_worker_bottleneck_for_two_required(
        self, worker_factory, periods_4
    ) -> None:
        """Two workers available for shift requiring two."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["special"])),
            worker_factory(restricted_shifts=frozenset(["special"])),
            worker_factory(),  # Can work special
            worker_factory(),  # Can work special
        ]

        shift_types = [
            ShiftType(
                id="normal",
                name="Normal",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="special",
                name="Special",
                category="special",
                start_time=time(17, 0),
                end_time=time(1, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
        )

        assert result.success


@pytest.mark.e2e
class TestPyramidRestrictions:
    """Tests for pyramid/escalating restriction patterns."""

    def test_increasing_restrictions_per_worker(self, worker_factory) -> None:
        """Workers with 0, 1, 2, 3 restrictions respectively."""
        workers = [
            worker_factory(),  # No restrictions
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(restricted_shifts=frozenset(["night", "weekend"])),
            worker_factory(
                restricted_shifts=frozenset(["night", "weekend", "evening"])
            ),
            worker_factory(),  # No restrictions
            worker_factory(),  # No restrictions
        ]

        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="evening",
                name="Evening",
                category="evening",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
            ShiftType(
                id="weekend",
                name="Weekend",
                category="weekend",
                start_time=time(8, 0),
                end_time=time(16, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=2)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success

    def test_inverse_pyramid_restrictions(self, worker_factory) -> None:
        """Inverse pyramid - most restricted first, least restricted last."""
        workers = [
            worker_factory(
                restricted_shifts=frozenset(["night", "weekend", "evening", "day"])
            ),  # 4 restrictions - only late can work
            worker_factory(
                restricted_shifts=frozenset(["night", "weekend", "evening"])
            ),  # 3 restrictions
            worker_factory(restricted_shifts=frozenset(["night", "weekend"])),  # 2
            worker_factory(restricted_shifts=frozenset(["night"])),  # 1
            worker_factory(),  # 0 restrictions
            worker_factory(),  # 0 restrictions
        ]

        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="evening",
                name="Evening",
                category="evening",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
            ShiftType(
                id="weekend",
                name="Weekend",
                category="weekend",
                start_time=time(8, 0),
                end_time=time(16, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
            ShiftType(
                id="late",
                name="Late",
                category="late",
                start_time=time(16, 0),
                end_time=time(0, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        periods = create_period_dates(num_periods=2)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success


@pytest.mark.e2e
class TestDynamicRestrictionsByPeriod:
    """Tests for restrictions that vary by period (via availability)."""

    def test_period_varying_availability_as_restrictions(
        self, worker_factory, periods_4
    ) -> None:
        """Model dynamic restrictions using availability."""
        workers = [worker_factory() for _ in range(6)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        # Worker 0 unavailable for night in period 0
        # Worker 1 unavailable for night in period 1, etc.
        availabilities = [
            Availability(
                worker_id=workers[i].id,
                start_date=periods_4[i][0],
                end_date=periods_4[i][1],
                availability_type="unavailable",
                shift_type_id="night",
            )
            for i in range(4)
        ]

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            availabilities=availabilities,
        )

        assert result.success

    def test_alternating_availability_pattern(
        self, worker_factory, periods_4
    ) -> None:
        """Workers alternate availability by period."""
        workers = [worker_factory() for _ in range(8)]

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

        # Workers 0-3 unavailable in even periods, 4-7 unavailable in odd
        availabilities = []
        for period_idx, (start, end) in enumerate(periods_4):
            unavailable_range = range(4) if period_idx % 2 == 0 else range(4, 8)
            for i in unavailable_range:
                availabilities.append(
                    Availability(
                        worker_id=workers[i].id,
                        start_date=start,
                        end_date=end,
                        availability_type="unavailable",
                    )
                )

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            availabilities=availabilities,
        )

        assert result.success


@pytest.mark.e2e
class TestCircularRestrictionDependencies:
    """Tests for circular or complex restriction dependencies."""

    def test_circular_restriction_pattern(self, worker_factory) -> None:
        """Workers form a circular restriction pattern."""
        # Worker 0 can't do A, Worker 1 can't do B, Worker 2 can't do C, etc.
        workers = [
            worker_factory(restricted_shifts=frozenset(["shift_a"])),
            worker_factory(restricted_shifts=frozenset(["shift_b"])),
            worker_factory(restricted_shifts=frozenset(["shift_c"])),
            worker_factory(restricted_shifts=frozenset(["shift_a"])),
            worker_factory(restricted_shifts=frozenset(["shift_b"])),
            worker_factory(restricted_shifts=frozenset(["shift_c"])),
        ]

        shift_types = [
            ShiftType(
                id="shift_a",
                name="Shift A",
                category="a",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="shift_b",
                name="Shift B",
                category="b",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="shift_c",
                name="Shift C",
                category="c",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=2)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success

    def test_overlapping_restriction_sets(self, worker_factory) -> None:
        """Workers with overlapping but not identical restriction sets."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["a", "b"])),
            worker_factory(restricted_shifts=frozenset(["b", "c"])),
            worker_factory(restricted_shifts=frozenset(["c", "a"])),
            worker_factory(restricted_shifts=frozenset(["a"])),
            worker_factory(restricted_shifts=frozenset(["b"])),
            worker_factory(restricted_shifts=frozenset(["c"])),
            worker_factory(),
            worker_factory(),
        ]

        shift_types = [
            ShiftType(
                id="a",
                name="Shift A",
                category="a",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="b",
                name="Shift B",
                category="b",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="c",
                name="Shift C",
                category="c",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=2)

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
        )

        assert result.success

    def test_feasibility_checker_with_complex_restrictions(
        self, worker_factory
    ) -> None:
        """Verify FeasibilityChecker handles complex restriction patterns."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["critical"])),
            worker_factory(restricted_shifts=frozenset(["critical"])),
            worker_factory(restricted_shifts=frozenset(["critical"])),
            # No unrestricted workers!
        ]

        shift_types = [
            ShiftType(
                id="critical",
                name="Critical",
                category="critical",
                start_time=time(9, 0),
                end_time=time(17, 0),
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
        assert any(issue["type"] == "restriction" for issue in result.issues)
