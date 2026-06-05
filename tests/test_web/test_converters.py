"""Tests for domain dataclass conversion layer (scheduler-112)."""

from datetime import date, time, timedelta

import pytest

from core.models import (
    Availability as ORMAvailability,
)
from core.models import (
    ConstraintConfig as ORMConstraintConfig,
)
from core.models import (
    ScheduleRequest as ORMScheduleRequest,
)
from core.models import (
    ShiftType as ORMShiftType,
)
from core.models import (
    SolverRun as ORMSolverRun,
)
from core.models import (
    Worker as ORMWorker,
)

pytestmark = pytest.mark.django_db


class TestWorkerConversion:
    """Tests for Worker ORM <-> domain conversion."""

    def test_orm_worker_to_domain_fields(self) -> None:
        """All worker fields are correctly mapped to domain dataclass."""
        from core.converters import orm_worker_to_domain

        orm_worker = ORMWorker.objects.create(
            worker_id="W001",
            name="Alice Smith",
            worker_type="full_time",
            restricted_shifts=["night"],
        )
        domain_worker = orm_worker_to_domain(orm_worker)
        assert domain_worker.id == "W001"
        assert domain_worker.name == "Alice Smith"
        assert domain_worker.worker_type == "full_time"
        assert domain_worker.restricted_shifts == frozenset(["night"])

    def test_domain_worker_to_orm_fields(self) -> None:
        """All worker fields are correctly mapped to ORM model."""
        from core.converters import domain_worker_to_orm
        from shift_solver.models import Worker as DomainWorker

        domain_worker = DomainWorker(
            id="W001",
            name="Alice Smith",
            worker_type="full_time",
            restricted_shifts=frozenset(["night"]),
        )
        orm_worker = domain_worker_to_orm(domain_worker)
        assert orm_worker.worker_id == "W001"
        assert orm_worker.name == "Alice Smith"
        assert orm_worker.worker_type == "full_time"
        assert set(orm_worker.restricted_shifts) == {"night"}

    def test_worker_round_trip(self) -> None:
        """ORM -> domain -> ORM preserves all fields."""
        from core.converters import domain_worker_to_orm, orm_worker_to_domain

        orm_worker = ORMWorker.objects.create(
            worker_id="W001",
            name="Alice",
            worker_type="full_time",
            restricted_shifts=["night"],
        )
        domain = orm_worker_to_domain(orm_worker)
        back = domain_worker_to_orm(domain)
        assert back.worker_id == orm_worker.worker_id
        assert back.name == orm_worker.name
        assert back.worker_type == orm_worker.worker_type


class TestShiftTypeConversion:
    """Tests for ShiftType ORM <-> domain conversion."""

    def test_orm_shift_type_to_domain_fields(self) -> None:
        """All shift type fields are correctly mapped."""
        from core.converters import orm_shift_type_to_domain

        orm_shift = ORMShiftType.objects.create(
            shift_type_id="day",
            name="Day Shift",
            category="day",
            start_time=time(7, 0),
            duration_hours=8.0,
            workers_required=2,
            is_undesirable=False,
        )
        domain_shift = orm_shift_type_to_domain(orm_shift)
        assert domain_shift.id == "day"
        assert domain_shift.name == "Day Shift"
        assert domain_shift.category == "day"
        assert domain_shift.start_time == time(7, 0)
        assert domain_shift.duration_hours == 8.0
        assert domain_shift.workers_required == 2

    def test_shift_type_round_trip(self) -> None:
        """ORM -> domain -> ORM preserves all fields."""
        from core.converters import domain_shift_type_to_orm, orm_shift_type_to_domain

        orm_shift = ORMShiftType.objects.create(
            shift_type_id="night",
            name="Night Shift",
            category="night",
            start_time=time(23, 0),
            duration_hours=8.0,
            workers_required=1,
            is_undesirable=True,
        )
        domain = orm_shift_type_to_domain(orm_shift)
        back = domain_shift_type_to_orm(domain)
        assert back.shift_type_id == orm_shift.shift_type_id
        assert back.name == orm_shift.name


class TestConstraintConversion:
    """Tests for ConstraintConfig ORM -> domain conversion."""

    def test_orm_constraint_to_domain_dict(self) -> None:
        """ConstraintConfig becomes a valid constraint configuration dict."""
        from core.converters import orm_constraint_to_domain

        orm_config = ORMConstraintConfig.objects.create(
            constraint_type="fairness",
            enabled=True,
            is_hard=False,
            weight=1000,
            parameters={"categories": ["weekend", "night"]},
        )
        domain_config = orm_constraint_to_domain(orm_config)
        assert domain_config.enabled is True
        assert domain_config.is_hard is False
        assert domain_config.weight == 1000
        assert domain_config.parameters == {"categories": ["weekend", "night"]}


