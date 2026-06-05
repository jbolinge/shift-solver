"""Tests that previously-orphaned pages are now linked from the UI."""

from datetime import date

import pytest
from django.test import Client

from core.models import ScheduleRequest, SolverRun

pytestmark = pytest.mark.django_db


def _make_request() -> ScheduleRequest:
    return ScheduleRequest.objects.create(
        name="Test",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 7),
        period_length_days=7,
    )


def test_request_detail_links_to_solver_settings(client: Client) -> None:
    """The request detail page links to the (previously orphaned) settings page."""
    req = _make_request()
    response = client.get(f"/requests/{req.pk}/")
    content = response.content.decode()
    assert response.status_code == 200
    assert f"/requests/{req.pk}/settings/" in content


def test_results_page_links_to_charts_and_export(client: Client) -> None:
    """A completed run's results page links to Analytics and Export pages."""
    req = _make_request()
    run = SolverRun.objects.create(schedule_request=req, status="completed")
    response = client.get(f"/solver-runs/{run.pk}/results/")
    content = response.content.decode()
    assert response.status_code == 200
    assert f"/solver-runs/{run.pk}/charts/" in content
    assert f"/solver-runs/{run.pk}/export/" in content


def test_schedule_view_links_to_charts_and_export(client: Client) -> None:
    """The schedule calendar view links to Analytics and Export pages."""
    req = _make_request()
    run = SolverRun.objects.create(schedule_request=req, status="completed")
    response = client.get(f"/solver-runs/{run.pk}/schedule/")
    content = response.content.decode()
    assert response.status_code == 200
    assert f"/solver-runs/{run.pk}/charts/" in content
    assert f"/solver-runs/{run.pk}/export/" in content
