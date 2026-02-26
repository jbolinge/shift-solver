"""Tests for SolverSettings views (scheduler-109)."""

import datetime

import pytest
from django.test import Client

from core.models import ScheduleRequest, SolverSettings

pytestmark = pytest.mark.django_db


def _make_request(**kwargs) -> ScheduleRequest:
    """Create a ScheduleRequest with sensible defaults."""
    defaults = {
        "name": "Test Schedule",
        "start_date": datetime.date(2026, 3, 1),
        "end_date": datetime.date(2026, 3, 31),
    }
    defaults.update(kwargs)
    return ScheduleRequest.objects.create(**defaults)


class TestSolverSettingsView:
    """Tests for the solver settings display view."""

    def test_settings_page_returns_200(self, client: Client) -> None:
        """GET /requests/<pk>/settings/ returns HTTP 200."""
        req = _make_request()
        response = client.get(f"/requests/{req.pk}/settings/")
        assert response.status_code == 200

    def test_settings_shows_current_values(self, client: Client) -> None:
        """Settings page shows the current saved values."""
        req = _make_request()
        SolverSettings.objects.create(
            schedule_request=req,
            time_limit_seconds=120,
            num_search_workers=4,
            optimality_tolerance=0.05,
            log_search_progress=False,
        )

        response = client.get(f"/requests/{req.pk}/settings/")
        content = response.content.decode()

        assert "120" in content
        assert "4" in content
        assert "0.05" in content

    def test_settings_shows_defaults_for_new_request(self, client: Client) -> None:
        """New request without explicit settings shows default values."""
        req = _make_request()

        response = client.get(f"/requests/{req.pk}/settings/")
        content = response.content.decode()

        # Default values
        assert "60" in content
        assert "8" in content


class TestSolverSettingsEditView:
    """Tests for the solver settings edit view."""

    def test_update_time_limit(self, client: Client) -> None:
        """POST changes time_limit_seconds."""
        req = _make_request()
        SolverSettings.objects.create(schedule_request=req)

        data = {
            "time_limit_seconds": "300",
            "num_search_workers": "8",
            "optimality_tolerance": "0.0",
            "log_search_progress": "on",
        }
        response = client.post(f"/requests/{req.pk}/settings/edit/", data)

        assert response.status_code in (200, 302)
        settings = SolverSettings.objects.get(schedule_request=req)
        assert settings.time_limit_seconds == 300

    def test_update_num_workers(self, client: Client) -> None:
        """POST changes num_search_workers."""
        req = _make_request()
        SolverSettings.objects.create(schedule_request=req)

        data = {
            "time_limit_seconds": "60",
            "num_search_workers": "16",
            "optimality_tolerance": "0.0",
            "log_search_progress": "on",
        }
        response = client.post(f"/requests/{req.pk}/settings/edit/", data)

        assert response.status_code in (200, 302)
        settings = SolverSettings.objects.get(schedule_request=req)
        assert settings.num_search_workers == 16

    def test_invalid_time_limit_rejected(self, client: Client) -> None:
        """POST with 0 or negative time limit shows error."""
        req = _make_request()
        SolverSettings.objects.create(schedule_request=req)

        data = {
            "time_limit_seconds": "0",
            "num_search_workers": "8",
            "optimality_tolerance": "0.0",
            "log_search_progress": "on",
        }
        response = client.post(f"/requests/{req.pk}/settings/edit/", data)

        content = response.content.decode()
        assert "Time limit must be greater than zero" in content
        # Original value should be unchanged
        settings = SolverSettings.objects.get(schedule_request=req)
        assert settings.time_limit_seconds == 60

    def test_settings_auto_created_on_first_access(self, client: Client) -> None:
        """Accessing settings page creates default SolverSettings if none exist."""
        req = _make_request()

        assert not SolverSettings.objects.filter(schedule_request=req).exists()

        client.get(f"/requests/{req.pk}/settings/")

        assert SolverSettings.objects.filter(schedule_request=req).exists()
        settings = SolverSettings.objects.get(schedule_request=req)
        assert settings.time_limit_seconds == 60
        assert settings.num_search_workers == 8
        assert settings.optimality_tolerance == 0.0
        assert settings.log_search_progress is True
