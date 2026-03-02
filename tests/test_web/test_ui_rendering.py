"""Tests for template tag adoption across templates (scheduler-130)."""

import pytest
from django.test import Client


@pytest.mark.django_db
class TestFormRendering:
    def test_worker_form_shows_help_text(self, client: Client):
        """Worker form page renders help text for fields that define it."""
        response = client.get("/workers/create/")
        html = response.content.decode()
        assert "text-gray-500" in html

    def test_shift_form_shows_help_text(self, client: Client):
        """Shift form page renders help text."""
        response = client.get("/shifts/create/")
        html = response.content.decode()
        assert "text-gray-500" in html

    def test_form_errors_render_in_red(self, client: Client):
        """Form validation errors appear with red styling."""
        response = client.post("/workers/create/", data={})
        html = response.content.decode()
        assert "text-red-600" in html


@pytest.mark.django_db
class TestBadgeRendering:
    def test_worker_row_uses_badge_tag(self, client: Client):
        """Worker list renders status badges."""
        from core.models import Worker

        Worker.objects.create(worker_id="W1", name="Test", fte=1.0)
        response = client.get("/workers/")
        html = response.content.decode()
        assert "rounded-full" in html
        assert "bg-green-100" in html or "bg-red-100" in html

    def test_constraint_row_uses_badge_tag(self, client: Client):
        """Constraint list renders type badges (hard/soft)."""
        from core.models import ConstraintConfig

        ConstraintConfig.objects.create(
            constraint_type="test_constraint",
            description="Test",
            enabled=True,
            is_hard=True,
            weight=1,
        )
        response = client.get("/constraints/")
        html = response.content.decode()
        assert "rounded-full" in html

    def test_request_row_uses_badge_tag(self, client: Client):
        """Request list renders status badges."""
        import datetime

        from core.models import ScheduleRequest

        ScheduleRequest.objects.create(
            name="Test",
            start_date=datetime.date(2026, 3, 1),
            end_date=datetime.date(2026, 3, 31),
            period_length_days=7,
        )
        response = client.get("/requests/")
        html = response.content.decode()
        assert "rounded-full" in html
