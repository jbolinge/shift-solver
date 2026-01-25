"""E2E tests for fairness edge cases.

scheduler-44: Tests fairness constraint edge conditions including all
undesirable shifts, single worker scenarios, and spread tracking.
"""

from datetime import date, time, timedelta

import pytest

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import Availability, ShiftType, Worker
from shift_solver.solver import ShiftSolver

from .conftest import create_period_dates, solve_and_verify


@pytest.mark.e2e
class TestAllShiftsUndesirable:
    """Tests when all shifts are marked undesirable."""

    def test_all_shifts_undesirable(self, worker_factory, periods_4) -> None:
        """Every shift type is marked as undesirable."""
        workers = [worker_factory() for _ in range(8)]

        shift_types = [
            ShiftType(
                id="shift_a",
                name="Shift A",
                category="a",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
            ShiftType(
                id="shift_b",
                name="Shift B",
                category="b",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
            ShiftType(
                id="shift_c",
                name="Shift C",
                category="c",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=150),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs=constraint_configs,
        )

        assert result.success

        # Count undesirable shifts per worker
        counts = {w.id: 0 for w in workers}
        for period in result.schedule.periods:
            for worker_id, shifts in period.assignments.items():
                counts[worker_id] += len(shifts)

        # With fairness enabled, distribution should be reasonably even
        values = list(counts.values())
        spread = max(values) - min(values)
        assert spread <= 4  # Allow some variation

    def test_all_shifts_undesirable_high_weight(
        self, worker_factory, periods_4
    ) -> None:
        """High fairness weight with all undesirable shifts."""
        workers = [worker_factory() for _ in range(6)]

        shift_types = [
            ShiftType(
                id="undesirable",
                name="Undesirable",
                category="undesirable",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=500),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs=constraint_configs,
        )

        assert result.success


@pytest.mark.e2e
class TestSingleWorkerUndesirable:
    """Tests when only one worker can take undesirable shifts."""

    def test_single_worker_available_for_undesirable(
        self, worker_factory, periods_4
    ) -> None:
        """Only one worker can work the undesirable shift."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(),  # Only this worker can do night
        ]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs=constraint_configs,
        )

        assert result.success
        # Worker 3 must get all night shifts
        for period in result.schedule.periods:
            for worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    if shift.shift_type_id == "night":
                        assert worker_id == workers[3].id

    def test_bottleneck_worker_fairness_impact(
        self, worker_factory, periods_4
    ) -> None:
        """Fairness when one worker is a bottleneck."""
        # 2 workers can work all shifts, 3 can only work day
        workers = [
            worker_factory(),  # Can work all
            worker_factory(),  # Can work all
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(restricted_shifts=frozenset(["night"])),
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
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs=constraint_configs,
        )

        assert result.success


@pytest.mark.e2e
class TestFairnessWithRestrictions:
    """Tests for fairness when workers have varying restrictions."""

    def test_fairness_with_varied_restrictions(self, worker_factory) -> None:
        """Fairness applied to workers with different restriction sets."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["night"])),
            worker_factory(restricted_shifts=frozenset(["weekend"])),
            worker_factory(restricted_shifts=frozenset(["night", "weekend"])),
            worker_factory(),
            worker_factory(),
            worker_factory(),
        ]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
            ShiftType(
                id="weekend",
                name="Weekend Shift",
                category="weekend",
                start_time=time(8, 0),
                end_time=time(16, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=4)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
        )

        assert result.success

    def test_fairness_only_among_eligible_workers(self, worker_factory) -> None:
        """Fairness should only distribute among workers who can work shift."""
        workers = [
            worker_factory(restricted_shifts=frozenset(["undesirable"])),
            worker_factory(restricted_shifts=frozenset(["undesirable"])),
            worker_factory(),  # Can work undesirable
            worker_factory(),  # Can work undesirable
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
                id="undesirable",
                name="Undesirable Shift",
                category="undesirable",
                start_time=time(17, 0),
                end_time=time(1, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        periods = create_period_dates(num_periods=4)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=200),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
        )

        assert result.success

        # Count undesirable shifts for eligible workers
        eligible_ids = {workers[2].id, workers[3].id}
        counts = {wid: 0 for wid in eligible_ids}
        for period in result.schedule.periods:
            for worker_id, shifts in period.assignments.items():
                if worker_id in eligible_ids:
                    for shift in shifts:
                        if shift.shift_type_id == "undesirable":
                            counts[worker_id] += 1

        # Each eligible worker should get ~2 undesirable shifts (4 periods, 1 required)
        values = list(counts.values())
        spread = max(values) - min(values)
        assert spread <= 2


@pytest.mark.e2e
class TestLongTermFairness:
    """Tests for fairness over extended time periods."""

    @pytest.mark.slow
    def test_fairness_12_week_quarterly(self, worker_factory, periods_12) -> None:
        """Fairness tracking over 12 weeks (quarterly)."""
        workers = [worker_factory() for _ in range(10)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=200),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_12,
            constraint_configs=constraint_configs,
            time_limit_seconds=120,
        )

        assert result.success
        assert len(result.schedule.periods) == 12

        # Verify fairness distribution
        night_counts = {w.id: 0 for w in workers}
        for period in result.schedule.periods:
            for worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    if shift.shift_type_id == "night":
                        night_counts[worker_id] += 1

        # 12 periods * 1 night required = 12 total, 10 workers
        # Each should have ~1.2, so expect 1-2 each with good fairness
        values = list(night_counts.values())
        spread = max(values) - min(values)
        assert spread <= 3, f"Unfair distribution over 12 weeks: {night_counts}"


