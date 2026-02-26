"""Tests for Django ORM models (scheduler-111)."""

from datetime import date, time

import pytest

from core.models import (
    Assignment,
    Availability,
    ConstraintConfig,
    ScheduleRequest,
    ShiftType,
    SolverRun,
    Worker,
)

pytestmark = pytest.mark.django_db


class TestWorkerModel:
    """Tests for the Worker model."""

    def test_create_worker(self) -> None:
        """Can create a Worker with required fields."""
        worker = Worker.objects.create(
            worker_id="W001",
            name="Alice Smith",
        )
        assert worker.pk is not None
        assert worker.worker_id == "W001"
        assert worker.name == "Alice Smith"

    def test_worker_str_representation(self) -> None:
        """Worker __str__ returns name."""
        worker = Worker.objects.create(worker_id="W001", name="Alice Smith")
        assert str(worker) == "Alice Smith"

    def test_worker_unique_worker_id(self) -> None:
        """worker_id must be unique."""
        Worker.objects.create(worker_id="W001", name="Alice")
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            Worker.objects.create(worker_id="W001", name="Bob")

    def test_worker_defaults(self) -> None:
        """Worker has correct default values."""
        worker = Worker.objects.create(worker_id="W001", name="Alice")
        assert worker.fte == 1.0
        assert worker.is_active is True
        assert worker.email == ""
        assert worker.group == ""


class TestShiftTypeModel:
    """Tests for the ShiftType model."""

    def test_create_shift_type(self) -> None:
        """Can create a ShiftType with required fields."""
        shift = ShiftType.objects.create(
            shift_type_id="day",
            name="Day Shift",
            start_time=time(7, 0),
            duration_hours=8.0,
        )
        assert shift.pk is not None
        assert shift.shift_type_id == "day"

    def test_shift_type_str_representation(self) -> None:
        """ShiftType __str__ returns name."""
        shift = ShiftType.objects.create(
            shift_type_id="day",
            name="Day Shift",
            start_time=time(7, 0),
            duration_hours=8.0,
        )
        assert str(shift) == "Day Shift"

    def test_shift_type_optional_max_workers(self) -> None:
        """max_workers can be null."""
        shift = ShiftType.objects.create(
            shift_type_id="day",
            name="Day Shift",
            start_time=time(7, 0),
            duration_hours=8.0,
            max_workers=None,
        )
        assert shift.max_workers is None


class TestAvailabilityModel:
    """Tests for the Availability model."""

    def test_create_availability(self) -> None:
        """Can create an Availability entry."""
        worker = Worker.objects.create(worker_id="W001", name="Alice")
        avail = Availability.objects.create(
            worker=worker,
            date=date(2026, 3, 1),
            is_available=True,
        )
        assert avail.pk is not None
        assert avail.worker == worker

    def test_availability_worker_cascade_delete(self) -> None:
        """Deleting a worker deletes their availabilities."""
        worker = Worker.objects.create(worker_id="W001", name="Alice")
        Availability.objects.create(
            worker=worker,
            date=date(2026, 3, 1),
            is_available=True,
        )
        assert Availability.objects.count() == 1
        worker.delete()
        assert Availability.objects.count() == 0


class TestConstraintConfigModel:
    """Tests for the ConstraintConfig model."""

    def test_create_constraint_config(self) -> None:
        """Can create a ConstraintConfig entry."""
        config = ConstraintConfig.objects.create(
            constraint_type="coverage",
            enabled=True,
            is_hard=True,
        )
        assert config.pk is not None
        assert config.constraint_type == "coverage"

    def test_constraint_config_str(self) -> None:
        """ConstraintConfig __str__ returns type name."""
        config = ConstraintConfig.objects.create(
            constraint_type="fairness",
        )
        assert str(config) == "fairness"


class TestScheduleRequestModel:
    """Tests for the ScheduleRequest model."""

    def test_create_schedule_request(self) -> None:
        """Can create a ScheduleRequest with date range."""
        request = ScheduleRequest.objects.create(
            name="March Schedule",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        assert request.pk is not None
        assert request.name == "March Schedule"

    def test_schedule_request_default_status(self) -> None:
        """Default status is 'draft'."""
        request = ScheduleRequest.objects.create(
            name="Test",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        assert request.status == "draft"

    def test_schedule_request_str(self) -> None:
        """ScheduleRequest __str__ returns name."""
        request = ScheduleRequest.objects.create(
            name="March Schedule",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        assert str(request) == "March Schedule"


class TestSolverRunModel:
    """Tests for the SolverRun model."""

    def test_create_solver_run(self) -> None:
        """Can create a SolverRun linked to a ScheduleRequest."""
        request = ScheduleRequest.objects.create(
            name="Test",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        run = SolverRun.objects.create(schedule_request=request)
        assert run.pk is not None
        assert run.schedule_request == request

    def test_solver_run_progress_default(self) -> None:
        """Default progress_percent is 0."""
        request = ScheduleRequest.objects.create(
            name="Test",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        run = SolverRun.objects.create(schedule_request=request)
        assert run.progress_percent == 0
        assert run.status == "pending"


class TestAssignmentModel:
    """Tests for the Assignment model."""

    def test_create_assignment(self) -> None:
        """Can create an Assignment linking worker, shift, and date."""
        worker = Worker.objects.create(worker_id="W001", name="Alice")
        shift = ShiftType.objects.create(
            shift_type_id="day",
            name="Day Shift",
            start_time=time(7, 0),
            duration_hours=8.0,
        )
        request = ScheduleRequest.objects.create(
            name="Test",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        run = SolverRun.objects.create(schedule_request=request)
        assignment = Assignment.objects.create(
            solver_run=run,
            worker=worker,
            shift_type=shift,
            date=date(2026, 3, 1),
        )
        assert assignment.pk is not None
        assert assignment.worker == worker
        assert assignment.shift_type == shift
        assert assignment.date == date(2026, 3, 1)
