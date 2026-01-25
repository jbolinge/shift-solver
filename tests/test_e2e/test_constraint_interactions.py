"""E2E tests for multi-constraint interactions.

scheduler-46: Tests interactions between constraints including weight competition,
tension between hard and soft constraints, and simultaneous constraint activation.
"""

from datetime import date, time, timedelta

import pytest

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import Availability, SchedulingRequest, ShiftType, Worker
from shift_solver.solver import ShiftSolver

from .conftest import create_period_dates, solve_and_verify


@pytest.mark.e2e
class TestFairnessVsRequestConflicts:
    """Tests for fairness vs request constraint competition."""

    def test_fairness_vs_request_weight_competition(
        self, worker_factory, periods_4
    ) -> None:
        """Fairness and request constraints compete via weights."""
        workers = [worker_factory() for _ in range(6)]
        period_start, period_end = periods_4[0]

        shift_types = [
            ShiftType(
                id="undesirable",
                name="Undesirable",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        # Worker 0 has high priority request to avoid undesirable
        requests = [
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="undesirable",
                priority=5,
            ),
        ]

        # High fairness weight vs high request weight
        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=200),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=200),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        assert result.success

    def test_high_fairness_overrides_low_request(
        self, worker_factory, periods_4
    ) -> None:
        """High fairness weight should dominate low request weight."""
        workers = [worker_factory() for _ in range(4)]
        period_start, period_end = periods_4[0]

        shift_types = [
            ShiftType(
                id="undesirable",
                name="Undesirable",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        # All workers request to avoid undesirable
        requests = [
            SchedulingRequest(
                worker_id=w.id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="undesirable",
                priority=1,  # Low priority
            )
            for w in workers
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=500),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=10),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        assert result.success


@pytest.mark.e2e
class TestCoverageVsAvailabilityTension:
    """Tests for coverage vs availability constraint tension."""

    def test_coverage_hard_availability_hard(
        self, worker_factory, periods_4
    ) -> None:
        """Both coverage and availability as hard constraints."""
        workers = [worker_factory() for _ in range(6)]
        period_start, period_end = periods_4[0]

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

        # 2 workers unavailable, still feasible with 4 remaining
        availabilities = [
            Availability(
                worker_id=workers[i].id,
                start_date=period_start,
                end_date=period_end,
                availability_type="unavailable",
            )
            for i in range(2)
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "availability": ConstraintConfig(enabled=True, is_hard=True),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            availabilities=availabilities,
            constraint_configs=constraint_configs,
        )

        assert result.success
        # Verify unavailable workers not assigned
        period_0 = result.schedule.periods[0]
        for i in range(2):
            assert (
                workers[i].id not in period_0.assignments
                or not period_0.assignments[workers[i].id]
            )

    def test_coverage_vs_availability_infeasible(
        self, worker_factory, periods_4
    ) -> None:
        """Coverage cannot be met due to availability constraints."""
        workers = [worker_factory() for _ in range(3)]
        period_start, period_end = periods_4[0]

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

        # All but 1 worker unavailable - can't meet coverage of 2
        availabilities = [
            Availability(
                worker_id=workers[i].id,
                start_date=period_start,
                end_date=period_end,
                availability_type="unavailable",
            )
            for i in range(2)
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "availability": ConstraintConfig(enabled=True, is_hard=True),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            availabilities=availabilities,
            constraint_configs=constraint_configs,
            expect_feasible=False,
        )

        assert not result.success


@pytest.mark.e2e
class TestFrequencyConstraintInteractions:
    """Tests for frequency constraint interactions."""

    def test_frequency_vs_fairness(self, worker_factory, periods_4) -> None:
        """Frequency and fairness constraints together."""
        workers = [worker_factory() for _ in range(8)]

        shift_types = [
            ShiftType(
                id="regular",
                name="Regular",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
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
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "frequency": ConstraintConfig(enabled=True, is_hard=False, weight=50),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            constraint_configs=constraint_configs,
        )

        assert result.success

    def test_frequency_limits_with_high_coverage(self, worker_factory) -> None:
        """Frequency limits when coverage requirements are high."""
        workers = [worker_factory() for _ in range(10)]

        shift_types = [
            ShiftType(
                id="shift",
                name="Shift",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=3,  # High coverage
            ),
        ]

        periods = create_period_dates(num_periods=4)

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "frequency": ConstraintConfig(
                enabled=True,
                is_hard=False,
                weight=100,
                parameters={"max_shifts_per_period": 1},
            ),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            constraint_configs=constraint_configs,
        )

        assert result.success


@pytest.mark.e2e
class TestSequenceVsFairness:
    """Tests for sequence vs fairness constraint interactions."""

    def test_sequence_and_fairness_together(self, worker_factory, periods_4) -> None:
        """Sequence constraint combined with fairness."""
        workers = [worker_factory() for _ in range(8)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "sequence": ConstraintConfig(
                enabled=True,
                is_hard=False,
                weight=50,
                parameters={"min_gap_periods": 1},
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
class TestAllSoftConstraintsSimultaneous:
    """Tests for all soft constraints enabled simultaneously."""

    @pytest.mark.slow
    def test_all_constraints_20_workers_5_shifts_12_periods(
        self, worker_factory
    ) -> None:
        """All 5 soft constraints enabled: 20 workers, 5 shifts, 12 periods."""
        workers = [worker_factory() for _ in range(20)]
        periods = create_period_dates(num_periods=12)

        shift_types = [
            ShiftType(
                id="morning",
                name="Morning",
                category="day",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="afternoon",
                name="Afternoon",
                category="day",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="night",
                name="Night",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
            ShiftType(
                id="weekend_day",
                name="Weekend Day",
                category="weekend",
                start_time=time(8, 0),
                end_time=time(16, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
            ShiftType(
                id="weekend_night",
                name="Weekend Night",
                category="weekend",
                start_time=time(16, 0),
                end_time=time(0, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]

        # Add some requests
        requests = [
            SchedulingRequest(
                worker_id=workers[i].id,
                start_date=periods[i % len(periods)][0],
                end_date=periods[i % len(periods)][1],
                request_type="negative",
                shift_type_id="night",
                priority=2,
            )
            for i in range(5)
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "availability": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "frequency": ConstraintConfig(enabled=True, is_hard=False, weight=50),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=75),
            "sequence": ConstraintConfig(enabled=True, is_hard=False, weight=30),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods,
            requests=requests,
            constraint_configs=constraint_configs,
            time_limit_seconds=180,
        )

        assert result.success
        assert len(result.schedule.periods) == 12
        assert len(result.schedule.workers) == 20

    def test_all_constraints_moderate_scenario(self, worker_factory, periods_4) -> None:
        """All constraints with moderate problem size."""
        workers = [worker_factory() for _ in range(10)]

        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
                workers_required=2,
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

        period_start, period_end = periods_4[0]
        requests = [
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="night",
                priority=2,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "restriction": ConstraintConfig(enabled=True, is_hard=True),
            "availability": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
            "frequency": ConstraintConfig(enabled=True, is_hard=False, weight=50),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=75),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        assert result.success


@pytest.mark.e2e
class TestWeightSensitivityAnalysis:
    """Tests for weight sensitivity analysis."""

    def test_same_scenario_different_weights(self, worker_factory, periods_4) -> None:
        """Same scenario with varying constraint weights."""
        workers = [worker_factory() for _ in range(6)]
        period_start, period_end = periods_4[0]

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

        # All workers request off
        requests = [
            SchedulingRequest(
                worker_id=w.id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="undesirable",
                priority=2,
            )
            for w in workers
        ]

        weight_configs = [
            {"fairness": 500, "request": 50},   # Fairness dominant
            {"fairness": 50, "request": 500},   # Request dominant
            {"fairness": 100, "request": 100},  # Equal weights
        ]

        objectives = []
        for config in weight_configs:
            constraint_configs = {
                "coverage": ConstraintConfig(enabled=True, is_hard=True),
                "fairness": ConstraintConfig(
                    enabled=True, is_hard=False, weight=config["fairness"]
                ),
                "request": ConstraintConfig(
                    enabled=True, is_hard=False, weight=config["request"]
                ),
            }

            result = solve_and_verify(
                workers=workers,
                shift_types=shift_types,
                period_dates=periods_4,
                requests=requests,
                constraint_configs=constraint_configs,
            )

            assert result.success
            objectives.append(result.objective_value)

        # All should solve successfully (objective values may differ)
        assert len(objectives) == 3

    @pytest.mark.parametrize(
        "fairness_weight,request_weight",
        [
            (10, 100),
            (50, 100),
            (100, 100),
            (100, 50),
            (100, 10),
        ],
    )
    def test_parametrized_weight_combinations(
        self, worker_factory, periods_4, fairness_weight, request_weight
    ) -> None:
        """Parametrized test for various weight combinations."""
        workers = [worker_factory() for _ in range(6)]
        period_start, period_end = periods_4[0]

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

        requests = [
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="undesirable",
                priority=3,
            ),
        ]

        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(
                enabled=True, is_hard=False, weight=fairness_weight
            ),
            "request": ConstraintConfig(
                enabled=True, is_hard=False, weight=request_weight
            ),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        assert result.success

    def test_extreme_weight_ratios(self, worker_factory, periods_4) -> None:
        """Test with extreme weight ratios (1000:1)."""
        workers = [worker_factory() for _ in range(6)]
        period_start, period_end = periods_4[0]

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

        requests = [
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=period_start,
                end_date=period_end,
                request_type="negative",
                shift_type_id="undesirable",
                priority=1,
            ),
        ]

        # Extreme fairness dominance
        constraint_configs = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=1000),
            "request": ConstraintConfig(enabled=True, is_hard=False, weight=1),
        }

        result = solve_and_verify(
            workers=workers,
            shift_types=shift_types,
            period_dates=periods_4,
            requests=requests,
            constraint_configs=constraint_configs,
        )

        assert result.success