class TestBuildScheduleInput:
    """Tests for building solver input from ORM data."""

    def test_build_schedule_input_includes_workers(self) -> None:
        """ScheduleInput includes all active workers."""
        from core.converters import build_schedule_input

        w1 = ORMWorker.objects.create(worker_id="W001", name="Alice", is_active=True)
        w2 = ORMWorker.objects.create(worker_id="W002", name="Bob", is_active=True)
        ORMWorker.objects.create(worker_id="W003", name="Inactive", is_active=False)
        ORMShiftType.objects.create(
            shift_type_id="day", name="Day", start_time=time(7, 0),
            duration_hours=8.0, workers_required=1,
        )
        request = ORMScheduleRequest.objects.create(
            name="Test", start_date=date(2026, 3, 2), end_date=date(2026, 3, 8),
        )
        request.workers.add(w1, w2)

        result = build_schedule_input(request)
        worker_ids = {w.id for w in result["workers"]}
        assert worker_ids == {"W001", "W002"}

    def test_build_schedule_input_includes_shift_types(self) -> None:
        """ScheduleInput includes all active shift types."""
        from core.converters import build_schedule_input

        w = ORMWorker.objects.create(worker_id="W001", name="Alice")
        s1 = ORMShiftType.objects.create(
            shift_type_id="day", name="Day", start_time=time(7, 0),
            duration_hours=8.0, workers_required=1,
        )
        ORMShiftType.objects.create(
            shift_type_id="inactive", name="Inactive", start_time=time(7, 0),
            duration_hours=8.0, is_active=False,
        )
        request = ORMScheduleRequest.objects.create(
            name="Test", start_date=date(2026, 3, 2), end_date=date(2026, 3, 8),
        )
        request.workers.add(w)
        request.shift_types.add(s1)

        result = build_schedule_input(request)
        shift_ids = {s.id for s in result["shift_types"]}
        assert "day" in shift_ids
        assert "inactive" not in shift_ids

    def test_build_schedule_input_includes_constraints(self) -> None:
        """ScheduleInput includes enabled constraints."""
        from core.converters import build_schedule_input

        w = ORMWorker.objects.create(worker_id="W001", name="Alice")
        ORMShiftType.objects.create(
            shift_type_id="day", name="Day", start_time=time(7, 0),
            duration_hours=8.0, workers_required=1,
        )
        ORMConstraintConfig.objects.create(
            constraint_type="coverage", enabled=True, is_hard=True,
        )
        ORMConstraintConfig.objects.create(
            constraint_type="disabled_one", enabled=False,
        )
        request = ORMScheduleRequest.objects.create(
            name="Test", start_date=date(2026, 3, 2), end_date=date(2026, 3, 8),
        )
        request.workers.add(w)

        result = build_schedule_input(request)
        assert "coverage" in result["constraint_configs"]
        assert "disabled_one" not in result["constraint_configs"]


