"""Tests for ScheduleRequest CRUD views (scheduler-118)."""

import datetime

import pytest
from django.test import Client

from core.models import ScheduleRequest, Worker

pytestmark = pytest.mark.django_db


class TestRequestListView:
    """Tests for the schedule request list view."""

    def test_request_list_returns_200(self, client: Client) -> None:
        """GET /requests/ returns HTTP 200."""
        response = client.get("/requests/")
        assert response.status_code == 200

    def test_request_list_shows_all_requests(self, client: Client) -> None:
        """Request list displays all requests in the table."""
        ScheduleRequest.objects.create(
            name="January Schedule",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 1, 31),
        )
        ScheduleRequest.objects.create(
            name="February Schedule",
            start_date=datetime.date(2026, 2, 1),
            end_date=datetime.date(2026, 2, 28),
        )

        response = client.get("/requests/")
        content = response.content.decode()

        assert "January Schedule" in content
        assert "February Schedule" in content

    def test_request_list_shows_status_badges(self, client: Client) -> None:
        """Request list shows status text for each request."""
        ScheduleRequest.objects.create(
            name="Draft Request",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 1, 31),
            status="draft",
        )
        ScheduleRequest.objects.create(
            name="Completed Request",
            start_date=datetime.date(2026, 2, 1),
            end_date=datetime.date(2026, 2, 28),
            status="completed",
        )

        response = client.get("/requests/")
        content = response.content.decode()

        assert "Draft" in content
        assert "Completed" in content


class TestRequestCreateView:
    """Tests for the schedule request create view."""

    def test_create_request_post_valid(self, client: Client) -> None:
        """POST /requests/create/ with valid data creates a new request."""
        data = {
            "name": "March Schedule",
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
            "period_length_days": "7",
        }
        response = client.post("/requests/create/", data)

        assert ScheduleRequest.objects.count() == 1
        req = ScheduleRequest.objects.first()
        assert req is not None
        assert req.name == "March Schedule"
        assert req.status == "draft"
        assert response.status_code == 302

    def test_create_request_invalid_date_range(self, client: Client) -> None:
        """POST with end_date < start_date returns form errors."""
        data = {
            "name": "Bad Dates",
            "start_date": "2026-03-31",
            "end_date": "2026-03-01",
            "period_length_days": "7",
        }
        response = client.post("/requests/create/", data)

        assert response.status_code == 200
        assert ScheduleRequest.objects.count() == 0
        content = response.content.decode()
        assert "End date must be on or after start date" in content

    def test_create_request_default_status_draft(self, client: Client) -> None:
        """New request status defaults to 'draft'."""
        data = {
            "name": "Auto Draft",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "period_length_days": "14",
        }
        client.post("/requests/create/", data)

        req = ScheduleRequest.objects.first()
        assert req is not None
        assert req.status == "draft"


class TestRequestDetailView:
    """Tests for the schedule request detail view."""

    def test_detail_returns_200(self, client: Client) -> None:
        """GET /requests/<pk>/ returns HTTP 200."""
        req = ScheduleRequest.objects.create(
            name="Detail Test",
            start_date=datetime.date(2026, 5, 1),
            end_date=datetime.date(2026, 5, 31),
        )
        response = client.get(f"/requests/{req.pk}/")
        assert response.status_code == 200

    def test_detail_shows_date_range(self, client: Client) -> None:
        """Detail page shows the start and end dates."""
        req = ScheduleRequest.objects.create(
            name="Date Range Test",
            start_date=datetime.date(2026, 6, 1),
            end_date=datetime.date(2026, 6, 30),
        )
        response = client.get(f"/requests/{req.pk}/")
        content = response.content.decode()

        assert "June 1, 2026" in content
        assert "June 30, 2026" in content

    def test_detail_shows_selected_workers(self, client: Client) -> None:
        """Detail page shows 'All active workers' when no workers selected."""
        req = ScheduleRequest.objects.create(
            name="Workers Test",
            start_date=datetime.date(2026, 7, 1),
            end_date=datetime.date(2026, 7, 31),
        )
        response = client.get(f"/requests/{req.pk}/")
        content = response.content.decode()

        assert "All active workers" in content

        # Now add specific workers and check they are shown
        w1 = Worker.objects.create(worker_id="W1", name="Alice Smith")
        w2 = Worker.objects.create(worker_id="W2", name="Bob Jones")
        req.workers.add(w1, w2)

        response = client.get(f"/requests/{req.pk}/")
        content = response.content.decode()

        assert "Alice Smith" in content
        assert "Bob Jones" in content


class TestRequestDeleteView:
    """Tests for the schedule request delete view."""

    def test_delete_request_removes_from_db(self, client: Client) -> None:
        """POST /requests/<pk>/delete/ removes the request from the database."""
        req = ScheduleRequest.objects.create(
            name="To Delete",
            start_date=datetime.date(2026, 8, 1),
            end_date=datetime.date(2026, 8, 31),
        )
        response = client.post(f"/requests/{req.pk}/delete/")

        assert ScheduleRequest.objects.count() == 0
        assert response.status_code == 302
