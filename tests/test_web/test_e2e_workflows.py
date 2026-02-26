"""E2E tests for web UI workflows (scheduler-126).

These tests exercise complete user workflows through the web UI,
from creating workers and shifts to launching the solver and viewing results.
"""

import datetime
import io

import pytest
from django.test import Client

from core.models import (
    ConstraintConfig,
    ScheduleRequest,
    ShiftType,
    SolverRun,
    SolverSettings,
    Worker,
)
from core.solver_runner import SolverRunner

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


def _create_workers(client: Client) -> list[Worker]:
    """Create workers via CRUD views."""
    workers = []
    for i in range(5):
        data = {
            "worker_id": f"E2E-W{i+1}",
            "name": f"Worker {i+1}",
            "email": f"worker{i+1}@test.com",
            "group": "Team A" if i < 3 else "Team B",
            "worker_type": "full_time",
            "fte": "1.0",
            "is_active": "on",
        }
        client.post("/workers/create/", data)
        w = Worker.objects.get(worker_id=f"E2E-W{i+1}")
        workers.append(w)
    return workers


def _create_shifts(client: Client) -> list[ShiftType]:
    """Create shift types via CRUD views."""
    shift_data = [
        {
            "shift_type_id": "E2E-DAY",
            "name": "Day Shift",
            "category": "day",
            "start_time": "07:00",
            "duration_hours": "12.0",
            "min_workers": "1",
            "max_workers": "3",
            "workers_required": "2",
            "is_active": "on",
        },
        {
            "shift_type_id": "E2E-NIGHT",
            "name": "Night Shift",
            "category": "night",
            "start_time": "19:00",
            "duration_hours": "12.0",
            "min_workers": "1",
            "max_workers": "2",
            "workers_required": "1",
            "is_active": "on",
            "is_undesirable": "on",
        },
        {
            "shift_type_id": "E2E-EVE",
            "name": "Evening Shift",
            "category": "evening",
            "start_time": "15:00",
            "duration_hours": "8.0",
            "min_workers": "1",
            "max_workers": "2",
            "workers_required": "1",
            "is_active": "on",
        },
    ]
    shifts = []
    for data in shift_data:
        client.post("/shifts/create/", data)
        s = ShiftType.objects.get(shift_type_id=data["shift_type_id"])
        shifts.append(s)
    return shifts


