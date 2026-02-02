"""Tests for objective function scaling with large request volumes.

These tests verify that the objective function remains balanced when
handling many requests, and that fairness constraints aren't overwhelmed.

Issue: scheduler-80
"""

from datetime import date, time, timedelta

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.constraints.fairness import FairnessConstraint
from shift_solver.constraints.request import RequestConstraint
from shift_solver.models import SchedulingRequest, ShiftType, Worker
from shift_solver.solver.objective_builder import ObjectiveBuilder
from shift_solver.solver.variable_builder import VariableBuilder


def create_workers(count: int) -> list[Worker]:
    """Create a list of workers."""
    return [Worker(id=f"W{i:03d}", name=f"Worker {i}") for i in range(1, count + 1)]


def create_shift_types() -> list[ShiftType]:
    """Create standard shift types."""
    return [
        ShiftType(
            id="day",
            name="Day Shift",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=2,
        ),
        ShiftType(
            id="night",
            name="Night Shift",
            category="night",
            start_time=time(23, 0),
            end_time=time(7, 0),
            duration_hours=8.0,
            workers_required=1,
            is_undesirable=True,
        ),
    ]


def create_period_dates(num_periods: int) -> list[tuple[date, date]]:
    """Create weekly period dates."""
    periods = []
    current = date(2026, 1, 5)  # Start on a Monday
    for _ in range(num_periods):
        end = current + timedelta(days=6)
        periods.append((current, end))
        current = end + timedelta(days=1)
    return periods


def create_requests(
    workers: list[Worker],
    shift_types: list[ShiftType],
    period_dates: list[tuple[date, date]],
    requests_per_worker: int = 1,
    request_type: str = "positive",
    priority: int = 1,
) -> list[SchedulingRequest]:
    """Create scheduling requests for testing."""
    requests = []
    shift_id = shift_types[0].id  # Use first shift type

    for worker in workers:
        for i in range(min(requests_per_worker, len(period_dates))):
            period_start, period_end = period_dates[i % len(period_dates)]
            requests.append(
                SchedulingRequest(
                    worker_id=worker.id,
                    start_date=period_start,
                    end_date=period_end,
                    request_type=request_type,
                    shift_type_id=shift_id,
                    priority=priority,
                )
            )
    return requests


class TestObjectiveWeightAnalysis:
    """Tests for analyzing objective weight distribution."""

    def test_small_request_volume_balanced(self) -> None:
        """With few requests, objective weights should be reasonably balanced."""
        workers = create_workers(5)
        shift_types = create_shift_types()
        num_periods = 4
        period_dates = create_period_dates(num_periods)

        # Create 10 requests (2 per worker)
        requests = create_requests(workers, shift_types, period_dates, requests_per_worker=2)

        model = cp_model.CpModel()
        var_builder = VariableBuilder(model, workers, shift_types, num_periods)
        variables = var_builder.build()

        # Create constraints
        fairness_config = ConstraintConfig(enabled=True, is_hard=False, weight=1000)
        fairness = FairnessConstraint(model, variables, fairness_config)
        fairness.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        request_config = ConstraintConfig(enabled=True, is_hard=False, weight=150)
        request_constraint = RequestConstraint(model, variables, request_config)
        request_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            requests=requests,
            period_dates=period_dates,
        )

        # Build objective
        obj_builder = ObjectiveBuilder(model)
        obj_builder.add_constraint(fairness)
        obj_builder.add_constraint(request_constraint)
        obj_builder.build()

        # Analyze weights
        weight_totals = obj_builder.get_total_weight_by_constraint()

        # With 10 requests × 150 weight = 1500 max request penalty
        # Fairness spread weight = 1000 per unit of spread
        assert "fairness" in weight_totals
        assert "request" in weight_totals

        # Request weight should be reasonable compared to fairness
        # 10 requests × 150 = 1500 max potential penalty
        assert weight_totals["request"] == 10 * 150  # 1500

    def test_medium_request_volume_weight_distribution(self) -> None:
        """With 100 requests, document the weight distribution."""
        workers = create_workers(10)
        shift_types = create_shift_types()
        num_periods = 10
        period_dates = create_period_dates(num_periods)

        # Create 100 requests (10 per worker)
        requests = create_requests(workers, shift_types, period_dates, requests_per_worker=10)
        assert len(requests) == 100

        model = cp_model.CpModel()
        var_builder = VariableBuilder(model, workers, shift_types, num_periods)
        variables = var_builder.build()

        # Create constraints
        fairness = FairnessConstraint(
            model, variables, ConstraintConfig(enabled=True, is_hard=False, weight=1000)
        )
        fairness.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        request_constraint = RequestConstraint(
            model, variables, ConstraintConfig(enabled=True, is_hard=False, weight=150)
        )
        request_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            requests=requests,
            period_dates=period_dates,
        )

        obj_builder = ObjectiveBuilder(model)
        obj_builder.add_constraint(fairness)
        obj_builder.add_constraint(request_constraint)
        obj_builder.build()

        weight_totals = obj_builder.get_total_weight_by_constraint()

        # 100 requests × 150 = 15,000 max potential request penalty
        assert weight_totals["request"] == 100 * 150

        # Document the imbalance: requests can dominate fairness
        # This is expected behavior - if you have many requests,
        # honoring them becomes more important than perfect fairness
        fairness_weight = weight_totals["fairness"]
        request_weight = weight_totals["request"]

        # Fairness has weight 1000 per spread unit
        # If max spread is 10 (num_periods), max penalty = 10,000
        # But request penalty can reach 15,000
        assert request_weight > fairness_weight

    def test_priority_multiplier_effect(self) -> None:
        """Higher priority requests have higher effective weights."""
        workers = create_workers(5)
        shift_types = create_shift_types()
        num_periods = 4
        period_dates = create_period_dates(num_periods)

        # Create requests with different priorities
        low_priority_requests = create_requests(
            workers[:2], shift_types, period_dates, priority=1
        )
        high_priority_requests = create_requests(
            workers[2:], shift_types, period_dates, priority=3
        )
        all_requests = low_priority_requests + high_priority_requests

        model = cp_model.CpModel()
        var_builder = VariableBuilder(model, workers, shift_types, num_periods)
        variables = var_builder.build()

        request_constraint = RequestConstraint(
            model, variables, ConstraintConfig(enabled=True, is_hard=False, weight=150)
        )
        request_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            requests=all_requests,
            period_dates=period_dates,
        )

        obj_builder = ObjectiveBuilder(model)
        obj_builder.add_constraint(request_constraint)
        obj_builder.build()

        # Analyze individual terms
        breakdown = obj_builder.get_objective_breakdown()
        request_terms = breakdown.get("request", [])

        # Check that high priority requests have higher effective weight
        low_prio_weights = [t.effective_weight for t in request_terms if t.priority_multiplier == 1]
        high_prio_weights = [t.effective_weight for t in request_terms if t.priority_multiplier == 3]

        if low_prio_weights and high_prio_weights:
            assert all(w == 150 for w in low_prio_weights)  # base weight × 1
            assert all(w == 450 for w in high_prio_weights)  # base weight × 3