class TestPeriodDates:
    """Tests for period-date tiling (end_date is inclusive, matching the engine)."""

    def test_daily_periods_include_end_date(self) -> None:
        """With daily periods, every day from start to end (inclusive) gets a period."""
        from core.converters import build_schedule_input

        w = ORMWorker.objects.create(worker_id="W001", name="Alice")
        ORMShiftType.objects.create(
            shift_type_id="day", name="Day", start_time=time(7, 0),
            duration_hours=8.0, workers_required=1,
        )
        request = ORMScheduleRequest.objects.create(
            name="Test", start_date=date(2026, 6, 1), end_date=date(2026, 6, 7),
            period_length_days=1,
        )
        request.workers.add(w)

        result = build_schedule_input(request)
        period_dates = result["period_dates"]
        # 7 inclusive days -> 7 daily periods; the final day must be present.
        assert len(period_dates) == 7
        assert period_dates[0] == (date(2026, 6, 1), date(2026, 6, 1))
        assert period_dates[-1] == (date(2026, 6, 7), date(2026, 6, 7))

    def test_weekly_periods_include_boundary_end_date(self) -> None:
        """A final day that lands exactly on a new period boundary is not dropped."""
        from core.converters import build_schedule_input

        w = ORMWorker.objects.create(worker_id="W001", name="Alice")
        ORMShiftType.objects.create(
            shift_type_id="day", name="Day", start_time=time(7, 0),
            duration_hours=8.0, workers_required=1,
        )
        # Jun 1-8 with weekly periods: a full week (1-7) plus a 1-day tail (8-8).
        request = ORMScheduleRequest.objects.create(
            name="Test", start_date=date(2026, 6, 1), end_date=date(2026, 6, 8),
            period_length_days=7,
        )
        request.workers.add(w)

        result = build_schedule_input(request)
        period_dates = result["period_dates"]
        assert period_dates == [
            (date(2026, 6, 1), date(2026, 6, 7)),
            (date(2026, 6, 8), date(2026, 6, 8)),
        ]

    def test_build_and_reconstruct_use_identical_tiling(self) -> None:
        """build_schedule_input and solver_run_to_schedule tile dates identically."""
        from core.converters import build_schedule_input, solver_run_to_schedule

        w = ORMWorker.objects.create(worker_id="W001", name="Alice")
        ORMShiftType.objects.create(
            shift_type_id="day", name="Day", start_time=time(7, 0),
            duration_hours=8.0, workers_required=1,
        )
        request = ORMScheduleRequest.objects.create(
            name="Test", start_date=date(2026, 6, 1), end_date=date(2026, 6, 10),
            period_length_days=3,
        )
        request.workers.add(w)
        run = ORMSolverRun.objects.create(schedule_request=request, status="completed")

        input_periods = build_schedule_input(request)["period_dates"]
        schedule = solver_run_to_schedule(run)
        reconstructed = [(p.period_start, p.period_end) for p in schedule.periods]
        assert input_periods == reconstructed

    @pytest.mark.parametrize(
        ("period_length", "expected_type"),
        [(1, "day"), (7, "week"), (14, "biweek"), (28, "month")],
    )
    def test_reconstructed_period_type_matches_engine(
        self, period_length: int, expected_type: str
    ) -> None:
        """solver_run_to_schedule labels period_type using the engine deriver."""
        from core.converters import solver_run_to_schedule

        ORMWorker.objects.create(worker_id="W001", name="Alice")
        ORMShiftType.objects.create(
            shift_type_id="day", name="Day", start_time=time(7, 0),
            duration_hours=8.0, workers_required=1,
        )
        # Span at least 2 days so Schedule's end_date > start_date holds; the
        # period_type is derived from the period length regardless of span.
        span_days = max(period_length, 2)
        request = ORMScheduleRequest.objects.create(
            name="Test", start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 1) + timedelta(days=span_days - 1),
            period_length_days=period_length,
        )
        run = ORMSolverRun.objects.create(
            schedule_request=request, status="completed"
        )

        schedule = solver_run_to_schedule(run)
        assert schedule.period_type == expected_type


class TestSolverResultConversion:
    """Tests for converting solver results back to ORM."""

    def test_solver_result_creates_assignments(self) -> None:
        """Schedule result is converted to Assignment ORM instances."""
        from core.converters import solver_result_to_assignments
        from shift_solver.models import PeriodAssignment, Schedule, ShiftInstance

        worker = ORMWorker.objects.create(worker_id="W001", name="Alice")
        shift = ORMShiftType.objects.create(
            shift_type_id="day", name="Day", start_time=time(7, 0),
            duration_hours=8.0,
        )
        request = ORMScheduleRequest.objects.create(
            name="Test", start_date=date(2026, 3, 2), end_date=date(2026, 3, 8),
        )
        run = ORMSolverRun.objects.create(schedule_request=request)

        schedule = Schedule(
            schedule_id="test",
            start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 8),
            period_type="week",
            periods=[
                PeriodAssignment(
                    period_index=0,
                    period_start=date(2026, 3, 2),
                    period_end=date(2026, 3, 8),
                    assignments={
                        "W001": [
                            ShiftInstance(
                                shift_type_id="day",
                                period_index=0,
                                date=date(2026, 3, 2),
                                worker_id="W001",
                            )
                        ]
                    },
                )
            ],
            workers=[],
            shift_types=[],
        )

        assignments = solver_result_to_assignments(run, schedule)
        assert len(assignments) == 1
        assert assignments[0].worker == worker
        assert assignments[0].shift_type == shift
        assert assignments[0].date == date(2026, 3, 2)

    def test_solver_result_links_to_solver_run(self) -> None:
        """All assignments reference the correct SolverRun."""
        from core.converters import solver_result_to_assignments
        from shift_solver.models import PeriodAssignment, Schedule, ShiftInstance

        ORMWorker.objects.create(worker_id="W001", name="Alice")
        ORMShiftType.objects.create(
            shift_type_id="day", name="Day", start_time=time(7, 0),
            duration_hours=8.0,
        )
        request = ORMScheduleRequest.objects.create(
            name="Test", start_date=date(2026, 3, 2), end_date=date(2026, 3, 8),
        )
        run = ORMSolverRun.objects.create(schedule_request=request)

        schedule = Schedule(
            schedule_id="test",
            start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 8),
            period_type="week",
            periods=[
                PeriodAssignment(
                    period_index=0,
                    period_start=date(2026, 3, 2),
                    period_end=date(2026, 3, 8),
                    assignments={
                        "W001": [
                            ShiftInstance(
                                shift_type_id="day", period_index=0,
                                date=date(2026, 3, 2), worker_id="W001",
                            )
                        ]
                    },
                )
            ],
            workers=[],
            shift_types=[],
        )

        assignments = solver_result_to_assignments(run, schedule)
        for assignment in assignments:
            assert assignment.solver_run == run


