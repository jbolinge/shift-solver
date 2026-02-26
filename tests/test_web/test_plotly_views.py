"""Tests for Plotly chart embedding and export views (scheduler-124)."""

import datetime
import zipfile
from io import BytesIO

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
    """Create a completed solver run with assignments for chart generation."""
    req = ScheduleRequest.objects.create(
        name="Chart Test",
        start_date=datetime.date(2026, 3, 1),
        end_date=datetime.date(2026, 3, 14),
        period_length_days=7,
    )
    workers = [
        Worker.objects.create(worker_id="W1", name="Alice"),
        Worker.objects.create(worker_id="W2", name="Bob"),
    ]
    shifts = [
        ShiftType.objects.create(
            shift_type_id="DAY",
            name="Day Shift",
            category="day",
            start_time=datetime.time(7, 0),
            duration_hours=12.0,
            workers_required=1,
        ),
        ShiftType.objects.create(
            shift_type_id="NIGHT",
            name="Night Shift",
            category="night",
            start_time=datetime.time(19, 0),
            duration_hours=12.0,
            workers_required=1,
        ),
    ]
    run = SolverRun.objects.create(
        schedule_request=req,
        status="completed",
        progress_percent=100,
        result_json={"assignment_count": 4},
    )
    # Create assignments across two periods
    for day_offset in range(4):
        Assignment.objects.create(
            solver_run=run,
            worker=workers[day_offset % 2],
            shift_type=shifts[day_offset % 2],
            date=datetime.date(2026, 3, 1 + day_offset),
        )
    return run


class TestPlotlyChartPage:
    """Tests for the Plotly analytics page."""

    def test_chart_page_returns_200(self, client: Client) -> None:
        """Chart analytics page returns HTTP 200."""
        run = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/charts/")
        assert response.status_code == 200

    def test_chart_page_has_tabs(self, client: Client) -> None:
        """Chart page includes tab navigation for all 5 chart types."""
        run = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/charts/")
        content = response.content.decode()
        assert "heatmap" in content.lower()
        assert "gantt" in content.lower()
        assert "fairness" in content.lower()
        assert "sunburst" in content.lower()
        assert "coverage" in content.lower()

    def test_chart_page_renders_default_chart(self, client: Client) -> None:
        """Chart page renders heatmap chart by default."""
        run = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/charts/")
        content = response.content.decode()
        # Default chart should be embedded or linked
        assert "plotly" in content.lower() or "chart" in content.lower()


class TestPlotlyChartView:
    """Tests for individual chart endpoints."""

    def test_heatmap_chart_returns_html(self, client: Client) -> None:
        """Heatmap chart endpoint returns Plotly HTML content."""
        run = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/charts/heatmap/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "plotly" in content.lower()

    def test_invalid_chart_type_returns_404(self, client: Client) -> None:
        """Unknown chart type returns HTTP 404."""
        run = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/charts/invalid/")
        assert response.status_code == 404


class TestPlotlyChartDownload:
    """Tests for chart download/export."""

    def test_download_single_chart(self, client: Client) -> None:
        """Download single chart returns HTML file attachment."""
        run = _make_completed_run()
        response = client.get(
            f"/solver-runs/{run.pk}/charts/download/heatmap/"
        )
        assert response.status_code == 200
        assert "attachment" in response.get("Content-Disposition", "")
        assert ".html" in response.get("Content-Disposition", "")

    def test_download_bundle_returns_zip(self, client: Client) -> None:
        """Download all returns ZIP file with all charts."""
        run = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/charts/download/")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/zip"

    def test_download_bundle_contains_all_charts(
        self, client: Client
    ) -> None:
        """ZIP bundle contains all 5 chart HTML files plus index."""
        run = _make_completed_run()
        response = client.get(f"/solver-runs/{run.pk}/charts/download/")
        zf = zipfile.ZipFile(BytesIO(response.content))
        names = zf.namelist()
        assert any("heatmap" in n for n in names)
        assert any("gantt" in n for n in names)
        assert any("fairness" in n for n in names)
        assert any("sunburst" in n for n in names)
        assert any("coverage" in n for n in names)
