"""Integration tests for database persistence cycle.

Tests the complete workflow: init DB -> load workers/shifts -> solve -> persist -> reload
"""

from datetime import date, time, timedelta

import pytest
from ortools.sat.python import cp_model
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from shift_solver.constraints import CoverageConstraint
from shift_solver.db.schema import (
    Base,
    DBAssignment,
    DBSchedule,
    DBShiftType,
    DBWorker,
)
from shift_solver.models import ShiftType, Worker
from shift_solver.solver import VariableBuilder
from shift_solver.solver.solution_extractor import SolutionExtractor


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


class TestDBPersistenceCycle:
    """Tests for full database persistence cycle."""

    def test_full_persistence_cycle(self, session: Session) -> None:
        """Test complete workflow: init -> load -> solve -> persist -> reload."""
        # Step 1: Create and persist workers
        db_workers = [
            DBWorker(id="W001", name="Alice", worker_type="full_time"),
            DBWorker(id="W002", name="Bob", worker_type="full_time"),
        ]
        session.add_all(db_workers)
        session.commit()

        # Step 2: Create and persist shift types
        db_shift_types = [
            DBShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            DBShiftType(
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
        session.add_all(db_shift_types)
        session.commit()

        # Step 3: Load workers and shift types from DB to domain models
        loaded_workers = [
            Worker(
                id=dbw.id,
                name=dbw.name,
                worker_type=dbw.worker_type,
                restricted_shifts=frozenset(dbw.restricted_shifts),
                preferred_shifts=frozenset(dbw.preferred_shifts),
            )
            for dbw in session.query(DBWorker).all()
        ]

        loaded_shift_types = [
            ShiftType(
                id=dbs.id,
                name=dbs.name,
                category=dbs.category,
                start_time=dbs.start_time,
                end_time=dbs.end_time,
                duration_hours=dbs.duration_hours,
                workers_required=dbs.workers_required,
                is_undesirable=dbs.is_undesirable,
            )
            for dbs in session.query(DBShiftType).all()
        ]

        assert len(loaded_workers) == 2
        assert len(loaded_shift_types) == 2

        # Step 4: Solve the schedule
        model = cp_model.CpModel()
        num_periods = 2
        builder = VariableBuilder(
            model, loaded_workers, loaded_shift_types, num_periods=num_periods
        )
        variables = builder.build()

        coverage = CoverageConstraint(model, variables)
        coverage.apply(
            workers=loaded_workers, shift_types=loaded_shift_types, num_periods=num_periods
        )

        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in [cp_model.OPTIMAL, cp_model.FEASIBLE]

        # Step 5: Extract schedule from solution
        base_date = date(2026, 1, 5)
        period_dates = [
            (base_date + timedelta(weeks=i), base_date + timedelta(weeks=i, days=6))
            for i in range(num_periods)
        ]

        extractor = SolutionExtractor(
            solver=solver,
            variables=variables,
            workers=loaded_workers,
            shift_types=loaded_shift_types,
            period_dates=period_dates,
            schedule_id="SCH-001",
        )
        schedule = extractor.extract()

        # Step 6: Persist schedule to database
        db_schedule = DBSchedule(
            id=schedule.schedule_id,
            name="Test Schedule",
            start_date=schedule.start_date,
            end_date=schedule.end_date,
            period_type=schedule.period_type,
            status="completed",
        )
        session.add(db_schedule)
        session.commit()

        # Persist assignments
        for period in schedule.periods:
            for worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    db_assignment = DBAssignment(
                        schedule_id=schedule.schedule_id,
                        worker_id=worker_id,
                        shift_type_id=shift.shift_type_id,
                        period_index=shift.period_index,
                        date=shift.date,
                    )
                    session.add(db_assignment)
        session.commit()

        # Step 7: Reload schedule from database
        reloaded_schedule = session.get(DBSchedule, "SCH-001")
        assert reloaded_schedule is not None
        assert reloaded_schedule.period_type == "week"
        assert reloaded_schedule.status == "completed"

        # Verify assignments were persisted
        reloaded_assignments = session.query(DBAssignment).filter_by(
            schedule_id="SCH-001"
        ).all()

        # Should have 2 periods * 2 shift types * 1 worker each = 4 assignments
        assert len(reloaded_assignments) == 4

        # Verify each assignment has correct relationships
        for assignment in reloaded_assignments:
            assert assignment.worker_id in ["W001", "W002"]
            assert assignment.shift_type_id in ["day", "night"]
            assert assignment.schedule.id == "SCH-001"

    def test_round_trip_data_integrity(self, session: Session) -> None:
        """Test that data survives a complete round-trip through the database."""
        # Create worker with all fields populated
        original_worker = DBWorker(
            id="W001",
            name="Test Worker",
            worker_type="part_time",
            restricted_shifts=["night"],
            preferred_shifts=["day"],
            attributes={"department": "Sales", "seniority": 3},
        )
        session.add(original_worker)
        session.commit()

        # Clear session cache to force reload from DB
        session.expire_all()

        # Reload and verify
        reloaded = session.get(DBWorker, "W001")
        assert reloaded.name == "Test Worker"
        assert reloaded.worker_type == "part_time"
        assert reloaded.restricted_shifts == ["night"]
        assert reloaded.preferred_shifts == ["day"]
        assert reloaded.attributes["department"] == "Sales"
        assert reloaded.attributes["seniority"] == 3

    def test_persistence_with_various_schedule_sizes(self, session: Session) -> None:
        """Test persistence with different schedule sizes."""
        # Create workers and shift types
        workers = [
            DBWorker(id=f"W{i:03d}", name=f"Worker {i}")
            for i in range(5)
        ]
        shift_types = [
            DBShiftType(
                id="shift",
                name="Shift",
                category="any",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        session.add_all(workers + shift_types)
        session.commit()

        # Test different numbers of periods
        for num_periods in [1, 4, 8]:
            schedule_id = f"SCH-{num_periods:02d}"
            base_date = date(2026, 1, 5)

            # Create schedule
            db_schedule = DBSchedule(
                id=schedule_id,
                start_date=base_date,
                end_date=base_date + timedelta(weeks=num_periods - 1, days=6),
                period_type="week",
            )
            session.add(db_schedule)

            # Create assignments for each period
            for period_idx in range(num_periods):
                worker_idx = period_idx % len(workers)
                assignment = DBAssignment(
                    schedule_id=schedule_id,
                    worker_id=f"W{worker_idx:03d}",
                    shift_type_id="shift",
                    period_index=period_idx,
                    date=base_date + timedelta(weeks=period_idx),
                )
                session.add(assignment)
            session.commit()

            # Verify correct number of assignments
            assignments = session.query(DBAssignment).filter_by(
                schedule_id=schedule_id
            ).all()
            assert len(assignments) == num_periods

    def test_cascade_delete_on_schedule(self, session: Session) -> None:
        """Test that deleting a schedule cascades to assignments."""
        # Create worker, shift type, schedule, and assignment
        worker = DBWorker(id="W001", name="Test")
        shift_type = DBShiftType(
            id="shift",
            name="Shift",
            category="any",
            start_time=time(0, 0),
            end_time=time(8, 0),
            duration_hours=8.0,
        )
        schedule = DBSchedule(
            id="SCH-001",
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 11),
            period_type="week",
        )
        session.add_all([worker, shift_type, schedule])
        session.commit()

        assignment = DBAssignment(
            schedule_id="SCH-001",
            worker_id="W001",
            shift_type_id="shift",
            period_index=0,
            date=date(2026, 1, 5),
        )
        session.add(assignment)
        session.commit()

        # Verify assignment exists
        assert session.query(DBAssignment).count() == 1

        # Delete schedule
        session.delete(schedule)
        session.commit()

        # Assignment should be deleted via cascade
        assert session.query(DBAssignment).count() == 0
