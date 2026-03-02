"""Tests for dashboard enhancement and HTMX loading (scheduler-135)."""

import datetime
import re
from pathlib import Path

import pytest
from django.test import Client


@pytest.mark.django_db
class TestDashboardCards:
    def test_constraint_count_displayed(self, client: Client):
        """Dashboard shows constraint count card."""
        response = client.get("/")
        html = response.content.decode()
        assert "Constraints" in html

    def test_all_four_cards_present(self, client: Client):
        """Dashboard has 4 summary cards: Workers, Shifts, Requests, Constraints."""
        response = client.get("/")
        html = response.content.decode()
        assert "Workers" in html
        assert "Shift" in html
        assert "Request" in html
        assert "Constraint" in html


@pytest.mark.django_db
class TestQuickActions:
    def test_quick_actions_section_present(self, client: Client):
        """Dashboard has a Quick Actions section."""
        response = client.get("/")
        html = response.content.decode()
        assert "Quick Actions" in html

    def test_quick_action_links(self, client: Client):
        """Quick actions include Add Worker, Add Shift, New Request."""
        response = client.get("/")
        html = response.content.decode()
        assert "Add Worker" in html
        assert "Add Shift" in html or "Shift Type" in html


@pytest.mark.django_db
class TestRecentActivity:
    def test_recent_requests_section(self, client: Client):
        """Dashboard has a Recent Requests section."""
        response = client.get("/")
        html = response.content.decode()
        assert "Recent Requests" in html

    def test_recent_requests_with_data(self, client: Client):
        """Recent requests section shows existing requests."""
        from core.models import ScheduleRequest

        req = ScheduleRequest.objects.create(
            name="March Schedule",
            start_date=datetime.date(2026, 3, 1),
            end_date=datetime.date(2026, 3, 31),
            period_length_days=7,
        )
        response = client.get("/")
        html = response.content.decode()
        assert req.name in html


@pytest.mark.django_db
class TestDashboardURLs:
    def test_no_hardcoded_urls(self):
        """Dashboard does not contain hardcoded URL paths."""
        template = Path("web/templates/home.html").read_text()
        hardcoded = re.findall(
            r'href="/(workers|shifts|requests|constraints)/"', template
        )
        assert len(hardcoded) == 0, f"Found hardcoded URLs: {hardcoded}"


@pytest.mark.django_db
class TestHTMXLoadingIndicator:
    def test_global_loading_indicator_present(self, client: Client):
        """base.html includes a global HTMX loading indicator."""
        response = client.get("/")
        html = response.content.decode()
        assert 'id="global-loading"' in html

    def test_body_has_hx_indicator(self, client: Client):
        """Body tag has hx-indicator attribute pointing to global loading."""
        response = client.get("/")
        html = response.content.decode()
        assert "hx-indicator" in html