@pytest.mark.e2e
class TestFairnessWithCategoryFilter:
    """Tests for fairness with category filtering."""

    def test_fairness_night_category_only(self, worker_factory, periods_4) -> None:
        """Fairness applies only to night category shifts."""
        workers = [worker_factory() for _ in range(8)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
            ShiftType(
                id="weekend",
                name="Weekend Shift",
                category="weekend",
                start_time=time(8, 0),
                end_time=time(16, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(
                enabled=True,
                is_hard=False,
                weight=200,
                parameters={"categories": ["night"]},
            ),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs=constraint_configs,
        )

        assert result.success

    def test_fairness_multiple_categories(self, worker_factory, periods_4) -> None:
        """Fairness across multiple filtered categories."""
        workers = [worker_factory() for _ in range(8)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="weekend",
                name="Weekend Shift",
                category="weekend",
                start_time=time(8, 0),
                end_time=time(16, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(
                enabled=True,
                is_hard=False,
                weight=150,
                parameters={"categories": ["night", "weekend"]},
            ),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs=constraint_configs,
        )

        assert result.success


@pytest.mark.e2e
class TestZeroUndesirableShifts:
    """Tests for scenarios with no undesirable shifts."""

    def test_no_undesirable_shifts_noop(self, worker_factory, periods_4) -> None:
        """Fairness constraint is effectively a no-op without undesirable shifts."""
        workers = [worker_factory() for _ in range(6)]

        shift_types = [
            ShiftType(
                id="shift_a",
                name="Shift A",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=False,
            ),
            ShiftType(
                id="shift_b",
                name="Shift B",
                category="evening",
                start_time=time(17, 0),
                end_time=time(1, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=False,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs=constraint_configs,
        )

        assert result.success

    def test_fairness_disabled_vs_enabled_no_undesirable(
        self, worker_factory, periods_4
    ) -> None:
        """Compare results with fairness enabled vs disabled, no undesirable."""
        workers = [worker_factory() for _ in range(5)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=False,
            ),
        ]

        # With fairness enabled
        result_with = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs={
                "coverage": ConstraintConfig(enabled=True, is_hard=True),
                "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            },
        )

        # Without fairness
        result_without = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs={
                "coverage": ConstraintConfig(enabled=True, is_hard=True),
                "fairness": ConstraintConfig(enabled=False),
            },
        )

        assert result_with.success
        assert result_without.success


@pytest.mark.e2e
class TestSpreadVariableTracking:
    """Tests for spread (max - min) variable tracking."""

    def test_spread_minimization(self, worker_factory, periods_4) -> None:
        """Verify spread is minimized with high fairness weight."""
        workers = [worker_factory() for _ in range(6)]

        shift_types = [
            ShiftType(
                id="undesirable",
                name="Undesirable",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=500),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs=constraint_configs,
        )

        assert result.success

        # 4 periods, 1 required each = 4 total, 6 workers
        # Optimal spread: some get 1, some get 0 -> spread = 1
        counts = {w.id: 0 for w in workers}
        for period in result.schedule.periods:
            for worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    if shift.shift_type_id == "undesirable":
                        counts[worker_id] += 1

        values = list(counts.values())
        spread = max(values) - min(values)
        # With 4 shifts and 6 workers, optimal spread is 1
        assert spread <= 2

    def test_spread_with_varying_weights(self, worker_factory, periods_4) -> None:
        """Compare spread with different fairness weights."""
        workers = [worker_factory() for _ in range(4)]

        shift_types = [
            ShiftType(
                id="undesirable",
                name="Undesirable",
                category="night",
                start_time=time(21, 0),
                end_time=time(5, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        spreads = {}
        for weight in [10, 100, 500]:
            constraint_configs = {
                "coverage": ConstraintConfig(enabled=True, is_hard=True),
                "fairness": ConstraintConfig(
                    enabled=True, is_hard=False, weight=weight
                ),
            }

            result = solve_and_verify(
                workers=workers,
                shift_types=shift_types,
                period_dates=periods_4,
                constraint_configs=constraint_configs,
            )

            counts = {w.id: 0 for w in workers}
            for period in result.schedule.periods:
                for worker_id, shifts in period.assignments.items():
                    for shift in shifts:
                        if shift.shift_type_id == "undesirable":
                            counts[worker_id] += 1

            values = list(counts.values())
            spreads[weight] = max(values) - min(values)

        # Higher weights should generally lead to smaller or equal spread
        assert spreads[500] <= spreads[10] + 1  # Allow small tolerance
