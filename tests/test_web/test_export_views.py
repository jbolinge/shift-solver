"""Tests for schedule export views (scheduler-125)."""

import datetime
import json

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


def _make_completed_run() -> SolverRun:
    """Create a completed solver run with assignments for export."""
    req = ScheduleRequest.objects.create(
        name="Export Test",
        start_date=datetime.date(2026, 3, 1),
        end_date=datetime.date(2026, 3, 7),
        period_length_days=7,
    )
    worker = Worker.objects.create(worker_id="W1", name="Alice")
    shift = ShiftType.objects.create(
        shift_type_id="DAY",
        name="Day Shift",
        category="day",
        start_time=datetime.time(7, 0),
        duration_hours=12.0,
        workers_required=1,
    )
    run = SolverRun.objects.create(
        schedule_request=req,
        status="completed",
        progress_percent=100,
        result_json={"assignment_count": 2},
    )
    Assignment.objects.create(
        solver_run=run,
        worker=worker,
        shift_type=shift,
        date=datetime.date(2026, 3, 1),
    )
    Assignment.objects.create(
        solver_run=run,
        worker=worker,
        shift_type=shift,
        date=datetime.date(2026, 3, 2),
    )
    return run


class TestExportPage:
    """Tests for the export page."""

    def test_export_page_returns_200(self, client: Client) -> None:
        """Export page returns HTTP 200."""
        run = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/export/")
        assert response.status_code == 200


class TestExportDownload:
    """Tests for schedule export downloads."""

    def test_export_excel_returns_file(self, client: Client) -> None:
        """Excel export returns downloadable file."""
        run = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/export/excel/")
        assert response.status_code == 200
        assert "attachment" in response.get("Content-Disposition", "")
        assert ".xlsx" in response.get("Content-Disposition", "")

    def test_export_json_returns_file(self, client: Client) -> None:
        """JSON export returns downloadable file."""
        run = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/export/json/")
        assert response.status_code == 200
        assert "attachment" in response.get("Content-Disposition", "")
        # Verify JSON is valid
        data = json.loads(response.content)
        assert "assignments" in data

    def test_export_invalid_format_returns_400(self, client: Client) -> None:
        """Unknown export format returns HTTP 400."""
        run = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/export/invalid/")
        assert response.status_code == 400