class TestAvailabilityConversion:
    """Tests for Availability ORM -> domain conversion."""

    def test_unavailable_maps_to_unavailable_type(self) -> None:
        """is_available=False maps to availability_type='unavailable'."""
        from core.converters import orm_availability_to_domain

        worker = ORMWorker.objects.create(worker_id="W001", name="Alice")
        avail = ORMAvailability.objects.create(
            worker=worker, date=date(2026, 3, 2), is_available=False,
        )
        result = orm_availability_to_domain(avail)
        assert result is not None
        assert result.availability_type == "unavailable"
        assert result.worker_id == "W001"
        assert result.start_date == date(2026, 3, 2)
        assert result.end_date == date(2026, 3, 2)

    def test_available_skipped(self) -> None:
        """is_available=True returns None (only unavailability is honored)."""
        from core.converters import orm_availability_to_domain

        worker = ORMWorker.objects.create(worker_id="W001", name="Alice")
        avail = ORMAvailability.objects.create(
            worker=worker, date=date(2026, 3, 2), is_available=True,
        )
        result = orm_availability_to_domain(avail)
        assert result is None

    def test_shift_type_id_forwarded(self) -> None:
        """Shift-specific availability preserves shift_type_id."""
        from core.converters import orm_availability_to_domain

        worker = ORMWorker.objects.create(worker_id="W001", name="Alice")
        shift = ORMShiftType.objects.create(
            shift_type_id="night", name="Night", start_time=time(23, 0),
            duration_hours=8.0,
        )
        avail = ORMAvailability.objects.create(
            worker=worker, date=date(2026, 3, 2), shift_type=shift,
            is_available=False,
        )
        result = orm_availability_to_domain(avail)
        assert result is not None
        assert result.shift_type_id == "night"

    def test_build_schedule_input_includes_availabilities(self) -> None:
        """build_schedule_input result dict has 'availabilities' key."""
        from core.converters import build_schedule_input

        w = ORMWorker.objects.create(worker_id="W001", name="Alice")
        ORMShiftType.objects.create(
            shift_type_id="day", name="Day", start_time=time(7, 0),
            duration_hours=8.0, workers_required=1,
        )
        request = ORMScheduleRequest.objects.create(
            name="Test", start_date=date(2026, 3, 2), end_date=date(2026, 3, 8),
        )
        request.workers.add(w)
        ORMAvailability.objects.create(
            worker=w, date=date(2026, 3, 3), is_available=False,
        )

        result = build_schedule_input(request)
        assert "availabilities" in result
        assert result["availabilities"] is not None
        assert len(result["availabilities"]) == 1
        assert result["availabilities"][0].worker_id == "W001"
        assert result["availabilities"][0].availability_type == "unavailable"

    def test_build_schedule_input_filters_by_date_range(self) -> None:
        """Only availability entries within the schedule date range are included."""
        from core.converters import build_schedule_input

        w = ORMWorker.objects.create(worker_id="W001", name="Alice")
        ORMShiftType.objects.create(
            shift_type_id="day", name="Day", start_time=time(7, 0),
            duration_hours=8.0, workers_required=1,
        )
        request = ORMScheduleRequest.objects.create(
            name="Test", start_date=date(2026, 3, 2), end_date=date(2026, 3, 8),
        )
        request.workers.add(w)
        # Within range
        ORMAvailability.objects.create(
            worker=w, date=date(2026, 3, 3), is_available=False,
        )
        # Outside range
        ORMAvailability.objects.create(
            worker=w, date=date(2026, 4, 1), is_available=False,
        )

        result = build_schedule_input(request)
        assert result["availabilities"] is not None
        assert len(result["availabilities"]) == 1