class TestCompleteSchedulingWorkflow:
    """Tests exercising the complete scheduling cycle through the web UI."""

    def test_create_workers_and_shifts(self, client: Client) -> None:
        """Create workers and shift types via CRUD views."""
        workers = _create_workers(client)
        shifts = _create_shifts(client)

        assert Worker.objects.count() == 5
        assert ShiftType.objects.count() == 3

        # Verify via list views
        response = client.get("/workers/")
        content = response.content.decode()
        for w in workers:
            assert w.name in content

        response = client.get("/shifts/")
        content = response.content.decode()
        for s in shifts:
            assert s.name in content

    def test_set_availability(self, client: Client) -> None:
        """Set worker availability via calendar endpoint."""
        workers = _create_workers(client)
        _create_shifts(client)

        # Set availability for first worker on a date
        response = client.post(
            "/availability/update/",
            {
                "worker_id": str(workers[0].pk),
                "date": "2026-03-01",
            },
        )
        assert response.status_code == 200

        # Verify via events endpoint
        response = client.get(
            f"/availability/events/?worker_id={workers[0].pk}"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_configure_constraints(self, client: Client) -> None:
        """Configure constraints via constraint UI."""
        # Seed default constraints
        client.post("/constraints/seed/")

        assert ConstraintConfig.objects.count() > 0

        # Verify via list view
        response = client.get("/constraints/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "coverage" in content.lower()

    def test_create_and_launch_schedule(self, client: Client) -> None:
        """Create request, launch solver, wait for completion."""
        workers = _create_workers(client)
        shifts = _create_shifts(client)

        # Seed constraints
        client.post("/constraints/seed/")

        # Create schedule request via form
        request_data = {
            "name": "E2E Test Schedule",
            "start_date": "2026-03-01",
            "end_date": "2026-03-07",
            "period_length_days": "7",
        }
        client.post("/requests/create/", request_data)

        req = ScheduleRequest.objects.get(name="E2E Test Schedule")
        # Set M2M relations directly (form doesn't include M2M fields)
        req.workers.set(workers)
        req.shift_types.set(shifts)

        # Create solver settings
        SolverSettings.objects.create(
            schedule_request=req,
            time_limit_seconds=30,
        )

        # Launch solver (synchronously via _execute for testing)
        solver_run = SolverRun.objects.create(
            schedule_request=req, status="pending"
        )
        runner = SolverRunner(solver_run_id=solver_run.id)
        runner._execute()  # Direct call for test reliability

        solver_run.refresh_from_db()
        assert solver_run.status == "completed"
        assert solver_run.assignments.count() > 0

    def test_view_schedule_calendar(self, client: Client) -> None:
        """View schedule via FullCalendar events endpoint."""
        workers = _create_workers(client)
        shifts = _create_shifts(client)
        client.post("/constraints/seed/")

        req = ScheduleRequest.objects.create(
            name="Calendar Test",
            start_date=datetime.date(2026, 3, 1),
            end_date=datetime.date(2026, 3, 7),
        )
        req.workers.set(workers)
        req.shift_types.set(shifts)
        SolverSettings.objects.create(schedule_request=req, time_limit_seconds=30)

        solver_run = SolverRun.objects.create(
            schedule_request=req, status="pending"
        )
        runner = SolverRunner(solver_run_id=solver_run.id)
        runner._execute()
        solver_run.refresh_from_db()

        # View schedule calendar page
        response = client.get(f"/solver-runs/{solver_run.pk}/schedule/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "fullcalendar" in content.lower()

        # Fetch events
        response = client.get(
            f"/solver-runs/{solver_run.pk}/schedule/events/"
        )
        assert response.status_code == 200
        events = response.json()
        assert len(events) > 0
        # Each event should have title, start, end
        for event in events:
            assert "title" in event
            assert "start" in event
            assert "end" in event

    def test_export_schedule_results(self, client: Client) -> None:
        """Export schedule results to Excel and JSON."""
        workers = _create_workers(client)
        shifts = _create_shifts(client)
        client.post("/constraints/seed/")

        req = ScheduleRequest.objects.create(
            name="Export Test",
            start_date=datetime.date(2026, 3, 1),
            end_date=datetime.date(2026, 3, 7),
        )
        req.workers.set(workers)
        req.shift_types.set(shifts)
        SolverSettings.objects.create(schedule_request=req, time_limit_seconds=30)

        solver_run = SolverRun.objects.create(
            schedule_request=req, status="pending"
        )
        runner = SolverRunner(solver_run_id=solver_run.id)
        runner._execute()
        solver_run.refresh_from_db()

        # Export page
        response = client.get(f"/solver-runs/{solver_run.pk}/export/")
        assert response.status_code == 200

        # JSON export
        response = client.get(f"/solver-runs/{solver_run.pk}/export/json/")
        assert response.status_code == 200
        data = response.json()
        assert "assignments" in data
        assert len(data["assignments"]) > 0

        # Excel export
        response = client.get(f"/solver-runs/{solver_run.pk}/export/excel/")
        assert response.status_code == 200
        assert ".xlsx" in response.get("Content-Disposition", "")


class TestDataImportWorkflow:
    """Tests for the import-to-schedule workflow."""

    def test_import_csv_and_schedule(self, client: Client) -> None:
        """Upload CSV data, create request, solve, and verify results."""
        # Upload workers via CSV
        csv_content = (
            "id,name,worker_type\n"
            "IMP-W1,ImportAlice,full_time\n"
            "IMP-W2,ImportBob,full_time\n"
            "IMP-W3,ImportCharlie,full_time\n"
        )
        csv_file = io.BytesIO(csv_content.encode("utf-8"))
        csv_file.name = "workers.csv"

        client.post(
            "/import/upload/",
            {"file": csv_file, "data_type": "workers"},
            format="multipart",
        )
        client.post("/import/confirm/", {"data_type": "workers"})

        assert Worker.objects.filter(worker_id="IMP-W1").exists()
        assert Worker.objects.filter(worker_id="IMP-W2").exists()
        assert Worker.objects.filter(worker_id="IMP-W3").exists()

        # Create shifts manually
        _create_shifts(client)

        # Create request and solve
        workers = Worker.objects.filter(worker_id__startswith="IMP-")
        shifts = ShiftType.objects.filter(shift_type_id__startswith="E2E-")
        client.post("/constraints/seed/")

        req = ScheduleRequest.objects.create(
            name="Import Test",
            start_date=datetime.date(2026, 3, 1),
            end_date=datetime.date(2026, 3, 7),
        )
        req.workers.set(workers)
        req.shift_types.set(shifts)
        SolverSettings.objects.create(schedule_request=req, time_limit_seconds=30)

        solver_run = SolverRun.objects.create(
            schedule_request=req, status="pending"
        )
        runner = SolverRunner(solver_run_id=solver_run.id)
        runner._execute()
        solver_run.refresh_from_db()

        assert solver_run.status == "completed"
        assert solver_run.assignments.count() > 0


class TestHTMXInteractions:
    """Tests for HTMX partial vs full page responses."""

    def test_htmx_create_returns_partial(self, client: Client) -> None:
        """HTMX requests return partial HTML, not full pages."""
        data = {
            "worker_id": "HTMX-W1",
            "name": "HTMX Worker",
            "email": "",
            "group": "",
            "worker_type": "",
            "fte": "1.0",
            "is_active": "on",
        }
        response = client.post(
            "/workers/create/",
            data,
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        content = response.content.decode()
        # HTMX response should be a partial (row), not contain full page structure
        assert "<!DOCTYPE" not in content
        assert "HTMX Worker" in content

    def test_htmx_delete_removes_element(self, client: Client) -> None:
        """HTMX delete returns empty response for DOM removal."""
        worker = Worker.objects.create(worker_id="DEL-W1", name="Delete Me")

        response = client.post(
            f"/workers/{worker.pk}/delete/",
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert response.content == b""
        assert not Worker.objects.filter(pk=worker.pk).exists()

    def test_non_htmx_returns_full_page(self, client: Client) -> None:
        """Non-HTMX requests return full HTML pages."""
        Worker.objects.create(worker_id="FP-W1", name="Full Page Worker")

        response = client.get("/workers/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "<!DOCTYPE" in content or "<html" in content
        assert "Full Page Worker" in content