class TestObjectiveScalingSolver:
    """Tests that verify solver behavior with scaled objectives."""

    def test_solver_handles_many_requests(self) -> None:
        """Solver should find solution even with many requests."""
        workers = create_workers(10)
        shift_types = create_shift_types()
        num_periods = 8
        period_dates = create_period_dates(num_periods)

        # Create 80 requests
        requests = create_requests(workers, shift_types, period_dates, requests_per_worker=8)

        model = cp_model.CpModel()
        var_builder = VariableBuilder(model, workers, shift_types, num_periods)
        variables = var_builder.build()

        # Add coverage constraints
        for period in range(num_periods):
            for shift_type in shift_types:
                shift_vars = [
                    variables.get_assignment_var(w.id, period, shift_type.id)
                    for w in workers
                ]
                model.add(sum(shift_vars) == shift_type.workers_required)

        # Add soft constraints
        fairness = FairnessConstraint(
            model, variables, ConstraintConfig(enabled=True, is_hard=False, weight=1000)
        )
        fairness.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        request_constraint = RequestConstraint(
            model, variables, ConstraintConfig(enabled=True, is_hard=False, weight=150)
        )
        request_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            requests=requests,
            period_dates=period_dates,
        )

        obj_builder = ObjectiveBuilder(model)
        obj_builder.add_constraint(fairness)
        obj_builder.add_constraint(request_constraint)
        obj_builder.build()

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_request_vs_fairness_tradeoff(self) -> None:
        """Document the tradeoff between requests and fairness."""
        workers = create_workers(5)
        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]
        num_periods = 4
        period_dates = create_period_dates(num_periods)

        # Create conflicting scenario:
        # Worker 0 requests to work ALL night shifts (unfair to others)
        # Fairness wants to distribute night shifts evenly
        requests = []
        for period_start, period_end in period_dates:
            requests.append(
                SchedulingRequest(
                    worker_id=workers[0].id,
                    start_date=period_start,
                    end_date=period_end,
                    request_type="positive",
                    shift_type_id="night",
                    priority=1,
                )
            )

        model = cp_model.CpModel()
        var_builder = VariableBuilder(model, workers, shift_types, num_periods)
        variables = var_builder.build()

        # Add coverage
        for period in range(num_periods):
            shift_vars = [
                variables.get_assignment_var(w.id, period, "night") for w in workers
            ]
            model.add(sum(shift_vars) == 1)

        # High fairness weight vs lower request weight
        fairness = FairnessConstraint(
            model, variables, ConstraintConfig(enabled=True, is_hard=False, weight=1000)
        )
        fairness.apply(workers=workers, shift_types=shift_types, num_periods=num_periods)

        request_constraint = RequestConstraint(
            model, variables, ConstraintConfig(enabled=True, is_hard=False, weight=150)
        )
        request_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            requests=requests,
            period_dates=period_dates,
        )

        obj_builder = ObjectiveBuilder(model)
        obj_builder.add_constraint(fairness)
        obj_builder.add_constraint(request_constraint)
        obj_builder.build()

        solver = cp_model.CpSolver()
        status = solver.solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # Check how many shifts Worker 0 got
        worker0_shifts = sum(
            solver.value(variables.get_assignment_var(workers[0].id, p, "night"))
            for p in range(num_periods)
        )

        # With fairness weight 1000 vs request weight 150 × 4 = 600,
        # fairness should dominate and prevent Worker 0 from getting all shifts
        # (unless the math works out differently based on spread)
        # This documents the expected behavior

        # The solver should balance: giving all 4 to Worker 0 would have
        # fairness penalty = 4 × 1000 = 4000 (spread of 4)
        # vs request penalty = 0 (all requests satisfied)
        # vs distributing evenly: fairness = 0 but request penalty = 3 × 150 = 450
        # So fairness should win and distribute more evenly
        assert worker0_shifts < num_periods  # Should not get all shifts


