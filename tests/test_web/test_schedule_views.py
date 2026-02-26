"""Tests for schedule visualization views (scheduler-123)."""

import datetime
from typing import Any

import pytest
from django.test import Client

from core.models import (
    Assignment,
    ScheduleRequest,
    ShiftType,
    SolverRun,
    Worker,
)

pytestmark = pytest.mark.django_db


def _make_request(**kwargs: Any) -> ScheduleRequest:
    """Create a ScheduleRequest with sensible defaults."""
    defaults: dict[str, Any] = {
        "name": "Test Schedule",
        "start_date": datetime.date(2026, 3, 1),
        "end_date": datetime.date(2026, 3, 7),
    }
    defaults.update(kwargs)
    return ScheduleRequest.objects.create(**defaults)


def _make_completed_run(
    request: ScheduleRequest | None = None,
) -> tuple[SolverRun, list[Worker], list[ShiftType]]:
    """Create a completed solver run with workers, shifts, and assignments."""
    req = request or _make_request()
    workers = [
        Worker.objects.create(worker_id="W1", name="Alice"),
        Worker.objects.create(worker_id="W2", name="Bob"),
    ]
    shifts = [
        ShiftType.objects.create(
            shift_type_id="DAY",
            name="Day Shift",
            category="Clinical",
            start_time=datetime.time(7, 0),
            duration_hours=12.0,
        ),
        ShiftType.objects.create(
            shift_type_id="NIGHT",
            name="Night Shift",
            category="Clinical",
            start_time=datetime.time(19, 0),
            duration_hours=12.0,
        ),
    ]
    run = SolverRun.objects.create(
        schedule_request=req,
        status="completed",
        progress_percent=100,
        result_json={"assignment_count": 4},
    )
    # Create assignments
    Assignment.objects.create(
        solver_run=run,
        worker=workers[0],
        shift_type=shifts[0],
        date=datetime.date(2026, 3, 1),
    )
    Assignment.objects.create(
        solver_run=run,
        worker=workers[1],
        shift_type=shifts[1],
        date=datetime.date(2026, 3, 1),
    )
    Assignment.objects.create(
        solver_run=run,
        worker=workers[0],
        shift_type=shifts[0],
        date=datetime.date(2026, 3, 2),
    )
    Assignment.objects.create(
        solver_run=run,
        worker=workers[1],
        shift_type=shifts[0],
        date=datetime.date(2026, 3, 2),
    )
    return run, workers, shifts


class TestScheduleView:
    """Tests for the schedule calendar view page."""

    def test_schedule_view_returns_200(self, client: Client) -> None:
        """Schedule view page returns HTTP 200."""
        run, _, _ = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/schedule/")
        assert response.status_code == 200

    def test_schedule_view_includes_fullcalendar(self, client: Client) -> None:
        """Schedule page includes FullCalendar JavaScript."""
        run, _, _ = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/schedule/")
        content = response.content.decode()
        assert "fullcalendar" in content.lower()

    def test_schedule_view_has_filter_controls(self, client: Client) -> None:
        """Schedule page includes worker and shift type filters."""
        run, workers, shifts = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/schedule/")
        content = response.content.decode()
        assert "Alice" in content
        assert "Bob" in content
        assert "Day Shift" in content
        assert "Night Shift" in content


class TestScheduleEventsEndpoint:
    """Tests for the schedule events JSON endpoint."""

    def test_events_returns_json(self, client: Client) -> None:
        """Events endpoint returns JSON array."""
        run, _, _ = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/schedule/events/")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"
        data = response.json()
        assert isinstance(data, list)

    def test_events_include_all_assignments(self, client: Client) -> None:
        """Events include all assignments from the solver run."""
        run, _, _ = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/schedule/events/")
        data = response.json()
        assert len(data) == 4

    def test_events_filtered_by_worker(self, client: Client) -> None:
        """Events can be filtered by worker_id parameter."""
        run, workers, _ = _make_completed_run()
        response = client.get(
            f"/solver-runs/{run.pk}/schedule/events/?worker_id={workers[0].pk}"
        )
        data = response.json()
        assert len(data) == 2
        for event in data:
            assert event["extendedProps"]["worker_name"] == "Alice"

    def test_events_filtered_by_shift_type(self, client: Client) -> None:
        """Events can be filtered by shift_type_id parameter."""
        run, _, shifts = _make_completed_run()
        response = client.get(
            f"/solver-runs/{run.pk}/schedule/events/?shift_type_id={shifts[1].pk}"
        )
        data = response.json()
        assert len(data) == 1
        assert data[0]["extendedProps"]["shift_type"] == "Night Shift"

    def test_events_have_correct_time_range(self, client: Client) -> None:
        """Event start/end times match shift type start time and duration."""
        run, _, _ = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/schedule/events/")
        data = response.json()
        # Find Alice's Day Shift on March 1
        day_events = [
            e
            for e in data
            if e["extendedProps"]["worker_name"] == "Alice"
            and e["start"] == "2026-03-01T07:00:00"
        ]
        assert len(day_events) == 1
        assert day_events[0]["end"] == "2026-03-01T19:00:00"

    def test_events_colored_by_category(self, client: Client) -> None:
        """Events include color based on shift category."""
        run, _, _ = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/schedule/events/")
        data = response.json()
        # All events should have a color field
        for event in data:
            assert "color" in event
            assert event["color"].startswith("#")
