"""Tests for database schema and models."""

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from shift_solver.db.schema import (
    Base,
    DBAssignment,
    DBAvailability,
    DBRequest,
    DBSchedule,
    DBShiftType,
    DBWorker,
)


@pytest.fixture
def engine():
    """Create an in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a database session."""
    with Session(engine) as session:
        yield session


class TestDBWorker:
    """Tests for DBWorker model."""

    def test_create_worker(self, session: Session) -> None:
        """Create a worker in the database."""
        worker = DBWorker(
            id="W001",
            name="John Doe",
            worker_type="full_time",
        )
        session.add(worker)
        session.commit()

        result = session.get(DBWorker, "W001")
        assert result is not None
        assert result.name == "John Doe"
        assert result.worker_type == "full_time"

    def test_worker_with_restrictions(self, session: Session) -> None:
        """Create a worker with shift restrictions."""
        worker = DBWorker(
            id="W002",
            name="Jane Smith",
            restricted_shifts=["night_shift", "weekend"],
            preferred_shifts=["day_shift"],
        )
        session.add(worker)
        session.commit()

        result = session.get(DBWorker, "W002")
        assert "night_shift" in result.restricted_shifts
        assert "day_shift" in result.preferred_shifts

    def test_worker_with_attributes(self, session: Session) -> None:
        """Create a worker with custom attributes."""
        worker = DBWorker(
            id="W003",
            name="Bob Wilson",
            attributes={"department": "Sales", "seniority": 5},
        )
        session.add(worker)
        session.commit()

        result = session.get(DBWorker, "W003")
        assert result.attributes["department"] == "Sales"
        assert result.attributes["seniority"] == 5


class TestDBShiftType:
    """Tests for DBShiftType model."""

    def test_create_shift_type(self, session: Session) -> None:
        """Create a shift type in the database."""
        shift_type = DBShiftType(
            id="day_shift",
            name="Day Shift",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=2,
        )
        session.add(shift_type)
        session.commit()

        result = session.get(DBShiftType, "day_shift")
        assert result is not None
        assert result.name == "Day Shift"
        assert result.start_time == time(7, 0)
        assert result.workers_required == 2

    def test_undesirable_shift_type(self, session: Session) -> None:
        """Create an undesirable shift type."""
        shift_type = DBShiftType(
            id="night_shift",
            name="Night Shift",
            category="night",
            start_time=time(23, 0),
            end_time=time(7, 0),
            duration_hours=8.0,
            is_undesirable=True,
        )
        session.add(shift_type)
        session.commit()

        result = session.get(DBShiftType, "night_shift")
        assert result.is_undesirable is True


class TestDBSchedule:
    """Tests for DBSchedule model."""

    def test_create_schedule(self, session: Session) -> None:
        """Create a schedule in the database."""
        schedule = DBSchedule(
            id="SCH-001",
            name="Q1 2026 Schedule",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            period_type="week",
            status="draft",
        )
        session.add(schedule)
        session.commit()

        result = session.get(DBSchedule, "SCH-001")
        assert result is not None
        assert result.name == "Q1 2026 Schedule"
        assert result.status == "draft"


class TestDBAssignment:
    """Tests for DBAssignment model."""

    def test_create_assignment(self, session: Session) -> None:
        """Create an assignment with relationships."""
        # Create required entities
        worker = DBWorker(id="W001", name="Test Worker")
        shift_type = DBShiftType(
            id="day_shift",
            name="Day",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
        )
        schedule = DBSchedule(
            id="SCH-001",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            period_type="week",
        )
        session.add_all([worker, shift_type, schedule])
        session.commit()

        # Create assignment
        assignment = DBAssignment(
            schedule_id="SCH-001",
            worker_id="W001",
            shift_type_id="day_shift",
            period_index=0,
            date=date(2026, 1, 5),
        )
        session.add(assignment)
        session.commit()

        result = session.query(DBAssignment).first()
        assert result is not None
        assert result.worker_id == "W001"
        assert result.shift_type_id == "day_shift"

    def test_assignment_relationships(self, session: Session) -> None:
        """Test that assignment relationships work."""
        worker = DBWorker(id="W001", name="Test Worker")
        shift_type = DBShiftType(
            id="day_shift",
            name="Day",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
        )
        schedule = DBSchedule(
            id="SCH-001",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            period_type="week",
        )
        session.add_all([worker, shift_type, schedule])
        session.commit()

        assignment = DBAssignment(
            schedule_id="SCH-001",
            worker_id="W001",
            shift_type_id="day_shift",
            period_index=0,
            date=date(2026, 1, 5),
        )
        session.add(assignment)
        session.commit()

        # Access relationships
        result = session.query(DBAssignment).first()
        assert result.worker.name == "Test Worker"
        assert result.shift_type.name == "Day"
        assert result.schedule.start_date == date(2026, 1, 1)


class TestDBAvailability:
    """Tests for DBAvailability model."""

    def test_create_availability(self, session: Session) -> None:
        """Create an availability record."""
        worker = DBWorker(id="W001", name="Test Worker")
        session.add(worker)
        session.commit()

        availability = DBAvailability(
            worker_id="W001",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 14),
            availability_type="unavailable",
        )
        session.add(availability)
        session.commit()

        result = session.query(DBAvailability).first()
        assert result is not None
        assert result.availability_type == "unavailable"


class TestDBRequest:
    """Tests for DBRequest model."""

    def test_create_request(self, session: Session) -> None:
        """Create a scheduling request."""
        worker = DBWorker(id="W001", name="Test Worker")
        shift_type = DBShiftType(
            id="day_shift",
            name="Day",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
        )
        session.add_all([worker, shift_type])
        session.commit()

        request = DBRequest(
            worker_id="W001",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 7),
            request_type="positive",
            shift_type_id="day_shift",
            priority=2,
        )
        session.add(request)
        session.commit()

        result = session.query(DBRequest).first()
        assert result is not None
        assert result.request_type == "positive"
        assert result.priority == 2


class TestDatabaseInitialization:
    """Tests for database initialization."""

    def test_create_all_tables(self) -> None:
        """Verify all tables are created."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        # Check that all expected tables exist
        table_names = Base.metadata.tables.keys()
        assert "workers" in table_names
        assert "shift_types" in table_names
        assert "schedules" in table_names
        assert "assignments" in table_names
        assert "availabilities" in table_names
        assert "requests" in table_names