class TestObjectiveTermCounting:
    """Tests for counting objective terms correctly."""

    def test_term_count_matches_requests(self) -> None:
        """Each request should create one violation variable per applicable period."""
        workers = create_workers(3)
        shift_types = create_shift_types()
        num_periods = 4
        period_dates = create_period_dates(num_periods)

        # Create 3 requests, each for a single period
        requests = [
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="positive",
                shift_type_id=shift_types[0].id,
                priority=1,
            ),
            SchedulingRequest(
                worker_id=workers[1].id,
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                request_type="positive",
                shift_type_id=shift_types[0].id,
                priority=2,
            ),
            SchedulingRequest(
                worker_id=workers[2].id,
                start_date=period_dates[2][0],
                end_date=period_dates[2][1],
                request_type="negative",
                shift_type_id=shift_types[0].id,
                priority=1,
            ),
        ]

        model = cp_model.CpModel()
        var_builder = VariableBuilder(model, workers, shift_types, num_periods)
        variables = var_builder.build()

        request_constraint = RequestConstraint(
            model, variables, ConstraintConfig(enabled=True, is_hard=False, weight=100)
        )
        request_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            requests=requests,
            period_dates=period_dates,
        )

        obj_builder = ObjectiveBuilder(model)
        obj_builder.add_constraint(request_constraint)
        obj_builder.build()

        # Should have 3 objective terms (one per request)
        assert len(obj_builder.objective_terms) == 3

    def test_multi_period_request_creates_multiple_terms(self) -> None:
        """A request spanning multiple periods creates multiple violation variables."""
        workers = create_workers(2)
        shift_types = create_shift_types()
        num_periods = 4
        period_dates = create_period_dates(num_periods)

        # Create request spanning all periods
        requests = [
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=period_dates[0][0],
                end_date=period_dates[-1][1],  # Spans all periods
                request_type="positive",
                shift_type_id=shift_types[0].id,
                priority=1,
            ),
        ]

        model = cp_model.CpModel()
        var_builder = VariableBuilder(model, workers, shift_types, num_periods)
        variables = var_builder.build()

        request_constraint = RequestConstraint(
            model, variables, ConstraintConfig(enabled=True, is_hard=False, weight=100)
        )
        request_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            requests=requests,
            period_dates=period_dates,
        )

        obj_builder = ObjectiveBuilder(model)
        obj_builder.add_constraint(request_constraint)
        obj_builder.build()

        # Should have 4 objective terms (one per period the request covers)
        assert len(obj_builder.objective_terms) == num_periods


class TestLargeScaleObjective:
    """Tests with larger numbers of requests."""

    @pytest.mark.slow
    def test_large_request_volume(self) -> None:
        """Test with 500+ requests to verify no performance issues."""
        workers = create_workers(20)
        shift_types = create_shift_types()
        num_periods = 26  # Half a year of weeks
        period_dates = create_period_dates(num_periods)

        # Create ~500 requests
        requests = create_requests(workers, shift_types, period_dates, requests_per_worker=26)
        assert len(requests) >= 500

        model = cp_model.CpModel()
        var_builder = VariableBuilder(model, workers, shift_types, num_periods)
        variables = var_builder.build()

        request_constraint = RequestConstraint(
            model, variables, ConstraintConfig(enabled=True, is_hard=False, weight=150)
        )
        request_constraint.apply(
            workers=workers,
            shift_types=shift_types,
            num_periods=num_periods,
            requests=requests,
            period_dates=period_dates,
        )

        obj_builder = ObjectiveBuilder(model)
        obj_builder.add_constraint(request_constraint)
        obj_builder.build()

        # Should create terms without error
        assert len(obj_builder.objective_terms) >= 500

        # Document total weight
        weight_totals = obj_builder.get_total_weight_by_constraint()
        # 520 requests × 150 = 78,000 max potential penalty
        assert weight_totals["request"] >= 500 * 150
