"""Shared fixtures for IO tests including Plotly chart tests."""

from datetime import date, time

import pytest

from shift_solver.models import ShiftType, Worker
from shift_solver.models.schedule import PeriodAssignment, Schedule
from shift_solver.models.shift import ShiftInstance


@pytest.fixture
def sample_schedule() -> Schedule:
    """Build a sample schedule with 3 workers, 2 shift types, 2 periods.

    Assignments:
      Period 0 (Feb 2-8):
        W001 -> day, night
        W002 -> day
        W003 -> night
      Period 1 (Feb 9-15):
        W001 -> day
        W002 -> night
        W003 -> day, night
    """
    workers = [
        Worker(id="W001", name="Alice"),
        Worker(id="W002", name="Bob"),
        Worker(id="W003", name="Charlie"),
    ]
    shift_types = [
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
    period0 = PeriodAssignment(
        period_index=0,
        period_start=date(2026, 2, 2),
        period_end=date(2026, 2, 8),
        assignments={
            "W001": [
                ShiftInstance(shift_type_id="day", period_index=0, date=date(2026, 2, 2), worker_id="W001"),
                ShiftInstance(shift_type_id="night", period_index=0, date=date(2026, 2, 3), worker_id="W001"),
            ],
            "W002": [
                ShiftInstance(shift_type_id="day", period_index=0, date=date(2026, 2, 2), worker_id="W002"),
            ],
            "W003": [
                ShiftInstance(shift_type_id="night", period_index=0, date=date(2026, 2, 4), worker_id="W003"),
            ],
        },
    )
    period1 = PeriodAssignment(
        period_index=1,
        period_start=date(2026, 2, 9),
        period_end=date(2026, 2, 15),
        assignments={
            "W001": [
                ShiftInstance(shift_type_id="day", period_index=1, date=date(2026, 2, 9), worker_id="W001"),
            ],
            "W002": [
                ShiftInstance(shift_type_id="night", period_index=1, date=date(2026, 2, 10), worker_id="W002"),
            ],
            "W003": [
                ShiftInstance(shift_type_id="day", period_index=1, date=date(2026, 2, 9), worker_id="W003"),
                ShiftInstance(shift_type_id="night", period_index=1, date=date(2026, 2, 11), worker_id="W003"),
            ],
        },
    )
    return Schedule(
        schedule_id="test-schedule",
        start_date=date(2026, 2, 2),
        end_date=date(2026, 2, 15),
        period_type="week",
        periods=[period0, period1],
        workers=workers,
        shift_types=shift_types,
    )
